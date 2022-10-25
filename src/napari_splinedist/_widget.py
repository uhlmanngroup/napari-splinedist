from pathlib import Path

import numpy as np
from napari.layers import Image as ImageLayer
from napari.layers.shapes.shapes import Mode
from napari.qt.threading import GeneratorWorker as NapariGeneratorWorker
from napari.qt.threading import thread_worker
from napari_splineit._writer import write_splineit
from napari_splineit.interpolation import (
    interpolator_factory as splineit_interpolator_factory,
)
from napari_splineit.interpolation.uhlmann import knots_from_coefs
from napari_splineit.layer.layer_factory import (
    layer_factory as splineit_layer_factory,
)
from napari_splineit.widgets.double_spin_slider import DoubleSpinSlider
from napari_splineit.widgets.spin_slider import SpinSlider
from qtpy.QtCore import QObject, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from skimage import io as skimage_io

from ._logging import logger
from .config.config import APPDIR, CONFIG
from .exceptions import NoInputImageException
from .model.predict import predict
from .utils.colormap import make_colormap
from .widgets.color_picker_push_button import ColorPicklerPushButton
from .widgets.image_layer_combo_box import ImageLayerComboBox
from .widgets.model_download_widget import ModelDownloadWidget
from .widgets.progress_widget import ProgressWidget
from .widgets.rotating_logo_widget import RotatingLogoWidget


class GeneratorWorker(NapariGeneratorWorker):

    """This class is used add extra signals to naparis thread worker
        (https://napari.org/stable/guides/threading.html#threading-in-napari-with-thread-worker)

    Attributes:
        extra_signals (Signal): class with an extra signal to do
                                some progress reporting from the
                                worker-thread which runs the
                                splinedist prediction
    """

    class ExtraSignals(QObject):
        progress = Signal(str, int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra_signals = GeneratorWorker.ExtraSignals()


class SplineDistWidget(QWidget):
    def __init__(self, napari_viewer):
        """Setup the SplineDist Widget

        Args:
            napari_viewer : The napari viewer
        """
        super().__init__()

        # napari viewer itself
        self.viewer = napari_viewer

        # this is the default edge/face color used for
        # the interpolated polygons
        edge_color = QColor(255, 0, 0, 255)
        face_color = QColor(85, 170, 255, 100)

        # add all the widgets/ui-elements
        self._init_ui(edge_color=edge_color, face_color=face_color)

        # connect the events: ie what happens when widgets are clicked etc
        self._connect_events()

        # pass the list of models urls/path to the model widget
        # this widget is used to select models.
        # The selected model is downloaded (only once, results
        # are cached on file)
        self._model_download_widget.setModelsMeta(CONFIG.models)

        # the main worker where splinedist is run
        self.worker = None

        # The result layers:
        # - labels_layer shows the pixelized objects
        # - ctlr_layer are the controll points
        # - interpolated_layer shows the interpolated splines
        self.labels_layer = None
        self.ctrl_layer = None
        self.interpolated_layer = None

        # the last results
        self._last_results = None

        # the ctrl_layer / interpolated_layer
        # is only updte
        self._ctrl_layer_is_up_to_date = False

        # colormap with inital size to avoid
        # recomputation
        self._colormap_capacity = 1000
        self._colormap = make_colormap(mx=self._colormap_capacity)

    def _init_ui(self, edge_color, face_color):
        """Initialize UI components

        Args:
            edge_color : current edge color used for spline layers
            face_color : current face color used for spline layers
        """

        # Layouts:
        # =========================================================
        # the "outer layout" is the box (a vertical box)
        #
        # [                       <-- box layout with grid and form layout
        #   [(logo) (header)]     <-- grid layout with the logo and the header
        #   [                     <-- form layout with text widget pairs
        #     "text" : (widget),
        #     ....
        #     "text" : (widget),
        #   ]
        # ]
        # =======================================================
        box = QVBoxLayout()
        self.setLayout(box)

        # the grid contains the topleft logo and the header
        grid = QGridLayout()

        # the form layout contains all the widgets like buttons and sliders
        form = QFormLayout()

        # the grid and form layout to the outer layout
        box.addLayout(grid)
        box.addLayout(form)

        # the HTML of the header / heading
        self._header_label = QLabel(
            """
            <h1><strong>napari-splinedist</strong></h1>
            <p><strong>
            Cite This:
            </strong><strong>
            <a href="https://ieeexplore.ieee.org/abstract/document/9433928">
            Splinedist: Automated Cell Segmentation With Spline Curves
            </a></strong></p>
        """
        )
        # make the URL in the header clickable
        self._header_label.setOpenExternalLinks(True)

        # the "spline-snake" logo which can be rotated
        self._logo_widget = RotatingLogoWidget()

        # add the logo and the header to the grid layout
        grid.addWidget(self._logo_widget, 0, 0)
        grid.addWidget(self._header_label, 0, 1)

        # to select on which input image we run spinedist
        self._input_image_combo_box = ImageLayerComboBox(self.viewer)

        # to select the model which shall be used
        self._model_download_widget = ModelDownloadWidget(APPDIR)

        # should image be normalized? (default yes)
        self._normalize_img_cb = QCheckBox()
        self._normalize_img_cb.setChecked(True)

        # quantiles sliders to normalize image
        self._low_quantile_slider = DoubleSpinSlider([0, 1], 0.01)
        self._high_quantile_slider = DoubleSpinSlider([0, 1], 0.998)

        # should image be inverted (default no)
        self._invert_img_cb = QCheckBox()
        self._invert_img_cb.setChecked(False)

        # threshold slider for probabilities
        self._prob_thresh_slider = DoubleSpinSlider([0, 1.0], 0.5)

        # slider for non-max. supression
        self._nms_thresh_slider = DoubleSpinSlider([0, 1.0], 0.5)

        # should splinedist only be run of the visible
        # part of the image (default no)
        self._run_on_visible_only_cb = QCheckBox()
        self._run_on_visible_only_cb.setChecked(False)

        # should the prediction be done on tiles?
        # (if both x and y tiles are 1, we do not used
        # tiled prediction on the whole image)
        self._n_tiles_x = SpinSlider([1, 10], 1)
        self._n_tiles_y = SpinSlider([1, 10], 1)

        # select the edge and face color of the interpolated slines
        # tracking=True means that the "events are fired live"
        # st. one see the  change of the color of the splines
        # right away (ie without pressing "OK" in the colorpicker)
        self._edge_color_sel = ColorPicklerPushButton(
            edge_color, with_alpha=True, tracking=True
        )
        self._face_color_sel = ColorPicklerPushButton(
            face_color, with_alpha=True, tracking=True
        )

        # run splineit
        self._run_button = QPushButton("run")

        # to show some progress
        self._progress_widget = ProgressWidget(self)

        # save the results of splineit to disk,
        # this will be enabled once results are
        # available
        self._save_button = QPushButton("Save")
        self._save_button.setEnabled(False)

        # make the results editable splines
        # (ie create / fill the splineit layers)
        # this will be enabled once results are
        # available
        self._edit_button = QPushButton("Edit")
        self._edit_button.setEnabled(False)

        # make the results editable splines
        # (ie create / fill the splineit layers)
        # this will be enabled once results are
        # available
        self._update_labels_button = QPushButton("UpdateLabels")
        self._update_labels_button.setEnabled(False)

        # add all the widgets to the form widget
        form.addRow("Input Image", self._input_image_combo_box)
        form.addRow("Select Model", self._model_download_widget)
        form.addRow("Normalize Image", self._normalize_img_cb)
        form.addRow("Percentile Low", self._low_quantile_slider)
        form.addRow("Percentile High", self._high_quantile_slider)
        form.addRow("Invert Image", self._invert_img_cb)
        form.addRow("Prob Threshold", self._prob_thresh_slider)
        form.addRow("NMS threshold", self._nms_thresh_slider)
        form.addRow("On Visible Only", self._run_on_visible_only_cb)
        form.addRow("#tiles-x", self._n_tiles_x)
        form.addRow("#tiles-y", self._n_tiles_y)
        form.addRow("Edge Color", self._edge_color_sel)
        form.addRow("Face Color", self._face_color_sel)
        form.addRow("Run", self._run_button)
        form.addRow("Progress", self._progress_widget)
        form.addRow("Save", self._save_button)
        form.addRow("Edit", self._edit_button)
        form.addRow("Update Labels", self._update_labels_button)

    def _connect_events(self):
        """connect the qt events
        (ie connect what happens when buttons etc are pressed)
        """

        # trigger the start of the computation
        self._run_button.clicked.connect(self._on_run)

        # when a new color is selected
        self._edge_color_sel.colorChanged.connect(self._on_edge_color_changed)
        self._face_color_sel.colorChanged.connect(self._on_face_color_changed)

        # when a layer is removed from layerlist by a user
        # (the thing on the left in napari)
        def on_layer_removed(event):
            layer = event.value
            if layer == self.interpolated_layer or layer == self.ctrl_layer:
                self._update_labels_button.setEnabled(False)
            elif layer == self.labels_layer:
                self.labels_layer = None
                self._update_labels_button.setEnabled(False)

        self.viewer.layers.events.removed.connect(on_layer_removed)

        # trigger to create/update the splineit layers
        self._edit_button.clicked.connect(self._on_edit_button)

        # when the model-download widget starts to
        # download something the model is *NOT* availalbe
        # until the donwload is finihed.
        # We need do disable run button when the
        # model is not availalbe / and activate
        # the button later
        def model_availablity_changed(is_available):
            if is_available:
                self._run_button.setEnabled(True)
            else:
                self._run_button.setEnabled(False)

        self._model_download_widget.model_availablity_changed.connect(
            model_availablity_changed
        )

        # the model download widget fires an progress event
        # st we can rotate the logo widget.
        # the logo widget accepts values from 0 to 100
        # to make it easy to use a progress spinner
        def on_progress(p):
            self._logo_widget.setValue(p)

        self._model_download_widget.progress.connect(on_progress)

        # save the results
        self._save_button.clicked.connect(self._on_save)

        # when users edit the splines in the splineit layer,
        # one can update the pixel layer to follow the splines
        def on_update_labels():
            logger.info("update labels")
            if (
                self.interpolated_layer is not None
                and self.labels_layer is not None
            ):
                input_data_shape = self._get_input_layer().data.shape[0:2]
                # we use naparis function to convert the splines to labels
                labels = self.interpolated_layer.to_labels(
                    labels_shape=input_data_shape
                )
                self.labels_layer.data = labels

        self._update_labels_button.clicked.connect(on_update_labels)

    def _on_save(self):
        """this is triggered when the save button is pressed.
        This will open a file dialog. This filedialog will ask
        the user specify a filename.
        The extension ".splineit" (the one splineit accepts)
        is added by default
        """
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.AnyFile)
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        dlg.setDefaultSuffix("splineit")
        dlg.setNameFilters(["SPLINEIT (*.splineit)"])
        if dlg.exec_():
            filename = str(dlg.selectedFiles()[0])
            filename_json = Path(filename)
            filename_png = Path(f"{filename.removesuffix('.splineit')}.png")

            # if there is an up to date ctrl-layer we
            # need to take the results from there since the user might
            # have changed some splines (ie erased some object
            # or changed controll points etc)
            if self._ctrl_layer_is_up_to_date and self.ctrl_layer is not None:

                # use splineits function to save the results
                write_splineit(
                    path=dlg.selectedFiles()[0],
                    data=self.ctrl_layer.data,
                    interpolator=self.ctrl_layer.interpolator,
                    z_index=self.ctrl_layer.z_index,
                    edge_color=self.interpolated_layer.edge_color,
                    face_color=self.interpolated_layer.face_color,
                    edge_width=self.interpolated_layer.edge_width,
                    opacity=self.interpolated_layer.opacity,
                )

                # we use naparis function to convert the splines to labels
                labels = self.interpolated_layer.to_labels(
                    labels_shape=self._last_results[0].shape
                )
                data_uint16 = labels.astype(np.uint16)
                skimage_io.imsave(
                    filename_png, data_uint16, check_contrast=False
                )

            else:
                # if there is no ctrl-layer we take the last results and
                # save them
                n_polygons = len(self._last_results[1])
                edge_color = [float(c) for c in self._edge_color_sel.asArray()]
                face_color = [float(c) for c in self._face_color_sel.asArray()]
                edge_color = [edge_color] * n_polygons
                face_color = [face_color] * n_polygons

                write_splineit(
                    path=filename_json,
                    interpolator=self._interpolator_factory(),
                    data=self._last_results[1],
                    z_index=range(n_polygons),
                    edge_color=edge_color,
                    face_color=face_color,
                )

                # convert to uint16 st. we can save labels
                # which are bigger that 255 in a png
                data_uint16 = self._last_results[0].astype(np.uint16)
                # save the image (we need to disable check_contrast,
                # otherwise we get some false postive warnings)
                skimage_io.imsave(
                    filename_png, data_uint16, check_contrast=False
                )

    def _on_edge_color_changed(self, color):
        """called when the user selects a new edge color.

        This will change the edge color of the interpolated splines

        Args:
            color: the edge color as QColor
        """
        if self.interpolated_layer is not None:
            arr = self._edge_color_sel.asArray()
            self.interpolated_layer.edge_color = arr
            self.interpolated_layer.current_edge_color = arr

    def _on_face_color_changed(self, color):
        """called when the user selects a new face color.

        This will change the face color of the interpolated splines

        Args:
            color: the face color as QColor
        """
        if self.interpolated_layer is not None:
            arr = self._face_color_sel.asArray()
            self.interpolated_layer.face_color = arr
            self.interpolated_layer.current_face_color = arr

    def _get_visible_slicing(self):
        """get the visible part of the input image as slicing.
            This can be used to get the
            visible_data = data[self._get_visible_slicing()]

        Returns:
            tuple: Description
        """
        input_layer = self._get_input_layer()
        slicing = tuple(slice(i[0], i[1]) for i in input_layer.corner_pixels.T)
        return slicing

    def _interpolator_factory(self):
        """create a interpolator which is used in the splineit layer"""
        return splineit_interpolator_factory(name="UhlmannSplines")

    def _on_worker_started(self):
        """this is called once the worker-thread which runs splinedist
        is started.
        We prepare the splineit layers while the thread is
        running.
        """
        self._progress_widget.setProgress("prepare", 25)
        if self.interpolated_layer is None:
            self._create_empty_result_layers()

    def _on_worker_finished(self):
        """this is called when the worker thread is finished.

        We can now:

            * enable the run button again to trigger a fresh run
            * enable the edit and save button since we have results
            * enable the model download widget again
            (we disabled this since we do not want models
            to be changed while the worker is running)

        """
        self._run_button.setEnabled(True)
        self._edit_button.setEnabled(True)
        self._update_labels_button.setEnabled(False)

        self._save_button.setEnabled(True)
        self._model_download_widget.setEnabled(True)

        if self.ctrl_layer in self.viewer.layers:
            self.viewer.layers.remove(self.ctrl_layer)

        if self.interpolated_layer in self.viewer.layers:
            self.viewer.layers.remove(self.interpolated_layer)

    def _create_empty_result_layers(self):
        """create the two splineit layers:
        * the interpolated_layer is shows the interpolated splines
        * the ctrl_layers shows the controll points
        """
        interpolated_layer, ctrl_layer = splineit_layer_factory(
            viewer=self.viewer, interpolator=self._interpolator_factory()
        )
        self.interpolated_layer = interpolated_layer
        self.ctrl_layer = ctrl_layer
        self.labels_layer = None

    def _on_edit_button(self):
        """this is triggered when the edit button is pressed.

            This will take the last results and build
            the splineit representation from it


        Raises:
            RuntimeError: when there are no results a runtime error is rased.
                This should never happen by desing.
        """

        # mark the results shown as splineit layer as up-to-date

        if self.ctrl_layer not in self.viewer.layers:
            self.viewer.add_layer(self.ctrl_layer)

        if self.interpolated_layer not in self.viewer.layers:
            self.viewer.add_layer(self.interpolated_layer)

        self._ctrl_layer_is_up_to_date = True

        # make sure the interpolated layers are "above" the
        # labels layer in layerlist of napari
        i_labels = self.viewer.layers.index(self.labels_layer)
        i_ctrl = self.viewer.layers.index(self.ctrl_layer)
        i_interpolated = self.viewer.layers.index(self.interpolated_layer)
        if i_labels > i_interpolated:
            # change the layer order
            self.viewer.layers.move_multiple(
                sources=[i_labels, i_interpolated],
                dest_index=i_ctrl,
            )

        if self._last_results is not None:
            # since the user has the most recent
            # results we can disable the edit button
            # (a new run of the splinedist will re-enable
            # this button)
            self._edit_button.setEnabled(False)
            self._update_labels_button.setEnabled(True)
            labels, coords_list = self._last_results

            # this will update the splines in the splineit
            # layers.
            self.ctrl_layer.set_polygons(
                data=coords_list,
                edge_color=self._edge_color_sel.asArray(),
                face_color=self._face_color_sel.asArray(),
                current_edge_color=self._edge_color_sel.asArray(),
                current_face_color=self._face_color_sel.asArray(),
            )
            self.ctrl_layer.z_index = list(range(len(coords_list)))

        else:
            # this should actually never happend
            raise RuntimeError("internal errro: has no results to edit")

        # male sure that the ctrl layer is the active layer
        self.viewer.layers.selection.active = self.ctrl_layer
        # this makes sure that we are in the "edit" mode
        # st. we can edit the control points
        self.ctrl_layer.mode = Mode.DIRECT

    def _on_worker_yielded_results(self, results):
        """this is called when the worker thread which runs
            splinedist yielded results (ie finished
            without error)

        Args:
            results (tuple): a tuple with labels / coordinate-list
        """
        # store results
        self._last_results = results

        labels, coords_list = results

        # get the max label
        max_label = labels.max()

        # check if the colormap is large enough
        if max_label >= self._colormap_capacity:
            # increase the color map size generousely
            self._colormap_capacity = int(1.5 * max_label + 0.5)
            self._colormap = make_colormap(self._colormap_capacity)

        # create or update the labels layer
        # the labels layer show the pixelized objects
        if self.labels_layer is None:
            self.labels_layer = ImageLayer(
                data=labels, colormap=self._colormap
            )
            self.viewer.add_layer(self.labels_layer)
        else:
            self.labels_layer.data = labels

    def _on_worker_progress(self, name, progress):
        """this is triggered from within the worker
            to report progress of various things.
            The progress is shown in the progress-widget

        Args:
            name (str): name of thing for which we want to report progress
            progress (int/float): progress in range [0,100]
        """
        self._progress_widget.setProgress(name, progress)

    def _on_worker_errored(self, e):
        """this is called whenever the worker which runs
        splinedist raises an expection.
        We call `_on_worker_finished` to do
        the same cleanup as for an non-errored run
        and raise the error after that.
        """
        self._on_worker_finished()
        raise RuntimeError(e)

    def _get_input_layer(self):
        """Get the layer which is used as input
           for splinedist

        Returns:
            layer: the layer which contains the data
                which will be used as input for
                splinedist

        Raises:
            NoInputImageException: raised when there are no
                input images
        """
        if self._input_image_combo_box.count() == 0:
            raise NoInputImageException()
        return self._input_image_combo_box.currentLayer()

    def _build_parameters(self):
        """build all the parameters passed to splinedist as single dict
        Returns:
            dict: dict with all the parameters for splinedist
        """
        n_tiles_x = self._n_tiles_x.value()
        n_tiles_y = self._n_tiles_x.value()
        n_tiles = (n_tiles_x, n_tiles_y)
        if n_tiles_x == 1 and n_tiles_y == 1:
            n_tiles = None

        return dict(
            normalize_image=self._normalize_img_cb.checkState(),
            percentile_low=self._low_quantile_slider.value() * 100.0,
            percentile_high=self._high_quantile_slider.value() * 100.0,
            prob_thresh=self._prob_thresh_slider.value(),
            nms_thresh=self._nms_thresh_slider.value(),
            invert_image=self._invert_img_cb.checkState(),
            n_tiles=n_tiles,
        )

    def _on_run(self):
        """this is triggered when a user pressed run.
        This will start a worker-thread which
        does run splinedist (ie the heavy lifting
        is done in this worker)
        """

        # we mark the splineit layers as utdated
        self._ctrl_layer_is_up_to_date = False

        # fetch the input data
        input_layer = self._get_input_layer()
        logger.info(f"run on layer {input_layer.name}")

        # show some info on the progress bar
        self._progress_widget.setProgress("prepare", 0)

        # disable the run/edut/model-dl/update-labels while we are running
        self._run_button.setEnabled(False)
        self._edit_button.setEnabled(False)
        self._model_download_widget.setEnabled(False)
        self._update_labels_button.setEnabled(False)

        # should we run only on the visible part of the input?
        slicing = None
        if self._run_on_visible_only_cb.checkState():
            # what part of the input image is currently visible?
            slicing = self._get_visible_slicing()

        # helper f
        def transform_results(labels, details, slicing, shape):
            """change / transform the results st we can
                display the resutls

            Args:
                labels (np.array): the result labels
                details (dict): dict with coordinates
                slicing (Tuple[slice,slice]|None): Description
                shape (Tuple[int,int]): *full* shape of input image!
                  (this is not the shape of the visible part, but
                  the full shape, since we "paste" the visible
                  part in the full_labels array )


            Returns:
                Tuple(np.array, List): labels and coordinates
            """

            # if the slicing is not none we need to compute an
            # offset we need to add to each coordinate of the slines.
            # Also we paste the "sub-labels" (ie the visible part)
            # in the "full-labels"
            if slicing is not None:
                # get the offset
                offset = np.array([slicing[0].start, slicing[1].start])
                # the empty "full-labels"
                full_labels = np.zeros(shape, dtype=labels.dtype)
                # paste the sub-lables
                full_labels[slicing] = labels
                labels = full_labels
            else:
                # when we predic on the full image (ie *not* just the
                # visible part) we can set the offset to zero
                offset = np.array([0, 0])

            # the result coordinates as given by splinedist
            coords = details["coord"]
            # the results as we need them for splineit
            coords_list = []
            # iteraten over all polygons / objects
            for i in range(coords.shape[0]):
                # convert the "coefs" (this is what splinedist returns
                # to actual controll points on the spline)
                coords_list.append(knots_from_coefs(coords[i, ...].T) + offset)
            return labels, coords_list

        # use naparis thread_worker decorator
        # to run this in a worker thread.
        # We use a custom worker_class st. we
        # can fire custom events
        # (ie  self.worker.extra_signals.progress)
        @thread_worker(worker_class=GeneratorWorker)
        def work_function(model_meta, data, slicing, **kwargs):
            def progress_callback(name, progress):
                self.worker.extra_signals.progress.emit(name, int(progress))

            # spatial shape (ignoring potential color channels)
            shape = data.shape[0:2]

            # when prediciting on the visible part only
            if slicing is not None:
                # fetch visible part of data
                data = input_layer.data[slicing]

            # run the prediction
            labels, details = predict(
                data,
                progress_callback=progress_callback,  # to update the
                # progress bar
                model_meta=model_meta,  # model meta has the info
                # how many controll points
                # are used
                **kwargs,
            )

            # convert the "raw" results st. we
            # can use them in the splineit layers
            labels, coords_list = transform_results(
                labels, details, slicing, shape
            )

            # since we use a generator worker we
            # yield the results
            yield labels, coords_list

            return

        # construct the worker (this does **not** start the thread
        # right away)
        self.worker = work_function(
            # model meta has the info how
            # many controll point are used
            model_meta=self._model_download_widget.getModelMeta(),
            # the input image
            data=input_layer.data,
            # the slicing (can be none if we predict on whole image)
            slicing=slicing,
            # the folder where the model is located
            model_path=self._model_download_widget._current_model_path(),
            # the parameters for normalization etc
            **self._build_parameters(),
        )
        # Connect events:
        # fired once the worker is started
        self.worker.started.connect(self._on_worker_started)
        # fired when the worker finishes **without** errors
        self.worker.finished.connect(self._on_worker_finished)
        # fired when the worker finishes **with** an error
        self.worker.errored.connect(self._on_worker_errored)
        # fired when the worker yields results
        self.worker.yielded.connect(self._on_worker_yielded_results)
        # fired when progress is reported from the worker
        self.worker.extra_signals.progress.connect(self._on_worker_progress)

        # this starts the worker and therefore splinedist:
        # Let the show begin!
        self.worker.start()
