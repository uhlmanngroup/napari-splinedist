from qtpy.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


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
