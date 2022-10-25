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

        # store withd/height
        # before rotating
        pxw = int(self._pixmap.width())
        pxh = int(self._pixmap.height())

        # rotate the pixmap
        t = QtGui.QTransform()
        t.rotate(value)
        pix = self._pixmap.transformed(t)

        # crop an image from the center with the size before
        # rotating st. the image will keep the same size
        pix = pix.copy(
            (pix.width() - pxw) // 2, (pix.height() - pxh) // 2, pxw, pxh
        )

        # update the pixmap
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
        # how often shall we rotate
        # when hitting 100%
        n_rotations_on_100_percent = 5

        # convert v (in range from [0,100])
        # to degrees (in range from [0,360])
        deg = -3.6 * v

        # the actual number of degrees we need to rotate
        effective_deg = deg * n_rotations_on_100_percent
        self.label.rotate(effective_deg)
