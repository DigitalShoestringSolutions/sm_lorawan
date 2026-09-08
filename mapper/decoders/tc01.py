import decoders.util as util

class tc01:
    @classmethod
    def decode(cls, sensor_payload: bytes):

        if len(sensor_payload) < 11:
            return None, {
                "error": f"Expected at least 11 sensor bytes, got {len(sensor_payload)}"
            }

        # Battery voltage in Volts (bytes 0-1)
        battery_v = util.uint16_be(sensor_payload[0:2]) / 1000.0

        # Internal sensor temperature in °C (bytes 2-3)
        internal_temperature_c = util.int16_be(sensor_payload[2:4]) / 10.0

        # External Thermocouple temperature in °C (bytes 4-5)
        raw_tc_temp = util.int16_be(sensor_payload[4:6])

        # 0x7FFF (32767) or 0x8000 indicates a disconnected probe or out-of-range reading
        if raw_tc_temp in (32767, -32768):
            thermocouple_temperature_c = None
        else:
            thermocouple_temperature_c = raw_tc_temp / 10.0

        return battery_v, {
            "internal_temperature_c": internal_temperature_c,
            "thermocouple_temperature_c": thermocouple_temperature_c,
        }
