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
    def decode(cls, sensor_payload: bytes):

        if len(sensor_payload) < 11:
            return None, {
                "error": f"Expected at least 11 sensor bytes, got {len(sensor_payload)}"
            }

        battery_v = util.uint16_be(sensor_payload[0:2]) / 1000.0

        temperature = util.int16_be(sensor_payload[7:9]) / 10
        humidity = util.uint16_be(sensor_payload[9:11]) / 10
        # alarm = sensor_payload[6]
        # timesync_offset = sensor_payload[2:6]

        return battery_v, {
            "temperature_c": temperature,
            "humidity_percent": humidity,
        }
