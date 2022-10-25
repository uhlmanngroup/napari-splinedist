import os
import shutil
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, parse_file_as

from .appdir import APPDIR

THIS_DIR = Path(os.path.dirname(os.path.realpath(__file__)))
CONFIG_FILENAME = "napari_splinedist_config.json"
DEFAULT_CONFIG_JSON = THIS_DIR / CONFIG_FILENAME
APPDIR_CONFIG = APPDIR / CONFIG_FILENAME


# Pydantic models for the config file.
# The use of pydantic makes sure that
# the config json file has the write
# format. If not a more-or-less
# readable error message is shown

# an enum to distinguish between
# models located at a local path/dir
# and models stored at a remote URL
class SourceType(str, Enum):
    path = "path"
    url = "url"


# the source for a model
class SourceModel(BaseModel):
    # can be path vs. url
    source_type: SourceType
    # how many controll points
    n_control_points: int
    # actual dir or path
    source: str


# the pydantic model for a model
class ModelModel(BaseModel):
    # name of the model visible in UI
    name: str
    # how many input channels does
    # this model have
    in_channels: int

    # an optional path relativ to the model dir
    # to a prototypical image used for training
    # this model
    preview_image: Optional[Path] = None

    # a list of sources. each source
    # has a different number of controll points
    sources: List[SourceModel]


# the config
class ConfigModel(BaseModel):
    # list of models
    models: List[ModelModel]


# if the config is **not** present in the
# config dir, we copy the default config
if not APPDIR_CONFIG.exists():
    shutil.copyfile(DEFAULT_CONFIG_JSON, APPDIR_CONFIG)

# load the config from the config dir with pydantic
CONFIG = parse_file_as(path=APPDIR_CONFIG, type_=ConfigModel)
