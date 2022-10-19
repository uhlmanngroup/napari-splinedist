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


class SourceType(str, Enum):
    path = "path"
    url = "url"


class SourceModel(BaseModel):
    source_type: SourceType
    n_control_points: int
    source: str


class ModelModel(BaseModel):
    name: str
    in_channels: int
    preview_image: Optional[Path] = None
    sources: List[SourceModel]


class ConfigModel(BaseModel):
    models: List[ModelModel]


if not APPDIR_CONFIG.exists():
    shutil.copyfile(DEFAULT_CONFIG_JSON, APPDIR_CONFIG)

CONFIG = parse_file_as(path=APPDIR_CONFIG, type_=ConfigModel)
