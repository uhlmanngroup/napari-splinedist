import os
from pathlib import Path

THIS_DIR = Path(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_CONFIG_JSON = THIS_DIR / "config.json"


def get_config():
    pass
