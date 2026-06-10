"""Constants shared across SwitchBot window devices (Blind Tilt, Curtain 3)."""

# Extended command subsystem bytes (first byte after EXT_SET/EXT_GET)
SUB_MOVE = 0x01
SUB_LINK = 0x02
SUB_LIGHT = 0x03
SUB_SETTINGS = 0x04
SUB_CALIBRATION = 0x05
SUB_DELAY = 0x06
SUB_WORK_MODE = 0x82

TIMER_IDX_TAG = 0x06  # fixed low nibble in timer index byte
