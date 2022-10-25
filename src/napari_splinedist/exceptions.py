# raised when we try to predict
# without any input image
class NoInputImageException(Exception):
    def __init__(
        self,
        message="SplineDist Error: Input image is missing!",
    ):
        super().__init__(message)


# raised for failures while predicting
class PredictionException(Exception):
    def __init__(self, message=None):
        super().__init__(message)
