"""Constants for the miniDSP-rs integration."""

import logging
from datetime import timedelta

DOMAIN = "minidsp_rs"
LOGGER = logging.getLogger(__package__)

CONF_DEVICE_ID = "device_id"
CONF_DEVICE_URL = "device_url"
CONF_PRODUCT_NAME = "product_name"
CONF_SERIAL = "serial"
CONF_MUTE_WITH_VOLUME = "mute_with_volume"
CONF_VOLUME_CURVE = "volume_curve"
CONF_VOLUME_CURVE_MODE = "volume_curve_mode"
CONF_VOLUME_MAX_DB = "volume_max_db"
CONF_VOLUME_MIN_DB = "volume_min_db"
CONF_VOLUME_POINT_25_DB = "volume_point_25_db"
CONF_VOLUME_POINT_50_DB = "volume_point_50_db"
CONF_VOLUME_POINT_75_DB = "volume_point_75_db"

DEFAULT_NAME = "miniDSP"
DEFAULT_PORT = 5380
UPDATE_INTERVAL = timedelta(seconds=5)

DEVICE_MIN_VOLUME_DB = -127.0
DEVICE_MAX_VOLUME_DB = 0.0
DEFAULT_VOLUME_MIN_DB = -90.0
DEFAULT_VOLUME_MAX_DB = -10.0
VOLUME_CURVE_MODE_EXPONENT = "exponent"
VOLUME_CURVE_MODE_FIVE_POINT = "five_point"
DEFAULT_VOLUME_CURVE_MODE = VOLUME_CURVE_MODE_EXPONENT
DEFAULT_VOLUME_CURVE = 0.415
DEFAULT_MUTE_WITH_VOLUME = False
MIN_VOLUME_CURVE = 0.05
MAX_VOLUME_CURVE = 5.0
VOLUME_STEP = 0.01

PRESET_NAMES = ("Preset 1", "Preset 2", "Preset 3", "Preset 4")

SOURCE_LABELS = {
    "Analog": "Analog",
    "Toslink": "TOSLINK",
    "Spdif": "S/PDIF",
    "Usb": "USB",
    "Aesebu": "AES/EBU",
    "Rca": "RCA",
    "Xlr": "XLR",
    "Lan": "LAN",
    "I2S": "I²S",
    "Bluetooth": "Bluetooth",
    "Hdmi": "HDMI",
}
