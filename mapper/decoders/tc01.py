import decoders.util as util

class tc01:
    @classmethod
    def decode(cls, sensor_payload: bytes):

        if len(sensor_payload) < 10:
            return None, {
                "error": f"Expected at least 10 sensor bytes, got {len(sensor_payload)}"
            }

        # Battery voltage in Volts (bytes 0-1)
        battery_v = util.uint16_be(sensor_payload[0:2]) / 1000.0

        # Sensor/Thermocouple Type (byte 2)
        sensor_type = sensor_payload[2]

        # Thermocouple Temperature in °C (bytes 3-4)
        raw_temp = util.int16_be(sensor_payload[3:5])
        if raw_temp in (32767, -32768):
            temperature_c = None
        else:
            temperature_c = raw_temp / 10.0

        # Alarm & Interrupt Flags (byte 5)
        # flags = sensor_payload[5]

        # Unix Timestamp in seconds (bytes 6-9)
        # timestamp = util.uint32_be(sensor_payload[6:10])

        return battery_v, {
            "sensor_type": sensor_type,
            "temperature_c": temperature_c,
            # "flags": flags,
            # "timestamp": timestamp,
        }
