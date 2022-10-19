class NoInputImageException(Exception):
    def __init__(
        self,
        message="SplineDist Error: Input image is missing!",
    ):
        super().__init__(message)


class PredictionException(Exception):
    def __init__(self, message=None):
        super().__init__(message)


class WrongSourceTypeExpcetion(Exception):
    def __init__(self, message=None):
        super().__init__(message)
