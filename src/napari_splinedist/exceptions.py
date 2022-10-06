class NoInputImageException(Exception):
    def __init__(
        self,
        message="SplineDist Error: Input image is missing!\nAt least one image layer must be available",
    ):
        super().__init__(message)
