from pathlib import Path

import appdirs

APP_NAME = "NapariSplineDist"
APP_AUTHOR = "NapariSplineDistAuthors"
APPDIR = Path(appdirs.user_data_dir(APP_NAME, APP_AUTHOR))
APPDIR.mkdir(exist_ok=True, parents=True)
