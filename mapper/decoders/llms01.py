import decoders.util as util

# class llms01:
#     @classmethod
#     def decode(cls,payload:dict):
#         battery_v = util.get_battery_v(payload)
#         return battery_v, {
#             "leaf_moisture": payload.get("Leaf_Moisture"),
#             "leaf_temperature_c": payload.get("Leaf_Temperature"),
#             # "external_temperature_c": payload.get("Temp_DS18B20"),
#             # "message_type": payload.get("Message_type"),
#             # "interrupt_flag": payload.get("Interrupt_flag"),
#         }


class llms01:
    @classmethod
    def decode(cls, sensor_payload: bytes):

        if len(sensor_payload) < 11:
            return None, {
                "error": f"Expected at least 11 sensor bytes, got {len(sensor_payload)}"
            }

        battery_v = util.uint16_be(sensor_payload[0:2]) / 1000.0

        external_temperature_c = util.int16_be(sensor_payload[2:4]) / 10
        leaf_moisture = util.uint16_be(sensor_payload[4:6]) / 10
        leaf_temperature_c = util.uint16_be(sensor_payload[6:8]) / 10

        return battery_v, {
            "leaf_moisture":leaf_moisture,
            "leaf_temperature_c": leaf_temperature_c,
            # "external_temperature_c": external_temperature_c,
        }
