from qtpy.QtCore import QThread, Signal

from .model.predict import predict


class Worker(QThread):

    started = Signal()
    resulted = Signal(object)
    progress = Signal(str, int)
    errored = Signal(object)
    finished = Signal()

    def __init__(self, sub_data, parent=None):
        self.sub_data = sub_data
        QThread.__init__(self, parent)

    def progress_callback(self, name, progress):
        self.progress.emit(name, int(progress))

    def run(self):
        self.started.emit()

        try:
            self.progress.emit("prepare", 100)
            labels, details = predict(
                self.sub_data, progress_callback=self.progress_callback
            )

            self.resulted.emit([labels, details])

        except Exception as e:
            self.errored.emit(e)

        finally:
            self.finished.emit()
