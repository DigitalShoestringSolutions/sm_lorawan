import multiprocessing
import zmq
import logging
import json
import re
import base64
from typing import Dict, Optional
import time, datetime
import decoders
from dataclasses import dataclass, asdict

context = zmq.Context()
logger = logging.getLogger("main.lorawan_mapper")


@dataclass
class MQTTMessage:
    topic: str | None = None
    payload: str | None = None
    retain: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


DECODER_MAPPINGS = {
    "lht65n_vib": decoders.lht65n_vib,
    "rs485_npk": decoders.rs485_npk,
    "cs01": decoders.cs01,
    "llms01": decoders.llms01,
    "lse01": decoders.lse01,
    "sw3l": decoders.sw3l,
    "s31b": decoders.s31b,
}

TOPIC_MAPPINGS = {
    "lht65n_vib": "vibration/{{identifier}}",
    "rs485_npk": "npk/{{identifier}}",
    "cs01": "power_monitoring/{{identifier}}",
    "llms01": "leaf_moisture/{{identifier}}",
    "lse01": "soil_moisture/{{identifier}}",
    "sw3l": "flow/{{identifier}}",
    "s31b": "temperature/{{identifier}}",
}


class LorawanMapper(multiprocessing.Process):
    def __init__(self, config, zmq_conf):
        super().__init__()
        
        self.config = config.get("mapper",[])

        # declarations
        self.zmq_conf = zmq_conf
        self.zmq_in = None
        self.zmq_out = None

    def do_connect(self):
        self.zmq_in = context.socket(self.zmq_conf["in"]["type"])
        if self.zmq_conf["in"]["bind"]:
            self.zmq_in.bind(self.zmq_conf["in"]["address"])
        else:
            self.zmq_in.connect(self.zmq_conf["in"]["address"])

        self.zmq_out = context.socket(self.zmq_conf["out"]["type"])
        if self.zmq_conf["out"]["bind"]:
            self.zmq_out.bind(self.zmq_conf["out"]["address"])
        else:
            self.zmq_out.connect(self.zmq_conf["out"]["address"])

    def run(self):
        logger.info("Starting ChirpStack LoRaWAN Mapper")
        self.do_connect()
        logger.info("ZMQ Connected")
        run = True
        while run:
            while self.zmq_in.poll(50, zmq.POLLIN):
                try:
                    msg = self.zmq_in.recv(zmq.NOBLOCK)
                    msg_json = json.loads(msg)
                    msg_topic = msg_json["topic"]
                    msg_payload = msg_json["payload"]
                except (zmq.ZMQError, json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.error(f"Malformed or unreadable incoming ZMQ packet: {e}")
                    continue

                try:
                    outbound_msgs = self.do_mapping(msg_topic, msg_payload)
                except Exception as e:
                    logger.error(f"Unhandled error during mapping: {e}", exc_info=True)
                    continue

                for out_msg in outbound_msgs:
                    if out_msg.topic is not None and out_msg.payload is not None:
                        self.zmq_out.send_json(out_msg.to_dict())

    def do_mapping(self, topic, payload_raw) -> list[MQTTMessage]:
        outbound_msgs = []

        # 1. Clean payload raw input
        if isinstance(payload_raw, bytes):
            payload_str = payload_raw.decode("utf-8", errors="replace").strip()
        else:
            payload_str = payload_raw.strip()

        # 2. Parse JSON envelope
        try:
            chirpstack_json = json.loads(payload_str)
            if not isinstance(chirpstack_json, dict):
                return []
        except (json.JSONDecodeError, TypeError):
            logger.error("Incoming MQTT payload is not a valid JSON object")
            return []

        # 3. Extract ChirpStack specific fields
        device_info = chirpstack_json.get("deviceInfo", {})
        msg_timestamp = chirpstack_json.get("time")

        # extract identifier and device_type
        identifier = device_info.get("deviceName")

        tags = device_info.get("tags", {})
        device_type = tags.get("device_type")

        if not identifier or not device_type:
            logger.warning(
                f"Missing deviceName or device_type tag for DevEUI: {device_info.get('devEui')}"
            )
            return []

        # handle radio strength
        rx_info = chirpstack_json.get("rxInfo")
        radio_strength= parse_chirpstack_rxInfo(rx_info)

        outbound_msgs.append(
            MQTTMessage(
                "radio/{{identifier}}",
                {
                    "identifier": identifier,
                    "timestamp": msg_timestamp,
                    **radio_strength,
                },
                retain=True,
            )
        )

        # 4. extract lora payload
        if "data" in chirpstack_json and chirpstack_json["data"]:
            try:
                lora_payload_bytes = base64.b64decode(chirpstack_json["data"])
            except Exception as e:
                logger.warning(f"Failed to decode base64 ChirpStack payload: {e}")
                return outbound_msgs
        else:
            logger.warning("'data' field not present in ChirpStack payload")
            return outbound_msgs

        # 5. Decode payload based on device_type
        decoder_module = DECODER_MAPPINGS.get(device_type)
        if decoder_module is None:
            logger.error(
                f"Mapping implementation not found for device_type: {device_type}"
            )
            return outbound_msgs

        battery_v, decoded = decoder_module.decode(lora_payload_bytes)

        # 6. Send battery message
        if battery_v is not None:
            outbound_msgs.append(
                MQTTMessage(
                    "battery/{{identifier}}",
                    {
                        "identifier": identifier,
                        "timestamp": msg_timestamp,
                        "battery_v": battery_v,
                    },
                    retain=True,
                )
            )

        # 7. Handle output messages
        topic_template = TOPIC_MAPPINGS.get(device_type)
        if topic_template is None:
            topic_template = "telemetry/{{identifier}}"
            logger.warning(f"No topic mapping for device type {device_type} - falling back to '{topic_template}'")


        device_type_conf = self.config.get(device_type,{})

        out_msg = {"identifier": identifier}

        identifier_tag = device_type_conf.get("identifier_tag", None)
        if identifier_tag is not None:
            out_msg[identifier_tag] = identifier

        # Handle single dictionary payload
        if isinstance(decoded, dict):
            out_msg.update(decoded)
            if "timestamp" not in out_msg:
                out_msg["timestamp"] = msg_timestamp
            outbound_msgs.append(MQTTMessage(topic_template, out_msg))
            return outbound_msgs

        # Handle multi-sample list payload (assuming decoded[0] is oldest, decoded[-1] is newest)
        elif isinstance(decoded, list):
            offset_s = int(device_type_conf.get("multi_sample_offset_s", 0))
            base_time = datetime.datetime.fromisoformat(msg_timestamp)

            for entry in decoded:
                # Calculate offset going backwards from newest sample
                offset_idx = entry.pop("offset", 0)
                time_offset = offset_idx * offset_s
                sample_time = base_time - datetime.timedelta(seconds=time_offset)
                outbound_msgs.append(
                    MQTTMessage(
                        topic_template,
                        {**out_msg, **entry, "timestamp": sample_time.isoformat()},
                    )
                )
            return outbound_msgs

        else:
            logger.warning("Unexpected decoded payload type")
            return []


def parse_chirpstack_rxInfo(rx_info_list: list[dict]):
    """
    Extracts radio metrics (RSSI/SNR) and payload from a ChirpStack v4 uplink event.
    """

    # Extract gateway radio metadata (from best/first gateway in rxInfo)
    if rx_info_list and isinstance(rx_info_list, list):
        radio = {}
        best_rx = rx_info_list[0]
        if "rssi" in best_rx:
            radio["rssi_dbm"] = int(best_rx["rssi"])
        if "snr" in best_rx:
            radio["snr_db"] = float(best_rx["snr"])
        return radio
    return None
