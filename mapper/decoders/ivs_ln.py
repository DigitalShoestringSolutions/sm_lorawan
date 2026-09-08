import decoders.util as util

class ivs_ln:

    @classmethod
    def decode(cls, sensor_payload: bytes, fport: int):
        if (fport == 2):
            if len(sensor_payload) < 6:
                return None, {
                    "error": f"Expected at least 6 sensor bytes, got {len(sensor_payload)}"
                }

            # Battery voltage in Volts (bytes 0-1)
            battery_v = util.uint16_be(sensor_payload[0:2]) / 1000.0

            # Sensor metadata (bytes 2-3)
            sampling_times = sensor_payload[2]
            sampling_flags = sensor_payload[3]

            # Surface temperature in °C (bytes 4-5)
            temperature_c = util.int16_be(sensor_payload[4:6]) / 10.0

            data = {
                "temperature_c": temperature_c,
                "sampling_times": sampling_times,
                "sampling_flags": sampling_flags,
            }

            # Dynamic byte offset for optional vibration parameters
            idx = 6

            # RMS Vibration Velocity X, Y, Z in mm/s (6 bytes)
            if len(sensor_payload) >= idx + 6:
                data["velocity_x_mms"] = (
                    util.uint16_be(sensor_payload[idx : idx + 2]) / 100.0
                )
                data["velocity_y_mms"] = (
                    util.uint16_be(sensor_payload[idx + 2 : idx + 4]) / 100.0
                )
                data["velocity_z_mms"] = (
                    util.uint16_be(sensor_payload[idx + 4 : idx + 6]) / 100.0
                )
                idx += 6

            # Peak-to-Peak Displacement X, Y, Z in µm (6 bytes)
            if len(sensor_payload) >= idx + 6:
                data["displacement_x_um"] = util.uint16_be(sensor_payload[idx : idx + 2])
                data["displacement_y_um"] = util.uint16_be(
                    sensor_payload[idx + 2 : idx + 4]
                )
                data["displacement_z_um"] = util.uint16_be(
                    sensor_payload[idx + 4 : idx + 6]
                )
                idx += 6

            # RMS Acceleration X, Y, Z in g (6 bytes)
            if len(sensor_payload) >= idx + 6:
                data["acceleration_x_g"] = (
                    util.uint16_be(sensor_payload[idx : idx + 2]) / 100.0
                )
                data["acceleration_y_g"] = (
                    util.uint16_be(sensor_payload[idx + 2 : idx + 4]) / 100.0
                )
                data["acceleration_z_g"] = (
                    util.uint16_be(sensor_payload[idx + 4 : idx + 6]) / 100.0
                )
                idx += 6

            # Dominant Frequency X, Y, Z in Hz (6 bytes)
            if len(sensor_payload) >= idx + 6:
                data["frequency_x_hz"] = util.uint16_be(sensor_payload[idx : idx + 2])
                data["frequency_y_hz"] = util.uint16_be(sensor_payload[idx + 2 : idx + 4])
                data["frequency_z_hz"] = util.uint16_be(sensor_payload[idx + 4 : idx + 6])

            return battery_v, data
        else:
            return None, None
