import decoders.util as util


class sw3l:
    @classmethod
    def decode(cls, payload: dict):
        return None, {
            "calculate_flag": payload.get("Calculate_flag"),
            "sensor_time": payload.get("Time"),
            "pin_status": payload.get("Pin_status"),
            "alarm": payload.get("Alarm"),
            "water_flow_value": payload.get("Water_flow_value"),
            "total_pulse": payload.get("Total_pulse"),
        }
