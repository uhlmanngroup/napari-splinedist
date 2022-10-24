# from __future__ import (
#     print_function,
#     unicode_literals,
#     absolute_import,
#     division,
# )
import functools
import json
from pathlib import Path

import numpy as np
from csbdeep.utils import normalize
from splinedist.utils import grid_generator, phi_generator

from .._logging import logger
from ..exceptions import PredictionException


# to speed up thye building of the model,
# we cache this
@functools.lru_cache(maxsize=1)
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
    return SplineDist2D(None, name=model_path.name, basedir=str(basedir))


def predict(
    image,
    model_path,
    normalize_image,
    percentile_low,
    percentile_high,
    invert_image,
    prob_thresh,
    nms_thresh,
    model_meta,
    grid=(2, 2),
    progress_callback=None,
    n_tiles=None,
):
    # how many color channels does the imag have?
    if image.ndim == 2:
        in_channels = 1
    elif image.ndim == 3:
        in_channels = image.shape[2]

    model_in_channels = model_meta.in_channels
    # are they matching with the models expected
    # number of channels?
    if in_channels != model_in_channels:
        if model_in_channels == 1:
            image = np.sum(image, axis=2) / in_channels
        else:
            raise PredictionException(
                f"{in_channels} != {model_meta.in_channels}"
            )

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

    # should the image be inverted (only for gray)
    if invert_image:
        if in_channels > 1:
            raise PredictionException("only gray image can be inverted")
        image = image.max() - image

    axis_norm = (0, 1)
    if normalize_image:
        logger.info(f"normalize {percentile_low=} {percentile_high=}")
        img = normalize(image, percentile_low, percentile_high, axis=axis_norm)
    else:
        img = image

    # run prediction
    labels, details = model.predict_instances(
        img,
        # progress_callback=progress_callback,
        prob_thresh=prob_thresh,
        nms_thresh=nms_thresh,
        n_tiles=n_tiles,
    )

    return labels, details
