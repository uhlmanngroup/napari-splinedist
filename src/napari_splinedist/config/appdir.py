from pathlib import Path

# this package makes it easy
# to get a persitent directory
import appdirs

# We create an appdir for splinedist.
# Later we store:
#  * a config which contains
#    list of models to donwload
#  * the donwloaded models
APP_NAME = "NapariSplineDist"
APP_AUTHOR = "NapariSplineDistAuthors"
APPDIR = Path(appdirs.user_data_dir(APP_NAME, APP_AUTHOR))
APPDIR.mkdir(exist_ok=True, parents=True)
