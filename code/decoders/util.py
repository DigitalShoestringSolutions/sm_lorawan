import struct

def int32_be(raw4):
    return struct.unpack(">i", raw4)[0]


def uint32_be(raw4):
    return struct.unpack(">I", raw4)[0]


def int16_be(raw2):
    return struct.unpack(">h", raw2)[0]


def uint16_be(raw2):
    return struct.unpack(">H", raw2)[0]


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_battery_v(data):
    battery_v = None
    if "BatV" in data:
        battery_v = safe_float(data.get("BatV"))
    elif "BAT" in data:
        battery_v = safe_float(data.get("BAT"))

    return battery_v
