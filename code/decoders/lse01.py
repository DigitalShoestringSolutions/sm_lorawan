import decoders.util as util

class lse01:
    @classmethod
    def decode(cls, payload: dict):
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
