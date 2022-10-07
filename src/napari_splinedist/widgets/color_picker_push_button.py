import numpy as np
from qtpy.QtCore import Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QColorDialog, QPushButton


class ColorPicklerPushButton(QPushButton):

    colorChanged = Signal(QColor)

    def __init__(self, color, with_alpha=True, tracking=False, parent=None):
        super().__init__(parent)

        self._with_alpha = with_alpha
        self._color = color
        self._tracking = tracking
        self._set_background_color()

        self.clicked.connect(self._on_clicked)

    def _on_color_changed(self, color):
        self._color = color
        self.colorChanged.emit(self._color)

    def _on_clicked(self):
        old_color = QColor(self._color)
        dialog = QColorDialog()
        dialog.setOption(QColorDialog.ShowAlphaChannel, on=self._with_alpha)
        if self._tracking:
            dialog.currentColorChanged.connect(self._on_color_changed)
        dialog.setCurrentColor(self._color)
        if dialog.exec_() == QColorDialog.Accepted:
            self._color = dialog.selectedColor()
            if not self._tracking:
                self._on_color_changed(self._color)
            self._set_background_color()
        else:
            self._on_color_changed(old_color)
            self._set_background_color()

    def getColor(self):
        return self._color

    def setColor(self, color):
        self._color = color
        self._set_background_color()

    def asArray(self):
        c = self._color
        if self._with_alpha:
            arr = [c.red(), c.green(), c.blue(), c.alpha()]
        else:
            arr = [c.red(), c.green(), c.blue()]
        return np.array(arr) / 255.0

    def _set_background_color(self):
        c = self._color
        r = c.red()
        g = c.green()
        b = c.blue()
        if self._with_alpha:
            a = c.alpha()
            self.setStyleSheet(f"background-color:rgba({r},{g},{b},{a})")
        else:
            self.setStyleSheet(f"background-color:rgb({r},{g},{b})")
