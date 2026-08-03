import decoders.util as util


class sw3l:
    @classmethod
    def decode(cls, payload: dict):
        return None, {
            # "calculate_flag": payload.get("Calculate_flag"),
            # "sensor_time": payload.get("Time"),
            # "pin_status": payload.get("Pin_status"),
            # "alarm": payload.get("Alarm"),
            "water_flow_value": payload.get("Water_flow_value"),
            "total_pulse": payload.get("Total_pulse"),
        }


class sw3l_ascii:
    @classmethod
    def decode(cls, sensor_payload: bytes):

        if len(sensor_payload) < 11:
            return None, {
                "error": f"Expected at least 11 sensor bytes, got {len(sensor_payload)}"
            }

        flag_byte = sensor_payload[0]
        calculate_byte = (flag_byte & 0b11111100)>2
        total_pulse = util.uint32_be(sensor_payload[1:5]) / 1000.0

        match calculate_byte:
            case 0:
                water_flow_value = total_pulse / 450
            case 1:
                water_flow_value = total_pulse / 390
            case 2:
                water_flow_value = total_pulse / 64
            case _:
                water_flow_value = 0

        return None, {
            "total_pulse": total_pulse,
            "water_flow_value": water_flow_value,
        }
