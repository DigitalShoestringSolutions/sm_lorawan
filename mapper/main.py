# packages
import signal
import tomli
import time
import logging
import argparse
import zmq
import sys
import os

# local
import config_manager
import mapper
import mqtt_out
import mqtt_in

logger = logging.getLogger("main")
terminate_flag = False


def create_building_blocks(config):
    bbs = {}

    mqtt_in_outbound = {
        "type": zmq.PUSH,
        "address": "tcp://127.0.0.1:4000",
        "bind": True,
    }

    mapper_in = {"type": zmq.PULL, "address": "tcp://127.0.0.1:4000", "bind": False}
    mapper_out = {"type": zmq.PUSH, "address": "tcp://127.0.0.1:4001", "bind": True}
    mqtt_out_inbound = {
        "type": zmq.PULL,
        "address": "tcp://127.0.0.1:4001",
        "bind": False,
    }

    bbs["mqtt_in"] = {
        "class": mqtt_in.MQTTInputWrapper,
        "args": [config, mqtt_in_outbound],
    }
    bbs["mapper"] = {
        "class": mapper.LorawanMapper,
        "args": [config, {"in": mapper_in, "out": mapper_out}],
    }
    bbs["mqtt_out"] = {
        "class": mqtt_out.MQTTServiceWrapper,
        "args": [config, mqtt_out_inbound],
    }

    logger.debug(f"bbs {bbs}")
    return bbs


def start_building_blocks(bbs):
    for key in bbs:
        start_building_block(bbs[key])


def start_building_block(bb):
    cls = bb["class"]
    args = bb["args"]

    process = cls(*args)

    process.start()
    bb["process"] = process


def monitor_building_blocks(bbs):
    while True:
        time.sleep(1)
        if terminate_flag:
            logger.info("Terminating gracefully")
            for key in bbs:
                process = bbs[key]["process"]
                process.join()
            return

        for key in bbs:
            process = bbs[key]["process"]
            if process.is_alive() is False:
                logger.warning(
                    f"Building block {key} stopped with exit: {process.exitcode}"
                )
                logger.info(f"Restarting Building block {key}")
                start_building_block(bbs[key])


def graceful_signal_handler(sig, _frame):
    logger.info(
        f"Received {signal.Signals(sig).name}. Triggering graceful termination."
    )
    global terminate_flag
    terminate_flag = True
    signal.alarm(10)


def harsh_signal_handler(sig, _frame):
    logger.debug(f"Received {signal.Signals(sig).name}.")
    if terminate_flag:
        logger.error(
            f"Failed to terminate gracefully before timeout - hard terminating"
        )
        sys.exit(0)


def handle_args():
    levels = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }
    parser = argparse.ArgumentParser(
        description="Validate config file for sensing data collection service module.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--log",
        choices=["debug", "info", "warning", "error"],
        help="Log level",
        default="info",
        type=str,
    )
    parser.add_argument("--module_config", help="Module config file", type=str)
    parser.add_argument("--user_config", help="User config file", type=str)
    args = parser.parse_args()

    log_level = levels.get(args.log, logging.INFO)
    module_conf_file = args.module_config
    user_conf_file = args.user_config

    return module_conf_file, user_conf_file, log_level


if __name__ == "__main__":
    module_conf_file, user_conf_file, log_level = handle_args()
    logging.basicConfig(level=log_level)
    conf = config_manager.get_config(module_conf_file, user_conf_file)

    if conf.get(
        "module_enabled", True
    ):  # in case this feature is not used in any config files, start up anyway
        signal.signal(signal.SIGINT, graceful_signal_handler)
        signal.signal(signal.SIGTERM, graceful_signal_handler)
        signal.signal(signal.SIGALRM, harsh_signal_handler)

        bbs = create_building_blocks(conf)
        start_building_blocks(bbs)
        monitor_building_blocks(bbs)

    else:
        logger.info(
            "Sensing module is disabled, sleeping for an hour before restarting"
        )
        time.sleep(3600)

    logger.info("Done")
