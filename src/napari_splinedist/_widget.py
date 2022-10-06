"""
This module is an example of a barebones QWidget plugin for napari

It implements the Widget specification.
see: https://napari.org/stable/plugins/guides.html?#widgets

Replace code below according to your needs.
"""
from pathlib import Path
from typing import TYPE_CHECKING

from napari_splineit.interpolation import (
    interpolator_factory as splineit_interpolator_factory,
)
from napari_splineit.layer.layer_factory import (
    layer_factory as splineit_layer_factory,
)
from napari_splineit.widgets.double_spin_slider import DoubleSpinSlider
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ._logging import logger
from .exceptions import NoInputImageException
from .widgets.image_layer_combo_box import ImageLayerComboBox
from .widgets.progress_widget import ProgressWidget
from .worker import Worker

if TYPE_CHECKING:
    pass


def shorten_path(file_path, length):
    """Split the path into separate parts, select the last
    'length' elements and join them again"""
    return str(Path(*Path(file_path).parts[-length:]))


class SplineDistWidget(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()

        self.viewer = napari_viewer

        self._model_path = None

        self._init_ui()
        self._connect_events()

        self.worker = None

        self.interpolated_layer = None
        self.ctrl_layer = None

    def _init_ui(self):

        box = QVBoxLayout()
        grid = QGridLayout()
        self.setLayout(box)
        box.addLayout(grid)
        box.addStretch(1)

        def add_labled_widget(text, widget, row):
            grid.addWidget(QLabel(text), row, 0)
            grid.addWidget(widget, row, 1)
            return widget

        row = 0

        def bar():
            f = QFrame()
            f.setStyleSheet("background-color: #c0c0c0;")
            f.setFrameShape(QFrame.HLine)
            f.setFixedHeight(1)
            f.setFrameShadow(QFrame.Sunken)
            f.setLineWidth(1)
            f.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            return f

        grid.addWidget(bar(), row, 0, 1, 2)
        row += 1

        self._input_image_combo_box = add_labled_widget(
            "InputImage", ImageLayerComboBox(self.viewer), row
        )
        row += 1

        grid.addWidget(QLabel("Neural Networl Predictions"), row, 0)
        row += 1

        grid.addWidget(bar(), row, 0, 1, 2)
        row += 1

        self._use_shipped_cb = add_labled_widget(
            "Use Shipped Model", QCheckBox(), row
        )
        row += 1

        self._shipped_combo_box = add_labled_widget(
            "ShippedModel", QComboBox(), row
        )
        self._shipped_combo_box.addItem("bbbc038_M8")
        row += 1

        grid.addWidget(bar(), row, 0, 1, 2)
        row += 1

        self._use_loaded_cb = add_labled_widget(
            "Use Loaded Model", QCheckBox(), row
        )
        row += 1

        self.select_model_button = add_labled_widget(
            "Model Path", QPushButton("Select model"), row
        )
        self.select_model_button.clicked.connect(
            self._on_selected_model_folder
        )
        self.select_model_button.setEnabled(False)
        row += 1
        self._model_path_label = add_labled_widget(
            "Selected Model", QLabel("None"), row
        )
        row += 1

        group = QButtonGroup(self)
        group.addButton(self._use_shipped_cb)
        group.addButton(self._use_loaded_cb)
        self._use_shipped_cb.setChecked(True)

        def on_click(btn):
            if self._use_shipped_cb.isChecked():
                self.select_model_button.setEnabled(False)
                self._shipped_combo_box.setEnabled(True)
            else:
                self.select_model_button.setEnabled(True)
                self._shipped_combo_box.setEnabled(False)

        group.buttonClicked.connect(on_click)

        grid.addWidget(bar(), row, 0, 1, 2)
        row += 1

        add_labled_widget("Normalize Image", QCheckBox(), row)
        row += 1
        add_labled_widget("Percentile Low", DoubleSpinSlider([0, 1], 0.1), row)
        row += 1
        add_labled_widget(
            "Percentile High", DoubleSpinSlider([0, 1], 0.9), row
        )
        row += 1

        grid.addWidget(bar(), row, 0, 1, 2)
        row += 1

        self._run_button = QPushButton("run")
        self._run_button.clicked.connect(self._on_run)
        grid.addWidget(self._run_button, row, 0, 1, 2)
        row += 1

        self._progress_widget = ProgressWidget(self)
        grid.addWidget(self._progress_widget, row, 0, 1, 2)
        row += 1

        grid.addWidget(bar(), row, 0, 1, 2)
        row += 1

    def _connect_events(self):
        pass

    def _verify_model_path(self, path):
        return

    def _on_selected_model_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select a splinedist model folder"
        )
        self._verify_model_path(path)
        self._model_path = path

        self._model_path_label.setText(shorten_path(path, 2))

    def _on_worker_started(self):
        print("_on_worker_started")
        self._progress_widget.setProgress("prepare", 25)

    def _on_worker_finished(self):
        self._run_button.setEnabled(True)

    def _on_worker_resulted(self, results):

        self._progress_widget.setProgress("make layers", 0)

        labels, details = results
        coords = details["coord"]
        coords_list = []
        for i in range(coords.shape[0]):
            coords_list.append(coords[i, ...].T)

        if self.interpolated_layer is None:
            interpolator = splineit_interpolator_factory(name="UhlmannSplines")
            interpolated_layer, ctrl_layer = splineit_layer_factory(
                viewer=self.viewer,
                interpolator=interpolator,
                data=coords_list,
            )
            self.interpolated_layer = interpolated_layer
            self.ctrl_layer = ctrl_layer
        else:
            self.ctrl_layer.selected_data = set(range(self.ctrl_layer.nshapes))
            self.ctrl_layer.remove_selected()
            self.ctrl_layer.add_polygons(data=coords_list)

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

    def _get_visible_slicing(self):
        input_layer = self._get_input_layer()
        crop = tuple(slice(i[0], i[1]) for i in input_layer.corner_pixels.T)
        return crop

    def _on_run(self):

        input_layer = self._get_input_layer()
        logger.info(f"run on layer {input_layer.name}")

        self._progress_widget.setProgress("prepare", 0)

        self._run_button.setEnabled(False)

        slicing = self._get_visible_slicing()
        sub_data = input_layer.data[slicing]

        self.worker = Worker(sub_data=sub_data)
        self.worker.started.connect(self._on_worker_started)
        self.worker.resulted.connect(self._on_worker_resulted)
        self.worker.errored.connect(self._on_worker_errored)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.start()
        self._progress_widget.setProgress("prepare", 50)
