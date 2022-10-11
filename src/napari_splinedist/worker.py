from qtpy.QtCore import QObject, Signal


class MyWorkerSignals(QObject):
    # started = Signal()
    resulted = Signal()
    progress = Signal(str, int)
    chunked_results = Signal(object)


# class Worker(WorkerBase):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._signals = MyWorkerSignals()

# def __init__(self, data, slicing, parent=None, **kwargs):
#     self.data = data
#     self.slicing = slicing
#     self.kwargs = kwargs
#     QObject.__init__(self, parent)

# def progress_callback(self, name, progress):
#     self.progress.emit(name, int(progress))

# @Slot()
# def run(self):
#     print("RUUUN")
#     # self.started.emit()

#     try:
#         self.progress.emit("prepare", 100)
#         labels, details = predict(
#             self.data,
#             progress_callback=self.progress_callback,
#             **self.kwargs
#         )
#         coords_list = self._transform_results(details)
#         self.resulted.emit()

#         p = 0
#         n_chunks = 5
#         n = len(coords_list) // n_chunks
#         done = 0
#         for chunk in chunks(coords_list, n):
#             print("emit", len(chunk))
#             self.chunked_results.emit(chunk)
#             percentage = done / len(coords_list) * 100.0
#             done += len(chunk)
#             self.progress.emit("make layers", int(percentage))
#             # print("DONE", done, "make layers", percentage)
#             # print("sleep")
#             # time.sleep(0.1)
#             # break
#         self.progress.emit("make layers", 100)
#     except Exception as e:
#         self.errored.emit(e)

#     finally:
#         self.finished.emit()

# def _transform_results(self, details):
#     if self.slicing is not None:
#         offset = np.array([self.slicing[0].start, self.slicing[1].start])
#     else:
#         offset = np.array([0, 0])
#     coords = details["coord"]
#     coords_list = []
#     for i in range(coords.shape[0]):
#         coords_list.append(coords[i, ...].T + offset)
#     return coords_list
