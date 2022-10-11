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

import numpy as np
from napari.qt.threading import thread_worker
from napari_splineit.interpolation import (
    interpolator_factory as splineit_interpolator_factory,
)
from napari_splineit.layer.layer_factory import (
    layer_factory as splineit_layer_factory,
)
from napari_splineit.widgets.double_spin_slider import DoubleSpinSlider
from napari_splineit.widgets.spin_slider import SpinSlider
from qtpy.QtCore import Signal
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
from .model.predict import predict
from .widgets.color_picker_push_button import ColorPicklerPushButton
from .widgets.image_layer_combo_box import ImageLayerComboBox
from .widgets.progress_widget import ProgressWidget

# from qtpy.QtGui import QApplication
# from qtpy.QtCore import Signal


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
    chunked_results_forwarded = Signal(object, int, int)
    # worker_continue = Signal(object)

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
        self.thread = None

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
        self._invert_img_cb = QCheckBox()
        self._invert_img_cb.setChecked(False)
        self._prob_thresh_slider = DoubleSpinSlider([0, 1.0], 0.5)
        self._nms_thresh_slider =  DoubleSpinSlider([0, 1.0], 0.5)
        self._run_on_visible_only_cb = QCheckBox()
        self._run_on_visible_only_cb.setChecked(False)
        self._n_chunks_slider =  SpinSlider([1,20], 1)
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
        form.addRow("Invert Image", self._invert_img_cb)
        form.addRow("Prob Threshold", self._prob_thresh_slider)
        form.addRow("NMS threshold", self._nms_thresh_slider)
        form.addRow("On Visible Only", self._run_on_visible_only_cb)
        form.addRow("Add-Chunked", self._n_chunks_slider)
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

        def on_layer_removed(event):
            layer = event.value
            print("removing", layer, type(layer), event.value)
            if layer == self.interpolated_layer or layer == self.ctrl_layer:
                print("BINGO")
                self.interpolated_layer = None
                self.ctrl_layer = None

        self.viewer.layers.events.removed.connect(on_layer_removed)

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

        # create layers or update existing layers
        if self.interpolated_layer is None:
            self._create_empty_result_layers()

    def _on_worker_finished(self):
        self._run_button.setEnabled(True)

    def _create_result_layers(self, coords_list):
        data = np.array(coords_list)
        interpolator = splineit_interpolator_factory(name="UhlmannSplines")
        interpolated_layer, ctrl_layer = splineit_layer_factory(
            viewer=self.viewer,
            interpolator=interpolator,
            data=np.array(coords_list),
            edge_color=self._edge_color_sel.asArray(),
            face_color=self._face_color_sel.asArray(),
            current_edge_color=self._edge_color_sel.asArray(),
            current_face_color=self._face_color_sel.asArray(),
        )
        # for sd in np.array_split(data, 10):
        #     ctrl_layer.add(sd)

        self.interpolated_layer = interpolated_layer
        self.ctrl_layer = ctrl_layer

    def _create_empty_result_layers(self):
        interpolator = splineit_interpolator_factory(name="UhlmannSplines")
        interpolated_layer, ctrl_layer = splineit_layer_factory(
            viewer=self.viewer, interpolator=interpolator
        )
        self.interpolated_layer = interpolated_layer
        self.ctrl_layer = ctrl_layer

    def _remove_all_from_result_layer(self):
        self.ctrl_layer.remove_all()

    def _add_to_result_layers(self, data):

        self._progress_widget.setProgress("make layers", 0)
        self.ctrl_layer.set_polygons(
            data=data,
            edge_color=self._edge_color_sel.asArray(),
            face_color=self._face_color_sel.asArray(),
            current_edge_color=self._edge_color_sel.asArray(),
            current_face_color=self._face_color_sel.asArray(),
        )

    def _update_result_layers(self, coords_list):

        print(
            f"PRE UPDATE {len(self.interpolated_layer.face_color) = }  {len(self.interpolated_layer._data_view.shapes) = }"
        )
        # remove existing shapes
        self.ctrl_layer.remove_all()
        print(
            f"AFTR remove_all {len(self.interpolated_layer.face_color) = }  {len(self.interpolated_layer._data_view.shapes) = }"
        )
        self.ctrl_layer.add_polygons(data=coords_list)

        print(
            f"AFTR add_polygons {len(self.interpolated_layer.face_color) = }  {len(self.interpolated_layer._data_view.shapes) = }"
        )

        self.interpolated_layer.edge_color = self._edge_color_sel.asArray()
        self.interpolated_layer.face_color = self._face_color_sel.asArray()

        print(
            f"PRE POST_UPDATE {len(self.interpolated_layer.face_color) = }  {len(self.interpolated_layer._data_view.shapes) = }"
        )

    def _on_worker_progress(self, name, progress):
        # pass
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
            invert_image=self._invert_img_cb.checkState(),
            add_in_n_chunks=self._n_chunks_slider.value(),
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

        def transform_results(details, slicing):
            if slicing is not None:
                offset = np.array([slicing[0].start, slicing[1].start])
            else:
                offset = np.array([0, 0])
            coords = details["coord"]
            coords_list = []
            for i in range(coords.shape[0]):
                coords_list.append(coords[i, ...].T + offset)
            return coords_list

        def chunks(lst, n):
            for i in range(0, len(lst), n):
                yield lst[i : i + n]

        @thread_worker
        def work_function(data, slicing, add_in_n_chunks, **kwargs):

            labels, details = predict(data, **kwargs)
            coords_list = transform_results(details, slicing)

            yield coords_list

            return

        self.worker = work_function(
            data,
            slicing,
            model_path=self._get_model_path(),
            **self._build_parameters(),
        )

        self.worker.started.connect(self._on_worker_started)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.errored.connect(self._on_worker_errored)
        self.worker.yielded.connect(self._add_to_result_layers)

        self.worker.start()
