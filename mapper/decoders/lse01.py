import decoders.util as util

# class lse01:
#     @classmethod
#     def decode(cls, payload: dict):
#         battery_v = util.get_battery_v(payload)
#         return battery_v, {
#             "soil_temperature_c": payload.get("Temp_SOIL"),
#             "soil_moisture": payload.get("Water_SOIL"),
#             "soil_conductivity": payload.get("Conduct_SOIL"),
#             # "external_temperature_c": payload.get("Temp_DS18B20"),
#         }


class lse01:
    @classmethod
    def decode(cls, sensor_payload: bytes):

        if len(sensor_payload) < 11:
            return None, {
                "error": f"Expected at least 11 sensor bytes, got {len(sensor_payload)}"
            }

        battery_v = util.uint16_be(sensor_payload[0:2]) / 1000.0

        external_temperature_c = util.int16_be(sensor_payload[2:4]) / 100
        soil_moisture = util.int16_be(sensor_payload[4:6]) / 100
        soil_temperature_c = util.uint16_be(sensor_payload[6:8]) / 100
        soil_conductivity = util.uint16_be(sensor_payload[8:10]) 

        return battery_v, {
            "soil_temperature_c": soil_temperature_c,
            "soil_moisture": soil_moisture,
            "soil_conductivity": soil_conductivity,
            # "external_temperature_c": external_temperature_c,
        }
