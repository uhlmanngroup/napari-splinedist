class NoInputImageException(Exception):
    def __init__(
        self,
        message="SplineDist Error: Input image is missing!\nAt least one image layer must be available",
    ):
        super().__init__(message)


class NoLoadedModelException(Exception):
    def __init__(
        self,
        message="SplineDist Error: Loaded model path is missing!\nSet directory approriate and rerun",
    ):
        super().__init__(message)
