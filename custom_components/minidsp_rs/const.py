"""Constants for the miniDSP-rs integration."""

import logging
from datetime import timedelta

DOMAIN = "minidsp_rs"
LOGGER = logging.getLogger(__package__)

CONF_DEVICE_ID = "device_id"
CONF_DEVICE_URL = "device_url"
CONF_PRODUCT_NAME = "product_name"
CONF_SERIAL = "serial"

DEFAULT_NAME = "miniDSP"
DEFAULT_PORT = 5380
UPDATE_INTERVAL = timedelta(seconds=5)

MIN_VOLUME_DB = -127.0
MAX_VOLUME_DB = 0.0
VOLUME_STEP_DB = 0.5

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
