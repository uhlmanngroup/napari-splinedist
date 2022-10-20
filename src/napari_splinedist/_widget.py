"""
TODOS:
    * splineit layers cannot be reused after user deleted them
    * add button to override/not-override exisiting layers
    * add advanced config?
    * implement actual model loading
    * implement configurage sub-data prediction
    * pass more parameters

"""

import numpy as np
from napari.layers import Image as ImageLayer
from napari.layers.shapes.shapes import Mode
from napari.qt.threading import GeneratorWorker as NapariGeneratorWorker
from napari.qt.threading import thread_worker
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
    QFormLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ._logging import logger
from .config.config import APPDIR, CONFIG
from .exceptions import NoInputImageException
from .model.predict import predict
from .utils.colormap import make_labels_colormap
from .widgets.color_picker_push_button import ColorPicklerPushButton
from .widgets.image_layer_combo_box import ImageLayerComboBox
from .widgets.model_download_widget import ModelDownloadWidget
from .widgets.progress_widget import ProgressWidget
from .widgets.rotating_logo_widget import RotatingLogoWidget


class GeneratorWorker(NapariGeneratorWorker):
    class ExtraSignals(QObject):
        progress = Signal(str, int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra_signals = GeneratorWorker.ExtraSignals()


class SplineDistWidget(QWidget):
    chunked_results_forwarded = Signal(object, int, int)
    # worker_continue = Signal(object)

    def __init__(self, napari_viewer):
        super().__init__()

        self.viewer = napari_viewer

        self._user_model_path = None
        edge_color = QColor(255, 0, 0, 255)
        face_color = QColor(85, 170, 255, 100)

        self._init_ui(edge_color=edge_color, face_color=face_color)
        self._connect_events()

        self._model_download_combo_box.setModelsMeta(CONFIG.models)

        self.worker = None
        self.thread = None

        self.interpolated_layer = None
        self.ctrl_layer = None
        self.labels_layer = None

        # last results
        self._last_results = None

    def _init_ui(self, edge_color, face_color):

        # layouts
        box = QVBoxLayout()
        grid = QGridLayout()
        form = QFormLayout()
        self.setLayout(box)

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
        self._header_label.setOpenExternalLinks(True)
        self._logo_widget = RotatingLogoWidget()

        grid.addWidget(self._logo_widget, 0, 0)
        grid.addWidget(self._header_label, 0, 1)
        # grid.addWidget(self._logo_bar_right,0,2)

        self._input_image_combo_box = ImageLayerComboBox(self.viewer)
        self._model_download_combo_box = ModelDownloadWidget(APPDIR)
        self._select_model_button = QPushButton("Select model")
        self._select_model_button.setEnabled(False)
        self._normalize_img_cb = QCheckBox()
        self._normalize_img_cb.setChecked(True)
        self._low_quantile_slider = DoubleSpinSlider([0, 1], 0.01)
        self._high_quantile_slider = DoubleSpinSlider([0, 100], 0.998)
        self._invert_img_cb = QCheckBox()
        self._invert_img_cb.setChecked(False)
        self._prob_thresh_slider = DoubleSpinSlider([0, 1.0], 0.5)
        self._nms_thresh_slider = DoubleSpinSlider([0, 1.0], 0.5)
        self._run_on_visible_only_cb = QCheckBox()
        self._run_on_visible_only_cb.setChecked(False)

        self._n_tiles_x = SpinSlider([1, 10], 1)
        self._n_tiles_y = SpinSlider([1, 10], 1)

        self._edge_color_sel = ColorPicklerPushButton(
            color=edge_color, with_alpha=True, tracking=True
        )
        self._face_color_sel = ColorPicklerPushButton(
            color=face_color, with_alpha=True, tracking=True
        )
        self._run_button = QPushButton("run")
        self._progress_widget = ProgressWidget(self)

        self._edit_button = QPushButton("Edit")

        box.addLayout(grid)
        box.addLayout(form)

        form.addRow("Input Image", self._input_image_combo_box)
        form.addRow("Select Model", self._model_download_combo_box)
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

        form.addRow("Edit", self._edit_button)
        self._edit_button.setEnabled(False)

    def _connect_events(self):

        self._run_button.clicked.connect(self._on_run)

        self._edge_color_sel.colorChanged.connect(self._on_edge_color_changed)
        self._face_color_sel.colorChanged.connect(self._on_face_color_changed)

        def on_layer_removed(event):
            layer = event.value
            if layer == self.interpolated_layer or layer == self.ctrl_layer:
                self.interpolated_layer = None
                self.ctrl_layer = None
            if layer == self.labels_layer:
                self.labels_layer = None

        self.viewer.layers.events.removed.connect(on_layer_removed)

        self._edit_button.clicked.connect(self._on_edit_button)

        def model_availablity_changed(is_available):
            if is_available:
                self._run_button.setEnabled(True)
            else:
                self._run_button.setEnabled(False)

        self._model_download_combo_box.model_availablity_changed.connect(
            model_availablity_changed
        )

        def on_progress(p):
            self._logo_widget.setValue(p)
            # self._logo_bar_right.setValue(p)

        self._model_download_combo_box.progress.connect(on_progress)

    def _on_edge_color_changed(self, color):
        if self.interpolated_layer is not None:
            arr = self._edge_color_sel.asArray()
            self.interpolated_layer.edge_color = arr
            self.interpolated_layer.current_edge_color = arr

    def _on_face_color_changed(self, color):
        if self.interpolated_layer is not None:
            arr = self._face_color_sel.asArray()
            self.interpolated_layer.face_color = arr
            self.interpolated_layer.current_face_color = arr

    def _verify_model_path(self, path):
        return

    def _get_visible_slicing(self):
        input_layer = self._get_input_layer()
        crop = tuple(slice(i[0], i[1]) for i in input_layer.corner_pixels.T)
        return crop

    def _get_model_path(self):
        return self._model_download_combo_box._current_model_path()

    def _on_worker_started(self):
        self._progress_widget.setProgress("prepare", 25)

        # create layers or update existing layers
        if self.interpolated_layer is None:
            self._create_empty_result_layers()

    def _on_worker_finished(self):
        self._run_button.setEnabled(True)
        self._edit_button.setEnabled(True)
        self._model_download_combo_box.setEnabled(True)

    def _create_empty_result_layers(self):
        interpolator = splineit_interpolator_factory(name="UhlmannSplines")
        interpolated_layer, ctrl_layer = splineit_layer_factory(
            viewer=self.viewer, interpolator=interpolator
        )
        self.interpolated_layer = interpolated_layer
        self.ctrl_layer = ctrl_layer
        self.labels_layer = None

    def _on_edit_button(self):

        # make sure the interpolated layers are "above" the
        # labels layer
        i_labels = self.viewer.layers.index(self.labels_layer)
        i_ctrl = self.viewer.layers.index(self.ctrl_layer)
        i_interpolated = self.viewer.layers.index(self.interpolated_layer)
        if i_labels > i_interpolated:
            self.viewer.layers.move_multiple(
                sources=[i_labels, i_interpolated],
                dest_index=i_ctrl,
            )

        i_labels = self.viewer.layers.index(self.labels_layer)
        i_ctrl = self.viewer.layers.index(self.ctrl_layer)
        i_interpolated = self.viewer.layers.index(self.interpolated_layer)

        if self._last_results is not None:
            self._edit_button.setEnabled(False)
            labels, coords_list = self._last_results

            self.ctrl_layer.set_polygons(
                data=coords_list,
                edge_color=self._edge_color_sel.asArray(),
                face_color=self._face_color_sel.asArray(),
                current_edge_color=self._edge_color_sel.asArray(),
                current_face_color=self._face_color_sel.asArray(),
            )

        else:
            raise RuntimeError("internal errro: has no results to edit")

        self.viewer.layers.selection.active = self.ctrl_layer
        self.ctrl_layer.mode = Mode.DIRECT

    def _on_worker_yielded_results(self, results):

        # store results
        self._last_results = results

        labels, coords_list = results

        if self.labels_layer is None:
            self.labels_layer = ImageLayer(
                data=labels,
                colormap=make_labels_colormap(labels),
            )
            self.viewer.add_layer(self.labels_layer)
        else:
            self.labels_layer.data = labels

    def _on_worker_progress(self, name, progress):
        self._progress_widget.setProgress(name, progress)

    def _on_worker_errored(self, e):
        self._on_worker_finished()
        raise RuntimeError(e)

    def _get_input_layer(self):
        if self._input_image_combo_box.count() == 0:
            raise NoInputImageException()
        return self._input_image_combo_box.currentLayer()

    def _build_parameters(self):
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

        input_layer = self._get_input_layer()
        logger.info(f"run on layer {input_layer.name}")

        self._progress_widget.setProgress("prepare", 0)

        self._run_button.setEnabled(False)
        self._edit_button.setEnabled(False)
        self._model_download_combo_box.setEnabled(False)

        slicing = None
        if self._run_on_visible_only_cb.checkState():
            # what part of the input image is currently visible?
            slicing = self._get_visible_slicing()

        def transform_results(labels, details, slicing, shape):
            if slicing is not None:
                offset = np.array([slicing[0].start, slicing[1].start])
                full_labels = np.zeros(shape, dtype=labels.dtype)
                full_labels[slicing] = labels
                labels = full_labels
            else:
                offset = np.array([0, 0])

            coords = details["coord"]
            coords_list = []
            for i in range(coords.shape[0]):
                coords_list.append(knots_from_coefs(coords[i, ...].T) + offset)
            return labels, coords_list

        @thread_worker(worker_class=GeneratorWorker)
        def work_function(model_meta, data, slicing, **kwargs):
            def progress_callback(name, progress):
                self.worker.extra_signals.progress.emit(name, int(progress))

            # spatial shape (ignoring potential color channels)
            shape = data.shape[0:2]
            if slicing is not None:
                data = input_layer.data[slicing]

            labels, details = predict(
                data,
                progress_callback=progress_callback,
                model_meta=model_meta,
                **kwargs,
            )
            labels, coords_list = transform_results(
                labels, details, slicing, shape
            )

            yield labels, coords_list

            return

        self.worker = work_function(
            model_meta=self._model_download_combo_box.getModelMeta(),
            data=input_layer.data,
            slicing=slicing,
            model_path=self._get_model_path(),
            **self._build_parameters(),
        )

        self.worker.started.connect(self._on_worker_started)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.errored.connect(self._on_worker_errored)
        self.worker.yielded.connect(self._on_worker_yielded_results)
        self.worker.extra_signals.progress.connect(self._on_worker_progress)
        self.worker.start()
