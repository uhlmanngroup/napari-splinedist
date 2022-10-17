import numpy as np


def make_labels_colormap(labels):
    mx = labels.max()
    colormap = np.random.random(size=(mx, 4))
    colormap[0, :] = 0.0
    colormap[1:, 3] = 1.0
    return colormap
