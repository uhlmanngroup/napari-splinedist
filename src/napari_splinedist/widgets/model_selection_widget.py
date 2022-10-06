from qtpy.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class ModelSelectionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.layout = grid = QGridLayout()
        self.layout.addWidget(QLabel("Selected Model"), 0, 0)
        self.layout.addWidget(QLabel("BRAAAA   Model"), 0, 1)

        self.layout.addWidget(QLabel("Selected Model"), 1, 0)
        self.layout.addWidget(QLabel("BRAAAA   Model"), 1, 1)

        QPushButton("select model")

        self.setLayout(self.layout)

    # def setProgress(self, text, progress):
    #     self.label.setText(f"Status: {text}")
    #     self.pbar.setValue(progress)
