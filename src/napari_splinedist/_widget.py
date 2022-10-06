"""
This module is an example of a barebones QWidget plugin for napari

It implements the Widget specification.
see: https://napari.org/stable/plugins/guides.html?#widgets

Replace code below according to your needs.
"""
import logging
import logging.config
from pathlib import Path
from typing import TYPE_CHECKING

from napari.qt.threading import thread_worker
from napari_splineit.interpolation import (
    interpolator_factory as splineit_interpolator_factory,
)
from napari_splineit.layer.layer_factory import (
    layer_factory as splineit_layer_factory,
)
from napari_splineit.widgets.double_spin_slider import DoubleSpinSlider
from qtpy.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .widgets.image_layer_combo_box import ImageLayerComboBox
from .worker import Worker

MY_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default_formatter": {
            "format": "[%(levelname)s:%(asctime)s] %(message)s"
        },
    },
    "handlers": {
        "stream_handler": {
            "class": "logging.StreamHandler",
            "formatter": "default_formatter",
        },
    },
    "loggers": {
        "splinedist": {
            "handlers": ["stream_handler"],
            "level": "INFO",
            "propagate": True,
        }
    },
}

logging.config.dictConfig(MY_LOGGING_CONFIG)
logger = logging.getLogger("splinedist")


if TYPE_CHECKING:
    pass


def shorten_path(file_path, length):
    """Split the path into separate parts, select the last
    'length' elements and join them again"""
    return str(Path(*Path(file_path).parts[-length:]))


class NoInputImageException(Exception):
    def __init__(
        self,
        message="SplineDist Error: Input image is missing!\nAt least one image layer must be available",
    ):
        super().__init__(message)


# class Worker(QObject):
#     finished = Signal()
#     intReady = Signal(int)

#     @Slot()
#     def proc_counter(self):  # A slot takes no params
#         for i in range(1, 100):
#             time.sleep(0.1)
#             self.intReady.emit(i)

#         self.finished.emit()


class ProgressWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.label = QLabel("Status:")
        self.pbar = QProgressBar(self)
        self.pbar.setMinimum(0)
        self.pbar.setMaximum(100)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.pbar)
        self.setLayout(self.layout)

    def setProgress(self, text, progress):
        self.label.setText(f"Status: {text}")
        self.pbar.setValue(progress)


class SplineDistWidget(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()

        self.viewer = napari_viewer

        self._model_path = None

        self._init_ui()
        self._connect_events()

        self.worker = None

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

        self._input_image_combo_box = add_labled_widget(
            "InputImage", ImageLayerComboBox(self.viewer), row
        )
        row += 1

        grid.addWidget(QLabel("Neural Networl Predictions"), row, 0)
        row += 1

        btn = add_labled_widget(
            "Select Model", QPushButton("select model"), row
        )
        btn.clicked.connect(self._on_selected_model_folder)
        row += 1
        self._model_path_label = add_labled_widget(
            "Selected Model", QLabel("None"), row
        )
        row += 1
        add_labled_widget("Normalize Image", QCheckBox(), row)
        row += 1
        add_labled_widget("Percentile Low", DoubleSpinSlider([0, 1], 0.1), row)
        row += 1
        add_labled_widget(
            "Percentile High", DoubleSpinSlider([0, 1], 0.9), row
        )
        row += 1

        self._run_button = QPushButton("run")
        self._run_button.clicked.connect(self._on_run)
        grid.addWidget(self._run_button, row, 0)
        row += 1

        self._progress_widget = ProgressWidget(self)
        grid.addWidget(self._progress_widget, row, 0, 1, 2)

    def _connect_events(self):
        # connect all exisitng layers
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

    def _on_worker_finished(self):
        self._run_button.setEnabled(True)

    def _on_worker_resulted(self, results):

        self._progress_widget.setProgress("make layers", 0)

        labels, details = results
        coords = details["coord"]
        coords_list = []
        for i in range(coords.shape[0]):
            coords_list.append(coords[i, ...].T)

        interpolator = splineit_interpolator_factory(name="UhlmannSplines")
        interpolated_layer, ctrl_layer = splineit_layer_factory(
            viewer=self.viewer,
            interpolator=interpolator,
            data=coords_list,
        )
        self._progress_widget.setProgress("done!", 100)

    def _on_worker_progress(self, name, progress):

        self._progress_widget.setProgress(name, progress)

    def _on_worker_errored(self, e):
        self._progress_widget.setProgress("ERRORED!", 100)
        raise RuntimeError(e)

    def _on_run(self):

        self._progress_widget.setProgress("prepare", 0)

        self._run_button.setEnabled(False)

        input_layer = self._input_image_combo_box.currentLayer()
        logger.info(f"run on layer {input_layer.name}")
        data = input_layer.data
        crop = tuple(slice(i[0], i[1]) for i in input_layer.corner_pixels.T)
        sub_data = data[crop]

        self.worker = Worker(sub_data=sub_data)
        self.worker.started.connect(self._on_worker_started)
        self.worker.resulted.connect(self._on_worker_resulted)
        self.worker.errored.connect(self._on_worker_errored)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.start()
        self._progress_widget.setProgress("prepare", 50)

    def _on_run_old(self):

        if self._input_image_combo_box.count() == 0:
            raise NoInputImageException()

        self._run_button.setEnabled(False)

        popup = PopUpProgressBar()

        def on_run_started():
            nonlocal popup
            popup.show()
            print("on started")

        def on_run_yielded(value):
            print("on yielded", value["type"])
            if value["type"] == "result":
                labels, details = value["value"]
                coords = details["coord"]
                coords_list = []
                for i in range(coords.shape[0]):
                    coords_list.append(coords[i, ...].T)

                interpolator = splineit_interpolator_factory(
                    name="UhlmannSplines"
                )
                interpolated_layer, ctrl_layer = splineit_layer_factory(
                    viewer=self.viewer,
                    interpolator=interpolator,
                    data=coords_list,
                )

        def on_run_finished():
            print("on finished")
            self._run_button.setEnabled(True)
            popup.hide()

        def on_run_error(err):
            print("on error", err)
            self._run_button.setEnabled(True)
            popup.hide()

        @thread_worker(
            connect={
                "errored": on_run_error,
                "started": on_run_started,
                "finished": on_run_finished,
                "yielded": on_run_yielded,
            }
        )
        def run_in_thread(sub_data):
            def progress_callback(*args, **kwargs):
                yield {"type": "misc", "value": (args, kwargs)}

            print("run in thread")
            progress_callback("wupppp")
            labels, details = predict(
                sub_data, progress_callback=progress_callback
            )
            yield {"type": "result", "value": (labels, details)}
            print("after yield")

        input_layer = self._input_image_combo_box.currentLayer()
        logger.info(f"run on layer {input_layer.name}")
        data = input_layer.data
        crop = tuple(slice(i[0], i[1]) for i in input_layer.corner_pixels.T)
        sub_data = data[crop]

        run_in_thread(sub_data)
