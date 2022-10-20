import zipfile
from pathlib import Path

from napari.qt.threading import GeneratorWorker as NapariGeneratorWorker
from napari.qt.threading import thread_worker
from qtpy.QtCore import QObject, QSignalBlocker, Qt, Signal
from qtpy.QtGui import QImage, QPixmap
from qtpy.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QWidget,
)

from ..utils.download_file import download_file


class DownloadWorker(NapariGeneratorWorker):
    class ExtraSignals(QObject):
        progress = Signal(float, int, int)
        resulted = Signal(object)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra_signals = DownloadWorker.ExtraSignals()


class ModelDownloadWidget(QWidget):
    model_availablity_changed = Signal(bool)
    progress = Signal(float)

    def __init__(self, download_dir):
        super().__init__()

        self._models_meta = None  # models_meta
        self._download_dir = Path(download_dir)
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self.worker = None

        self._init_ui()
        self._connect_events()

    def setModelsMeta(self, models_meta):

        with QSignalBlocker(self._name_combo_box):
            with QSignalBlocker(self._n_ctrl_points_combo_box):

                self._models_meta = models_meta

                names = [meta.name for meta in self._models_meta]
                self._name_combo_box.addItems(names)

                self._n_ctrl_points_combo_box.clear()
                n_ctrl_names = [
                    str(source_meta.n_control_points)
                    for source_meta in self.getModelMeta().sources
                ]
                self._n_ctrl_points_combo_box.addItems(n_ctrl_names)

        self._on_model_changed()

    def _init_ui(self):

        self._name_combo_box = QComboBox()
        self._n_ctrl_points_combo_box = QComboBox()
        self._progress_widget = QProgressBar()
        self._cancel_button = QPushButton("cancel")
        self._restart_button = QPushButton("restart")
        self._cancel_button.setEnabled(False)
        self._restart_button.setEnabled(False)
        self._sample_image_label = QLabel()

        self.setLayout(QGridLayout())
        self.layout().addWidget(self._name_combo_box, 0, 0)
        self.layout().addWidget(self._n_ctrl_points_combo_box, 0, 1)
        self.layout().addWidget(self._progress_widget, 1, 0, 1, 2)
        self.layout().addWidget(self._cancel_button, 2, 0)
        self.layout().addWidget(self._restart_button, 2, 1)
        self.layout().addWidget(self._sample_image_label, 3, 0, 1, 2)

        if self._models_meta is not None:
            names = [meta["name"] for meta in self._models_meta]
            self._name_combo_box.addItems(names)
            self._on_model_name_changed(0)

    def getModelMeta(self, index=None):
        if index is None:
            index = self._name_combo_box.currentIndex()
        return self._models_meta[index]

    def _n_ctrl_points(self):
        return self._current_source().n_control_points

    def _current_source(self):
        return self.getModelMeta().sources[
            self._n_ctrl_points_combo_box.currentIndex()
        ]

    def _connect_events(self):
        self._name_combo_box.currentIndexChanged.connect(
            self._on_model_name_changed
        )
        self._n_ctrl_points_combo_box.currentIndexChanged.connect(
            self._on_n_ctrl_points_combo_box_changed
        )

        def kill_worker():
            self.worker.quit()

        self._cancel_button.clicked.connect(kill_worker)

        def restart_dl():
            self._on_model_changed()

        self._restart_button.clicked.connect(restart_dl)

    def _on_model_name_changed(self, index):
        with QSignalBlocker(self._n_ctrl_points_combo_box):
            self._n_ctrl_points_combo_box.clear()
            n_ctrl_names = [
                str(source_meta.n_control_points)
                for source_meta in self.getModelMeta(index).sources
            ]
            self._n_ctrl_points_combo_box.addItems(n_ctrl_names)

        self._on_model_changed()

    def _on_n_ctrl_points_combo_box_changed(self, index):
        self._on_model_changed()

    def _on_worker_started(self):
        pass

    def _on_worker_finished(self):
        if self.worker.abort_requested:
            self._restart_button.setEnabled(True)
        self._name_combo_box.setEnabled(True)
        self._n_ctrl_points_combo_box.setEnabled(True)
        self._cancel_button.setEnabled(False)

    def _on_worker_errored(self, e):
        raise e

    def _on_worker_yielded_results(self, path):
        self.model_availablity_changed.emit(True)

        if self.getModelMeta().preview_image is not None:

            sample_image_path = (
                Path(self._current_model_path())
                / self.getModelMeta().preview_image
            )
            if sample_image_path.exists():
                img = QImage()
                img.load(str(sample_image_path))
                img = img.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio)
                self._sample_image_label.setPixmap(QPixmap.fromImage(img))

        else:
            self._sample_image_label.clear()

    def _on_worker_progress(self, p, t=None, d=None):
        if t is not None and d is not None:
            self._progress_widget.setFormat(f"{p:.2f}% ({d}/ {t})")
        if p >= 100:
            self._progress_widget.setFormat("model is ready")
        self._progress_widget.setValue(int(p))
        self.progress.emit(p)

    def _current_model_path(self):
        source = self._current_source()
        source_type = source.source_type
        if source_type == "url":
            name = f"{self.getModelMeta().name}_{self._n_ctrl_points()}"
            path = self._download_dir / name
            return path
        elif source_type == "path":
            return source.source

    def _on_model_changed(self):

        self._on_worker_progress(0, "?", 0)
        self.model_availablity_changed.emit(False)
        self._name_combo_box.setEnabled(False)
        self._n_ctrl_points_combo_box.setEnabled(False)
        self._restart_button.setEnabled(False)
        self._cancel_button.setEnabled(True)
        self._progress_widget.setValue(0)
        self._sample_image_label.clear()

        @thread_worker(worker_class=DownloadWorker, start_thread=False)
        def work_function(source):

            if source.source_type == "url":
                base_name = (
                    f"{self.getModelMeta().name}_{self._n_ctrl_points()}"
                )
                name = f"{base_name}.zip"
                zip_path = self._download_dir / name
                unzipped_path = self._download_dir / base_name

                if unzipped_path.exists():
                    self._on_worker_progress(100)
                    self.worker.extra_signals.resulted.emit(unzipped_path)
                else:

                    def status(progress, total, downloaded):
                        self.worker.extra_signals.progress.emit(
                            progress, total, downloaded
                        )

                    # the empty yield allows us to cancel the download
                    for _ in download_file(source.source, zip_path, status):
                        yield

                    with zipfile.ZipFile(zip_path, "r") as zip_ref:
                        zip_ref.extractall(self._download_dir)

                    # yield unzipped_path
                    self.worker.extra_signals.resulted.emit(unzipped_path)
            elif source.source_type == "path":
                self._on_worker_progress(100)
                if not Path(source.source).exists():
                    raise FileNotFoundError(
                        f"source directory `{source.source}` does not exist"
                    )
                self.worker.extra_signals.resulted.emit(source.source)

        self.worker = work_function(self._current_source())
        self.worker.started.connect(self._on_worker_started)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.errored.connect(self._on_worker_errored)
        self.worker.extra_signals.resulted.connect(
            self._on_worker_yielded_results
        )
        self.worker.extra_signals.progress.connect(self._on_worker_progress)
        self.worker.start()
