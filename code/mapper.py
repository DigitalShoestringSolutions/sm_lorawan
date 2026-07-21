import multiprocessing
import zmq
import logging
import json
import re
from typing import Dict, Optional
import time, datetime
import decoders

context = zmq.Context()
logger = logging.getLogger("main.lorawan_mapper")


class LorawanMapper(multiprocessing.Process):
    def __init__(self, config, zmq_conf):
        super().__init__()

        mapper_conf = config.get("mapper", {})
        config_pattern = mapper_conf.get(
            "topic_pattern", "<gw>/<DeviceID>/<type>"
        )  # only the DeviceID matters, the rest are placeholders
        self.parser = TopicParser(config_pattern)

        self.mappings = config.get("mapping", {})

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
        logger.info("Starting")
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
                    out_topic, out_msgs = self.do_mapping(msg_topic, msg_payload)
                except Exception as e:
                    logger.error(f"Unhandled error during mapping: {e}", exc_info=True)
                    continue

                if out_topic is not None and out_msgs is not None:
                    if not isinstance(out_msgs, list):
                        out_msgs = [out_msgs]

                    for out_msg in out_msgs:
                        self.zmq_out.send_json({"topic": out_topic, "payload": out_msg})

    def do_mapping(self, topic, payload_raw):
        result = self.parser.parse(topic)
        device_id = result.get("DeviceID")

        # prefilter / early escape
        if device_id is None:
            return None, None

        # mapping on device_id
        mapping = self.mappings.get(device_id)
        if mapping is None:
            logger.warning(f"No mapping for {device_id}")
            return None, None

        out_topic = mapping["output_topic"]
        out_msg = {"identifier": mapping["identifier"]}
        mapping_type = mapping["type"]

        # 1. Ensure payload_raw is a clean string (handles both str and bytes inputs)
        if isinstance(payload_raw, bytes):
            payload_str = payload_raw.decode("utf-8", errors="replace").strip()
        else:
            payload_str = payload_raw.strip()

        envelope_type = None
        envelope_json = None
        envelope_bytes = None

        # Check if payload is a JSON object
        try:
            parsed_json = json.loads(payload_str)
            if isinstance(parsed_json, dict):  # Ensure it's a JSON dict, not a standalone number
                envelope_json = parsed_json
                envelope_type = "gateway_json"
        except (json.JSONDecodeError, TypeError):
            pass

        # If not JSON, attempt to parse as Hex string
        if not envelope_type:
            try:
                envelope_bytes = bytes.fromhex(payload_str)
                envelope_type = "ascii_hex"
            except ValueError:
                logger.error("Envelope is neither valid JSON nor hexstring")
                return None, None

        # handle envelope
        radio_prefix = {}
        match envelope_type:
            case "gateway_json":
                radio_prefix, payload, payload_type = parse_json_envelope(envelope_json)
            case "ascii_hex":
                radio_prefix, payload, payload_type = parse_bytes_envelope(envelope_bytes)

        out_msg["radio"] = radio_prefix

        # Decode payload based on types
        decoded = {}

        match (payload_type, mapping_type):
            case "bytes_payload", "lht65n_vib":
                decoded = decoders.lht65n_vib.decode(payload)
            case "bytes_payload", "rs485_npk":
                decoded = decoders.rs485_npk.decode(payload)
            case "bytes_payload", "cs01":
                decoded = decoders.cs01.decode(payload)
            case "json_payload", "llms01":
                decoded = decoders.llms01.decode(payload)
            case "json_payload", "sw3l":
                decoded = decoders.sw3l.decode(payload)
            case _:
                # default
                logger.error(
                    f"Mapping implementation not found for {payload_type},{mapping_type}"
                )
                return None, None

        # Handle single dictionary payload
        if isinstance(decoded, dict):
            out_msg.update(decoded)
            if "timestamp" not in out_msg:
                out_msg["timestamp"] = get_timestamp()
            return out_topic, out_msg

        # Handle multi-sample list payload (assuming decoded[0] is oldest, decoded[-1] is newest)
        elif isinstance(decoded, list):
            out_msgs = []
            offset_s = mapping.get("multi_sample_offset_s", 0)
            base_time = get_timestamp()  # Assumes datetime object or numeric timestamp

            num_samples = len(decoded)
            for idx, entry in enumerate(decoded):
                # Calculate offset going backwards from newest sample
                time_offset = (num_samples - 1 - idx) * offset_s
                sample_time = base_time - datetime.timedelta(seconds=time_offset)
                out_msgs.append({**out_msg, **entry, "timestamp": sample_time})

            return out_topic, out_msgs

        else:
            logger.warning("Unexpected decoded payload type")
            return None, None


def get_timestamp():
    __dt = -1 * (time.timezone if (time.localtime().tm_isdst == 0) else time.altzone)
    tz = datetime.timezone(datetime.timedelta(seconds=__dt))
    return datetime.datetime.now(tz=tz).isoformat()


class TopicParser:
    """
    Parses MQTT topics based on configurable template patterns.
    Supports placeholders formatted as {variable_name} or <variable_name>.
    """

    def __init__(self, pattern: str):
        self.pattern = pattern
        self._regex = self._compile_pattern(pattern)

    def _compile_pattern(self, pattern: str) -> re.Pattern:
        # Regex to find {var_name} or <var_name> placeholders
        placeholder_re = re.compile(r"[\{<]([a-zA-Z0-9_]+)[\}>]")

        parts = []
        last_end = 0

        for match in placeholder_re.finditer(pattern):
            # 1. Escape literal string parts so special chars (like @, ., +) aren't misparsed
            parts.append(re.escape(pattern[last_end : match.start()]))

            # 2. Replace placeholder with a named regex group matching anything up to the next '/'
            var_name = match.group(1)
            parts.append(f"(?P<{var_name}>[^/]+)")

            last_end = match.end()

        # 3. Append any trailing literal text
        parts.append(re.escape(pattern[last_end:]))

        # Anchor the regex to match the exact full string
        return re.compile(f"^{''.join(parts)}$")

    def parse(self, topic: str) -> Optional[Dict[str, str]]:
        """
        Parses an incoming topic string.
        Returns a dict of extracted parameters, or None if the topic doesn't match.
        """
        match = self._regex.match(topic)
        return match.groupdict() if match else {}


def parse_json_envelope(envelope:dict):
    radio = {}
    if "RSSI" in envelope:
        radio["rssi_dbm"] = envelope.get("RSSI")
    elif "rssi" in envelope:
        radio["rssi_dbm"] = decoders.util.safe_int(envelope.get("rssi"))

    if "SNR" in envelope:
        radio["snr_db"] = envelope.get("SNR")
    elif "snr" in envelope:
        radio["snr_db"] = decoders.util.safe_float(envelope.get("snr"))

    if "payload" in envelope and isinstance(envelope.get("payload"), str):
        try:
            payload = bytes.fromhex(envelope.get("payload"))
            payload_type = "bytes_payload"
        except ValueError:
            logger.error("payload in json envelope in invalid hexstring")
            payload = None
            payload_type = "unknown"
    else:
        payload = envelope
        payload_type = "json_payload"

    return radio , payload, payload_type


def parse_bytes_envelope(envelope: bytes):
    """
    Raw/ASCII messages from the Dragino gateway have been observed as:

        [4 bytes RSSI signed int32] [4 bytes SNR*10 signed int32] [sensor payload...]

    Example:
        ffffff93 0000000f 0e0401000000210019

    Decodes to:
        RSSI = -109 dBm
        SNR  = 1.5 dB
    """
    radio = {}
    sensor_payload = envelope
    
    if len(envelope) >= 8:
        radio = {
            "rssi_dbm": decoders.util.int32_be(envelope[0:4]),
            "snr_db": decoders.util.int32_be(envelope[4:8]) / 10.0,
        }
        sensor_payload = envelope[8:]
    
    return radio, sensor_payload, "bytes_payload"
