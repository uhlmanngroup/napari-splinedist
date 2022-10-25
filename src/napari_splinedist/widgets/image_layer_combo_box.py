from napari.layers import Image as ImageLayer
from qtpy.QtWidgets import QComboBox


# ComboBox which shows all napari layers
# which are of type "ImageLayer"
#
# when layers are
# inserted/deleted/renamed the
# Combo box is auto updated
class ImageLayerComboBox(QComboBox):
    def __init__(self, napari_viewer):
        super().__init__()
        self._viewer = napari_viewer
        self._layer_mapping = dict()

        self._connect_events()
        self._rebuild()

    def _connect_events(self):
        # connect all exisitng layers
        for layer in self._viewer.layers:
            print(layer)
            if isinstance(layer, ImageLayer):
                layer.events.name.connect(self._rebuild)

        self._viewer.layers.events.inserted.connect(self._on_layer_inserted)
        self._viewer.layers.events.removed.connect(self._rebuild)

    def _on_layer_inserted(self, event):
        layer = event.value
        if isinstance(layer, ImageLayer):
            layer.events.name.connect(self._rebuild)
            self._rebuild()

    def _rebuild(self, *args, **kwargs):
        new_layer_mapping = dict()
        current_layer = None
        if self.count() > 0:
            current_layer = self._layer_mapping[self.currentIndex()]
        self.clear()
        index = 0
        current_index = None
        for layer in self._viewer.layers:
            if isinstance(layer, ImageLayer):
                self.addItem(layer.name)
                new_layer_mapping[index] = layer
                if current_layer is not None and layer == current_layer:
                    current_index = index
                index += 1
        if current_index is not None:
            self.setCurrentIndex(current_index)

        self._layer_mapping = new_layer_mapping

    def currentLayer(self):
        return self._layer_mapping[self.currentIndex()]
