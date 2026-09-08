import decoders.util as util

class ivs_ln:

    @classmethod
    def decode(cls, sensor_payload: bytes, fport: int):
        if fport != 2:
            return None, None

        if len(sensor_payload) < 6:
            return None, {
                "error": f"Expected at least 6 sensor bytes, got {len(sensor_payload)}"
            }

        # Battery voltage in Volts (bytes 0-1)
        battery_v = util.uint16_be(sensor_payload[0:2]) / 1000.0

        # Sensor metadata (bytes 2-3)
        sampling_times = sensor_payload[2]
        sampling_flags = sensor_payload[3]

        # Calculate exact byte block size based on active bitmask flags
        sample_data_len = 0
        if sampling_flags & 0x01:
            sample_data_len += 6  # Velocity
        if sampling_flags & 0x02:
            sample_data_len += 6  # Displacement
        if sampling_flags & 0x04:
            sample_data_len += 6  # Acceleration
        if sampling_flags & 0x08:
            sample_data_len += 6  # Frequency

        block_len = 2 + sample_data_len  # 2 bytes temp + active metric bytes
        samples = []
        idx = 4  # Start of sample data block

        # Loop through each sample block as defined by sampling_times
        for _ in range(max(1, sampling_times)):
            if len(sensor_payload) < idx + block_len:
                break

            # Temperature in °C (bytes 0-1 of each sample block)
            temp_c = util.int16_be(sensor_payload[idx : idx + 2]) / 10.0
            s_idx = idx + 2
            sample_data = {"temperature_c": temp_c}

            # Bit 0 (0x01): RMS Vibration Velocity X, Y, Z in mm/s
            if sampling_flags & 0x01:
                sample_data["velocity_x_mms"] = (
                    util.uint16_be(sensor_payload[s_idx : s_idx + 2]) / 100.0
                )
                sample_data["velocity_y_mms"] = (
                    util.uint16_be(sensor_payload[s_idx + 2 : s_idx + 4]) / 100.0
                )
                sample_data["velocity_z_mms"] = (
                    util.uint16_be(sensor_payload[s_idx + 4 : s_idx + 6]) / 100.0
                )
                s_idx += 6

            # Bit 1 (0x02): Peak-to-Peak Displacement X, Y, Z in µm
            if sampling_flags & 0x02:
                sample_data["displacement_x_um"] = util.uint16_be(
                    sensor_payload[s_idx : s_idx + 2]
                )
                sample_data["displacement_y_um"] = util.uint16_be(
                    sensor_payload[s_idx + 2 : s_idx + 4]
                )
                sample_data["displacement_z_um"] = util.uint16_be(
                    sensor_payload[s_idx + 4 : s_idx + 6]
                )
                s_idx += 6

            # Bit 2 (0x04): RMS Acceleration X, Y, Z in g
            if sampling_flags & 0x04:
                sample_data["acceleration_x_g"] = (
                    util.uint16_be(sensor_payload[s_idx : s_idx + 2]) / 100.0
                )
                sample_data["acceleration_y_g"] = (
                    util.uint16_be(sensor_payload[s_idx + 2 : s_idx + 4]) / 100.0
                )
                sample_data["acceleration_z_g"] = (
                    util.uint16_be(sensor_payload[s_idx + 4 : s_idx + 6]) / 100.0
                )
                s_idx += 6

            # Bit 3 (0x08): Dominant Frequency X, Y, Z in Hz
            if sampling_flags & 0x08:
                sample_data["frequency_x_hz"] = util.uint16_be(
                    sensor_payload[s_idx : s_idx + 2]
                )
                sample_data["frequency_y_hz"] = util.uint16_be(
                    sensor_payload[s_idx + 2 : s_idx + 4]
                )
                sample_data["frequency_z_hz"] = util.uint16_be(
                    sensor_payload[s_idx + 4 : s_idx + 6]
                )
                s_idx += 6

            samples.append(sample_data)
            idx += block_len

        return battery_v, samples
