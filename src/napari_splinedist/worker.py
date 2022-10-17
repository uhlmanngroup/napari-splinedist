from napari.qt.threading import GeneratorWorker as NapariGeneratorWorker
from qtpy.QtCore import QObject, Signal


class GeneratorWorker(NapariGeneratorWorker):
    class ExtraSignals(QObject):
        progress = Signal(str, int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra_signals = GeneratorWorker.ExtraSignals()
