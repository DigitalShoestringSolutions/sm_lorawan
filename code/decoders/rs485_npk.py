import decoders.util


class rs485_npk:
    @classmethod
    def decode(cls, sensor_payload: bytes):
        """
        RS485-LB + DFRobot NPK raw payload after gateway RSSI/SNR prefix.

        Cleaned payload structure:
            [battery 2 bytes] [payload version 1 byte] [N 2] [P 2] [K 2]

        Example:
            0e0401000000210019

        Conversions:
            battery_v = battery_mV / 1000
            nitrogen_mg_kg = unsigned 16-bit big-endian
            phosphorus_mg_kg = unsigned 16-bit big-endian
            potassium_mg_kg = unsigned 16-bit big-endian
        """

        if len(sensor_payload) < 9:
            return None, {
                "error": f"Expected at least 9 sensor bytes, got {len(sensor_payload)}",
            }

        battery_v = decoders.util.uint16_be(sensor_payload[0:2]) / 1000.0

        return battery_v, {
            "payload_version": sensor_payload[2],
            "nitrogen_mg_kg": decoders.util.uint16_be(sensor_payload[3:5]),
            "phosphorus_mg_kg": decoders.util.uint16_be(sensor_payload[5:7]),
            "potassium_mg_kg": decoders.util.uint16_be(sensor_payload[7:9]),
        }
