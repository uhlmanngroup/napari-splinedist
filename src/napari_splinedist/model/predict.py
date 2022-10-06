# from __future__ import (
#     print_function,
#     unicode_literals,
#     absolute_import,
#     division,
# )
import os
import sys

sys.path.append(os.path.dirname(os.path.realpath(__file__)))

import os
import sys

from csbdeep.utils import normalize

# from csbdeep.io import save_tiff_imagej_compatible


# from splinedist.models import SplineDist2D


os.environ["CUDA_VISIBLE_DEVICES"] = ""


from splinedist.utils import grid_generator, phi_generator


# @functools.lru_cache(maxsize=1)
def build_model(model_path=None, M=8, grid=(2, 2), contoursize_max=400):
    if model_path is None:
        model_path = "/home/derthorsten/src/splinedist/models/bbbc038_M8"
    from splinedist.models import Config2D, SplineDist2D

    n_params = 2 * M
    conf = Config2D(
        n_params=n_params,
        grid=tuple(grid),
        n_channel_in=1,
        contoursize_max=contoursize_max,
    )

    phi_generator(M, conf.contoursize_max, model_path)
    grid_generator(M, conf.train_patch_size, conf.grid, model_path)

    basedir = "/home/derthorsten/src/splinedist/models"
    return SplineDist2D(None, name="bbbc038_M8", basedir=basedir)


def predict(
    image,
    model_path=None,
    M=8,
    grid=(2, 2),
    contoursize_max=400,
    progress_callback=None,
):
    if progress_callback is not None:
        progress_callback("build-model", 0)
    # cached st
    model = build_model(
        model_path=model_path,
        M=M,
        grid=grid,
        contoursize_max=contoursize_max,
    )
    if progress_callback is not None:
        progress_callback("build-model", 100)

    axis_norm = (0, 1)
    img = normalize(image, 1, 99.8, axis=axis_norm)
    labels, details = model.predict_instances(
        img, progress_callback=progress_callback
    )

    return labels, details
