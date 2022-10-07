from qtpy.QtCore import QThread, Signal

from .model.predict import predict


class Worker(QThread):

    started = Signal()
    resulted = Signal(object)
    progress = Signal(str, int)
    errored = Signal(object)
    finished = Signal()

    def __init__(self, data, slicing, parent=None, **kwargs):
        self.data = data
        self.slicing = slicing
        self.kwargs = kwargs
        QThread.__init__(self, parent)

    def progress_callback(self, name, progress):
        self.progress.emit(name, int(progress))

    def run(self):
        self.started.emit()

        try:
            self.progress.emit("prepare", 100)
            labels, details = predict(
                self.data,
                progress_callback=self.progress_callback,
                **self.kwargs
            )

            self.resulted.emit([labels, details, self.slicing])

        except Exception as e:
            self.errored.emit(e)

        finally:
            self.finished.emit()
