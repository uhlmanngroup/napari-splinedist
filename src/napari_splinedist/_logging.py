import logging
import logging.config

MY_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default_formatter": {
            "format": "[%(levelname)s:%(asctime)s] %(message)s"
        },
    },
    "handlers": {
        "stream_handler": {
            "class": "logging.StreamHandler",
            "formatter": "default_formatter",
        },
    },
    "loggers": {
        "splinedist": {
            "handlers": ["stream_handler"],
            "level": "INFO",
            "propagate": True,
        }
    },
}

logging.config.dictConfig(MY_LOGGING_CONFIG)
logger = logging.getLogger("splinedist")
