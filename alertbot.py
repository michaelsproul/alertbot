#!/usr/bin/env python3

import time
import telegram
import requests
import traceback
import configparser

HTTP_TIMEOUT_SECONDS = 10.0
CONFIG_FILE = "config.ini"

def load_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    return config

def get_bot(config):
    return telegram.Bot(config["telegram"]["api_token"])

def check_lighthouse_health(config, errors):
    errors = []
    lh_health = requests.get(
        f"{config['lighthouse']['endpoint']}/lighthouse/health",
        timeout=HTTP_TIMEOUT_SECONDS
    )
    if lh_health.ok:
        health_json = lh_health.json()["data"]
        mem_percent = health_json["sys_virt_mem_percent"]

        if mem_percent > 95.0:
            errors.append(f"Memory usage at {mem_percent}%")
    else:
        errors.append(f"Error from /lighthouse/health: {lh_health.status_code}")

def check_sync_status(config, errors):
    node_health = requests.get(
        f"{config['lighthouse']['endpoint']}/eth/v1/node/health",
        timeout=HTTP_TIMEOUT_SECONDS
    )
    if node_health.status_code != 200 and node_health.status != 206:
        errors.append(f"Lighthouse not synced: {node_health.status_code}")

def check_peer_count(config, errors):
    peer_count = requests.get(
        f"{config['lighthouse']['endpoint']}/eth/v1/node/peer_count",
        timeout=HTTP_TIMEOUT_SECONDS
    )

    if peer_count.ok:
        peer_count = int(peer_count.json()["data"]["connected"])
        min_peer_count = int(config["lighthouse"]["min_peer_count"])
        max_peer_count = int(config["lighthouse"]["max_peer_count"])

        if peer_count < min_peer_count or peer_count > max_peer_count:
            errors.append(f"Bad peer count: {peer_count}")
    else:
        errors.append(f"Error from /eth/v1/node/peer_count: {lh_health.status_code}")

def check_for_errors(config, errors):
    check_lighthouse_health(config, errors)
    check_sync_status(config, errors)
    check_peer_count(config, errors)

def main():
    config = load_config()

    if config["telegram"]["api_token"].startswith('"'):
        raise Exception("Telgram API token has quotes, remove them")

    while True:
        print("Checking node health")
        errors = []

        try:
            check_for_errors(config, errors)
        except Exception as e:
            errors.append(f"Heartbeat error: {e}")

        if len(errors) > 0:
            print("BAD")
            message = "Trouble in paradise:\n\n"
            for error in errors:
                message += f"- {error}\n"
            bot = get_bot(config)
            bot.send_message(config["telegram"]["chat_id"], message)
        else:
            print("OK")

        time.sleep(int(config["alertbot"]["poll_interval_seconds"]))

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print(e)
            traceback.print_exc()
            time.sleep(10)
