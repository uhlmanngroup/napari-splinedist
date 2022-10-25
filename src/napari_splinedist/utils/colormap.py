import numpy as np


def make_labels_colormap(labels):
    mx = labels.max()
    return make_colormap(mx)


def make_colormap(mx):

    # when labels are empty,ie only zeros, we would
    # only need a LUT of shape 1 X 4.
    # but napari dislikes a LUT which has 1x4 shape
    # and is all zeros.
    # in  that case napari ignores the alpha channel
    # and the image is black instead of transparent.
    # as a consequence we do mx +2 to guarantee
    # a minimum size of 2x4
    colormap = np.random.random(size=(mx + 2, 4))
    colormap[0, :] = 0.0
    if mx > 0:
        colormap[1:, 3] = 1.0
    return colormap
