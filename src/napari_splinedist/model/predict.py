# from __future__ import (
#     print_function,
#     unicode_literals,
#     absolute_import,
#     division,
# )
import os
import sys

sys.path.append(os.path.dirname(os.path.realpath(__file__)))

import json
import os
import sys
from pathlib import Path

import numpy as np
from csbdeep.utils import normalize

# from csbdeep.io import save_tiff_imagej_compatible


# from splinedist.models import SplineDist2D


os.environ["CUDA_VISIBLE_DEVICES"] = ""


from splinedist.utils import grid_generator, phi_generator

from .._logging import logger


# @functools.lru_cache(maxsize=1)
def build_model(model_path, grid=(2, 2)):

    from splinedist.models import Config2D, SplineDist2D

    with open(Path(model_path) / "config.json") as f:
        config = json.load(f)

    n_params = config["n_params"]
    M = n_params // 2

    conf = Config2D(
        n_params=n_params,
        grid=tuple(grid),
        n_channel_in=1,
        contoursize_max=config["contoursize_max"],
    )

    phi_generator(M, conf.contoursize_max, str(model_path))
    grid_generator(M, conf.train_patch_size, conf.grid, str(model_path))

    basedir = model_path.parent
    return SplineDist2D(None, name="bbbc038_M8", basedir=str(basedir))


def predict(
    image,
    model_path,
    normalize_image,
    percentile_low,
    percentile_high,
    invert_image,
    prob_thresh,
    nms_thresh,
    grid=(2, 2),
    progress_callback=None,
    n_tiles=None,
):
    # if the image has an integral dtype, we normalize
    # by dividing with the max value for that dtype
    # even when normalize_image == False
    if np.issubdtype(image.dtype, np.integer):
        image = image.astype("float32") / np.iinfo(image.dtype).max
    else:
        image = np.require(image, requirements=["C"], dtype="float32")
    if progress_callback is not None:
        progress_callback("build-model", 0)
    # cached st
    model = build_model(model_path=model_path, grid=grid)
    if progress_callback is not None:
        progress_callback("build-model", 100)

    if invert_image:
        image = image.max() - image

    axis_norm = (0, 1)
    if normalize_image:
        logger.info(f"normalize {percentile_low=} {percentile_high=}")
        img = normalize(image, percentile_low, percentile_high, axis=axis_norm)
    else:
        img = image
        # img = normalize(image, 0.0, 100.0, axis=axis_norm)
    labels, details = model.predict_instances(
        img,
        progress_callback=progress_callback,
        prob_thresh=prob_thresh,
        nms_thresh=nms_thresh,
        n_tiles=n_tiles,
    )

    return labels, details
