import os
from pathlib import Path

import skimage.io

THIS_DIR = Path(os.path.dirname(os.path.realpath(__file__)))
SAMPLE_DATA_DIR = THIS_DIR / "sample_data"


def sample_data_conic():
    img = skimage.io.imread(SAMPLE_DATA_DIR / "conic.png")
    return [(img, {"name": "conic"})]


def sample_data_bbbc038():
    img = skimage.io.imread(SAMPLE_DATA_DIR / "bbbc038.png")
    return [(img, {"name": "bbbc038"})]
