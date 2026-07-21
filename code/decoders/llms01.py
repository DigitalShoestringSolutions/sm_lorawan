import util

class llms01:
    @classmethod
    def decode(cls,payload:dict):
        battery_v = util.get_battery_v(payload)
        return {
            "battery_v": battery_v,
            "leaf_moisture": payload.get("Leaf_Moisture"),
            "leaf_temperature_c": payload.get("Leaf_Temperature"),
            "external_temperature_c": payload.get("Temp_DS18B20"),
            "message_type": payload.get("Message_type"),
            "interrupt_flag": payload.get("Interrupt_flag"),
        }

class lse01:
    @classmethod
    def decode(cls,payload:dict):
        battery_v = util.get_battery_v(payload)
        return {
            "battery_v": battery_v,
            "soil_temperature_c": payload.get("Temp_SOIL"),
            "soil_water": payload.get("Water_SOIL"),
            "soil_conductivity": payload.get("Conduct_SOIL"),
            "external_temperature_c": payload.get("Temp_DS18B20"),
            "sensor_flag": payload.get("Sensor_flag"),
            "interrupt_flag": payload.get("Interrupt_flag"),
        }
