import decoders.util as util
import logging

logger = logging.getLogger(__name__)


class cs01:
    @classmethod
    def decode(cls, sensor_payload: bytes):
        """
        CS01-LB/LS current monitor raw payload after gateway RSSI/SNR prefix.

        Current deployment:
            AT+RESOLUTION=0

        Conversion:
            current_A = raw / 100

        Direct mode MOD=1 payload:
            [battery 2] [CH1 2] [CH2 2] [CH3 2] [CH4 2] [alarm 1]

        Grouped continuous mode MOD=2 payload:
            [battery 2] + N groups of:
            [CH1 2] [CH2 2] [CH3 2] [CH4 2]
        """

        if len(sensor_payload) < 2:
            return None, []

        battery_v = util.uint16_be(sensor_payload[0:2]) / 1000.0

        def current_a(raw2):
            return util.uint16_be(raw2) / 100.0

        # Direct mode: one sample + alarm byte
        if len(sensor_payload) == 11:
            return battery_v, [
                {"current": current_a(sensor_payload[2:4]), "phase": "A", "offset": 0},
                {"current": current_a(sensor_payload[4:6]), "phase": "B", "offset": 0},
                {"current": current_a(sensor_payload[6:8]), "phase": "C", "offset": 0},
                {"current": current_a(sensor_payload[8:10]), "phase": "N", "offset": 0},
            ]

        # Grouped mode: battery + N groups of 8 bytes
        if len(sensor_payload) > 2 and (len(sensor_payload) - 2) % 8 == 0:
            sample_count = (len(sensor_payload) - 2) // 8
            samples = []

            for i in range(sample_count):
                start = 2 + i * 8
                samples.append(
                    {
                        "current": current_a(sensor_payload[start : start + 2]),
                        "phase": "A",
                        "offset": 1 + i - sample_count,
                    }
                )
                samples.append(
                    {
                        "current": current_a(sensor_payload[start + 2 : start + 4]),
                        "phase": "B",
                        "offset": 1 + i - sample_count,
                    }
                )
                samples.append(
                    {
                        "current": current_a(sensor_payload[start + 4 : start + 6]),
                        "phase": "C",
                        "offset": 1 + i - sample_count,
                    }
                )
                samples.append(
                    {
                        "current": current_a(sensor_payload[start + 6 : start + 8]),
                        "phase": "N",
                        "offset": 1 + i - sample_count,
                    }
                )

            return battery_v, samples

        logger.warning("Unexpected payload length/layout")
        return None, []


{"current": 1, "phase": 1, "machine": "ID"}
