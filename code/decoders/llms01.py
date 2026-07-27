import decoders.util as util

class llms01:
    @classmethod
    def decode(cls,payload:dict):
        battery_v = util.get_battery_v(payload)
        return battery_v, {
            "leaf_moisture": payload.get("Leaf_Moisture"),
            "leaf_temperature_c": payload.get("Leaf_Temperature"),
            "external_temperature_c": payload.get("Temp_DS18B20"),
            "message_type": payload.get("Message_type"),
            "interrupt_flag": payload.get("Interrupt_flag"),
        }
