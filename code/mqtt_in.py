from paho.mqtt.client import Client as MQTTClient, CallbackAPIVersion
import multiprocessing
import logging
import zmq
import json
import chevron
import time
import signal
from urllib.parse import urljoin

context = zmq.Context()
logger = logging.getLogger("main.mqtt_in")

terminate_flag = False


def graceful_signal_handler(sig, _frame):
    logger.info(
        f"Received {signal.Signals(sig).name}. Triggering graceful termination."
    )
    global terminate_flag
    terminate_flag = True
    signal.alarm(10)


class MQTTInputWrapper(multiprocessing.Process):
    def __init__(self, config, zmq_conf):
        super().__init__()

        mqtt_conf = config["mqtt_in"]
        self.url = mqtt_conf["broker"]
        self.port = int(mqtt_conf["port"])

        mqtt_conf_reconnect = mqtt_conf.get("reconnect", {})
        self.initial = mqtt_conf_reconnect.get("initial", 5)
        self.backoff = mqtt_conf_reconnect.get("backoff", 2)
        self.limit = mqtt_conf_reconnect.get("limit", 60)

        self.subscriptions = mqtt_conf.get("subscriptions", [])

        # declarations
        self.zmq_conf = zmq_conf
        self.zmq_out = None

    def do_connect(self):
        self.zmq_out = context.socket(self.zmq_conf["type"])
        if self.zmq_conf["bind"]:
            self.zmq_out.bind(self.zmq_conf["address"])
        else:
            self.zmq_out.connect(self.zmq_conf["address"])

    def mqtt_connect(self, client, first_time=False):
        timeout = self.initial
        exceptions = True
        while exceptions and terminate_flag is False:
            try:
                if first_time:
                    client.connect(self.url, self.port, 60)
                else:
                    logger.error("Attempting to reconnect...")
                    client.reconnect()
                logger.info("Connected!")
                time.sleep(self.initial)  # to give things time to settle
                exceptions = False
            except Exception:
                logger.error(f"Unable to connect, retrying in {timeout} seconds")
                time.sleep(timeout)
                if timeout < self.limit:
                    timeout = timeout * self.backoff
                else:
                    timeout = self.limit

    def on_disconnect(self, client, userdata, disconnect_flags, rc, properties=None):
        if rc != 0:
            logger.error(f"Unexpected MQTT disconnection (rc:{rc}), reconnecting...")
            self.mqtt_connect(client)

    def run(self):
        signal.signal(signal.SIGINT, graceful_signal_handler)
        signal.signal(signal.SIGTERM, graceful_signal_handler)
        self.do_connect()

        client = MQTTClient(CallbackAPIVersion.VERSION2)
        client.on_connect = self.mqtt_on_connect
        client.on_message = self.mqtt_on_message
        client.on_disconnect = self.on_disconnect

        # client.reconnect_delay_set(min_delay=self.initial, max_delay=self.limit)

        # self.client.tls_set('ca.cert.pem',tls_version=2)
        logger.info(f"connecting to {self.url}:{self.port}")
        self.mqtt_connect(client, True)

        while terminate_flag is False:
            client.loop(0.05)
        logger.info("Done")

    def mqtt_on_connect(
        self, client: MQTTClient, userdata, flags, reason_code, properties
    ):
        logger.info(f"MQTT client connected with result code {reason_code}")
        for topic in self.subscriptions:
            client.subscribe(topic)

    def mqtt_on_message(self, client: MQTTClient, userdata, msg):
        try:
            # Safely decode binary payload to string so json serialization works
            payload_str = msg.payload.decode("utf-8", errors="replace")

            output = {"topic": msg.topic, "payload": payload_str}
            logger.debug(f"Forwarding message on topic: {msg.topic}")
            self.zmq_out.send_json(output)
        except Exception as e:
            logger.error(f"Failed to process/forward MQTT message: {e}")
