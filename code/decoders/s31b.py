import decoders.util as util


class s31b:
    @classmethod
    def decode(cls, payload: dict):
        battery_v = util.get_battery_v(payload)
        return battery_v, {
            "temperature_c": payload.get("TempC_SHT"),
            "humidity_percent": payload.get("Hum_SHT"),
        }

class s31b_ascii:
    @classmethod
    def decode(cls, payload: bytes):
        pass