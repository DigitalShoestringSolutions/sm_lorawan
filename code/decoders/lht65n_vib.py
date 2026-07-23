import decoders.util


class lht65n_vib:
    @classmethod
    def decode(cls, sensor_payload: bytes):
        """
        LHT65N-VIB raw payload after gateway RSSI/SNR prefix.

        Verified deployment structure:
            [battery 2 bytes] [flag 1 byte] [mode-specific data 8 bytes]

        Example sensor payload:
            0c16060000000000000000

        Conversions:
            battery_v = battery_mV / 1000
            vib_mode = (flag >> 2) & 0x07

        For VIBMOD=1:
            bytes 3:7  = vib_count
            bytes 7:11 = work_min
        """


        if len(sensor_payload) < 11:
            return {
                    "error": f"Expected at least 11 sensor bytes, got {len(sensor_payload)}"
            }

        battery_v = decoders.util.uint16_be(sensor_payload[0:2]) / 1000.0
        flag = sensor_payload[2]

        vib_mode = (flag >> 2) & 0x07
        alarm = bool(flag & 0x01)
        tdc = bool(flag & 0x02)

        decoded_data = {
            "battery_v": battery_v,
            "vib_mode": vib_mode,
            "alarm": alarm,
            "tdc": tdc,
        }

        if vib_mode == 1:
            decoded_data["vib_count"] = decoders.util.uint32_be(sensor_payload[3:7])
            decoded_data["work_min"] = decoders.util.uint32_be(sensor_payload[7:11])
        elif vib_mode == 2:
            decoded_data["vib_count"] = decoders.util.uint32_be(sensor_payload[3:7])
            decoded_data["temperature_c"] = (
                decoders.util.int16_be(sensor_payload[7:9]) / 100.0
            )
            decoded_data["humidity_percent"] = (
                decoders.util.uint16_be(sensor_payload[9:11]) & 0x0FFF
            ) / 10.0
        elif vib_mode == 3:
            decoded_data["temperature_c"] = (
                decoders.util.int16_be(sensor_payload[3:5]) / 100.0
            )
            decoded_data["humidity_percent"] = (
                decoders.util.uint16_be(sensor_payload[5:7]) & 0x0FFF
            ) / 10.0
            decoded_data["work_min"] = decoders.util.uint32_be(sensor_payload[7:11])
        else:
            decoded_data["warning"] = f"Unsupported or unexpected VIB mode: {vib_mode}"
            decoded_data["sensor_payload_hex"] = sensor_payload.hex()

        return decoded_data
