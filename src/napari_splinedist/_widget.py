"""
TODOS:
    * splineit layers cannot be reused after user deleted them
    * add button to override/not-override exisiting layers
    * add advanced config?
    * implement actual model loading
    * implement configurage sub-data prediction
    * pass more parameters

"""
import os
from pathlib import Path
from typing import TYPE_CHECKING

import numpy
from napari_splineit.interpolation import (
    interpolator_factory as splineit_interpolator_factory,
)
from napari_splineit.layer.layer_factory import (
    layer_factory as splineit_layer_factory,
)
from napari_splineit.widgets.double_spin_slider import DoubleSpinSlider
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from ._logging import logger
from .exceptions import NoInputImageException, NoLoadedModelException
from .widgets.color_picker_push_button import ColorPicklerPushButton
from .widgets.image_layer_combo_box import ImageLayerComboBox
from .widgets.progress_widget import ProgressWidget
from .worker import Worker

if TYPE_CHECKING:
    pass


def shorten_path(file_path, length):
    """Split the path into separate parts, select the last
    'length' elements and join them again"""
    return str(Path(*Path(file_path).parts[-length:]))


def bar():
    f = QFrame()
    f.setStyleSheet("background-color: #c0c0c0;")
    f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)
    f.setFrameShadow(QFrame.Sunken)
    f.setLineWidth(1)
    f.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return f


class SplineDistWidget(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()

        self.viewer = napari_viewer

        self._user_model_path = None
        edge_color = QColor(255, 0, 0, 255)
        face_color = QColor(85, 170, 255, 100)

        # todo
        self._find_shippd_models()

        self._init_ui(edge_color=edge_color, face_color=face_color)
        self._connect_events()

        self.worker = None

        self.interpolated_layer = None
        self.ctrl_layer = None

    def _find_shippd_models(self):
        this_dir = Path(os.path.dirname(os.path.realpath(__file__)))
        shipped_models_dir = this_dir / "model" / "shipped_models"

        self._shipped_models = []
        for path in shipped_models_dir.iterdir():
            if path.is_dir():
                self._shipped_models.append(path)

    def _init_ui(self, edge_color, face_color):

        form = QFormLayout()
        self.setLayout(form)
        # fmt: off
        self._input_image_combo_box = ImageLayerComboBox(self.viewer)
        self._use_shipped_cb = QCheckBox()
        self._use_loaded_cb = QCheckBox()
        self.group = QButtonGroup(self)
        self.group.addButton(self._use_shipped_cb)
        self.group.addButton(self._use_loaded_cb)
        self._shipped_combo_box = QComboBox()
        for sm in self._shipped_models:
            self._shipped_combo_box.addItem(sm.name)
        self._select_model_button = QPushButton("Select model")
        self._select_model_button.setEnabled(False)
        self._model_path_label = QLabel("None")
        self._normalize_img_cb = QCheckBox()
        self._normalize_img_cb.setChecked(True)
        self._low_quantile_slider = DoubleSpinSlider([0, 1], 0.01)
        self._high_quantile_slider = DoubleSpinSlider([0, 100], 0.998)

        self._prob_thresh_slider = DoubleSpinSlider([0, 1.0], 0.5)
        self._nms_thresh_slider =  DoubleSpinSlider([0, 1.0], 0.5)

        self._run_on_visible_only_cb = QCheckBox()
        self._run_on_visible_only_cb.setChecked(False)

        self._edge_color_sel = ColorPicklerPushButton(color=edge_color, with_alpha=True, tracking=True)
        self._face_color_sel = ColorPicklerPushButton(color=face_color, with_alpha=True, tracking=True)
        self._run_button = QPushButton("run")
        self._progress_widget = ProgressWidget(self)
        self._use_shipped_cb.setChecked(True)
        # fmt: on

        form.addRow("Input Image", self._input_image_combo_box)
        form.addRow("Use Shipped Model", self._use_shipped_cb)
        form.addRow("Model", self._shipped_combo_box)
        form.addRow("Use Loaded Model", self._use_loaded_cb)
        form.addRow("Select Model", self._select_model_button)
        form.addRow("Selected Model", self._model_path_label)
        form.addRow("Normalize Image", self._normalize_img_cb)
        form.addRow("Percentile Low", self._low_quantile_slider)
        form.addRow("Percentile High", self._high_quantile_slider)

        form.addRow("Prob Threshold", self._prob_thresh_slider)
        form.addRow("NMS threshold", self._nms_thresh_slider)
        form.addRow("On Visible Only", self._run_on_visible_only_cb)

        form.addRow("Edge Color", self._edge_color_sel)
        form.addRow("Face Color", self._face_color_sel)
        form.addRow("Run", self._run_button)
        form.addRow("Progress", self._progress_widget)

    def _connect_events(self):

        self._select_model_button.clicked.connect(
            self._on_selected_model_folder
        )

        self._run_button.clicked.connect(self._on_run)

        def on_click(btn):
            if self._use_shipped_cb.isChecked():
                self._select_model_button.setEnabled(False)
                self._shipped_combo_box.setEnabled(True)
            else:
                self._select_model_button.setEnabled(True)
                self._shipped_combo_box.setEnabled(False)

        self.group.buttonClicked.connect(on_click)

        self._edge_color_sel.colorChanged.connect(self._on_edge_color_changed)
        self._face_color_sel.colorChanged.connect(self._on_face_color_changed)

    def _on_edge_color_changed(self, color):
        if self.interpolated_layer is not None:
            self.interpolated_layer.edge_color = self._edge_color_sel.asArray()

    def _on_face_color_changed(self, color):
        if self.interpolated_layer is not None:
            self.interpolated_layer.face_color = self._face_color_sel.asArray()

    def _verify_model_path(self, path):
        return

    def _get_visible_slicing(self):
        input_layer = self._get_input_layer()
        crop = tuple(slice(i[0], i[1]) for i in input_layer.corner_pixels.T)
        return crop

    def _on_selected_model_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select a splinedist model folder"
        )
        self._verify_model_path(path)
        self._user_model_path = Path(path)

        self._model_path_label.setText(shorten_path(path, 2))

    def _get_model_path(self):
        if self._use_shipped_cb.checkState():
            return self._shipped_models[self._shipped_combo_box.currentIndex()]
        else:
            if self._user_model_path is None:
                raise NoLoadedModelException()
            return self._user_model_path

    def _on_worker_started(self):
        print("_on_worker_started")
        self._progress_widget.setProgress("prepare", 25)

    def _on_worker_finished(self):
        self._run_button.setEnabled(True)

    def _create_result_layers(self, coords_list):
        interpolator = splineit_interpolator_factory(name="UhlmannSplines")
        interpolated_layer, ctrl_layer = splineit_layer_factory(
            viewer=self.viewer,
            interpolator=interpolator,
            data=coords_list,
            edge_color=self._edge_color_sel.asArray(),
            face_color=self._face_color_sel.asArray(),
        )
        self.interpolated_layer = interpolated_layer
        self.ctrl_layer = ctrl_layer

    def _update_result_layers(self, coords_list):
        # remove existing shapes
        self.ctrl_layer.remove_all()
        # self.ctrl_layer.selected_data = set(range(self.ctrl_layer.nshapes))
        # self.ctrl_layer.remove_selected()
        self.ctrl_layer.add_polygons(data=coords_list)
        self.interpolated_layer.edge_color = self._edge_color_sel.asArray()
        self.interpolated_layer.face_color = self._face_color_sel.asArray()

    def _transform_results(self, results):

        labels, details, slicing = results
        if slicing is not None:
            offset = numpy.array([slicing[0].start, slicing[1].start])
        else:
            offset = numpy.array([0, 0])
        coords = details["coord"]
        coords_list = []
        for i in range(coords.shape[0]):
            coords_list.append(coords[i, ...].T + offset)
        return coords_list

    def _on_worker_resulted(self, results):

        self._progress_widget.setProgress("make layers", 0)

        # convert the results st. napari-splineit
        # understands them
        coords_list = self._transform_results(results)

        # create layers or update existing layers
        if self.interpolated_layer is None:
            self._create_result_layers(coords_list)
        else:
            self._update_result_layers(coords_list)

        # some progress reporting
        self._progress_widget.setProgress("done!", 100)

    def _on_worker_progress(self, name, progress):

        self._progress_widget.setProgress(name, progress)

    def _on_worker_errored(self, e):
        self._progress_widget.setProgress("ERRORED!", 100)
        raise RuntimeError(e)

    def _get_input_layer(self):
        if self._input_image_combo_box.count() == 0:
            raise NoInputImageException()
        return self._input_image_combo_box.currentLayer()

    def _build_parameters(self):
        return dict(
            normalize_image=self._normalize_img_cb.checkState(),
            percentile_low=self._low_quantile_slider.value() * 100.0,
            percentile_high=self._high_quantile_slider.value() * 100.0,
            prob_thresh=self._prob_thresh_slider.value(),
            nms_thresh=self._nms_thresh_slider.value(),
        )

    def _on_run(self):

        input_layer = self._get_input_layer()
        logger.info(f"run on layer {input_layer.name}")

        self._progress_widget.setProgress("prepare", 0)

        self._run_button.setEnabled(False)

        if self._run_on_visible_only_cb.checkState():

            # what part of the input image is currently visible?
            slicing = self._get_visible_slicing()
            # crop the visible part
            data = input_layer.data[slicing]
        else:
            slicing = None
            data = input_layer.data

        # pass data and parameter to fresh worker
        self.worker = Worker(
            data=data,
            slicing=slicing,
            model_path=self._get_model_path(),
            **self._build_parameters(),
        )

        # connect all the signals for communication between
        # worker thread and this widget:

        # when worker starts..nothing important to do
        self.worker.started.connect(self._on_worker_started)

        # when the worker produced results without errors
        self.worker.resulted.connect(self._on_worker_resulted)

        # called when exceptions/errors happen in the worker
        self.worker.errored.connect(self._on_worker_errored)

        # called when worker is done. this is called no matter
        # if errors happend or not
        self.worker.finished.connect(self._on_worker_finished)

        # this can be called from the worker to report progress
        self.worker.progress.connect(self._on_worker_progress)

        # start the worker thread
        self.worker.start()

        # report some progress
        self._progress_widget.setProgress("prepare", 50)
