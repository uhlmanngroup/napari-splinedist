import os
from pathlib import Path

from qtpy import QtCore, QtGui, QtWidgets

THIS_DIR = Path(os.path.dirname(os.path.realpath(__file__)))
LOGO = THIS_DIR.parent / "logo" / "logo_white_small.svg"


class RotatingLabel(QtWidgets.QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pixmap = QtGui.QPixmap()

    def set_pixmap(self, pixmap):
        self._pixmap = pixmap
        self.setPixmap(self._pixmap)

    def rotate(self, value):
        t = QtGui.QTransform()
        t.rotate(value)

        pxw = self._pixmap.width()
        pxh = self._pixmap.height()

        pix = self._pixmap.transformed(t)

        pix = pix.copy(
            (pix.width() - pxw) // 2, (pix.height() - pxh) // 2, pxw, pxh
        )

        self.setPixmap(pix)


class RotatingLogoWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.label = RotatingLabel(alignment=QtCore.Qt.AlignCenter)
        pixmap = QtGui.QPixmap(str(LOGO))
        t = QtGui.QTransform()
        pixmap = pixmap.transformed(t)
        self.label.set_pixmap(pixmap)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(self.label)

    def setValue(self, v):
        deg = -3.6 * v * 4
        self.label.rotate(deg)
