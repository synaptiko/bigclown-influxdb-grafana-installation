#!/usr/bin/env python3

"""
BigClown gateway between USB and MQTT broker.

Usage:
  mqtt_to_influxdb [options]

Options:
  -D --debug                   Print debug messages.
  -h HOST --host=HOST          MQTT host to connect to (default is localhost).
  -p PORT --port=PORT          MQTT port to connect to (default is 1883).
  -t TOPIC --base-topic=TOPIC  Base MQTT topic (default is node).
  --influxdb-host=HOST         InfluxDB host to connect to (default is localhost).
  --influxdb-port=PORT         InfluxDB port to connect to (default is 8086).
  -v --version                 Print version.
  --help                       Show this message.
"""

import os
import sys
from logging import DEBUG, INFO
import logging as log
from docopt import docopt
import json
import time
import datetime
import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient

__version__ = '@@VERSION@@'

LOG_FORMAT = '%(asctime)s %(levelname)s: %(message)s'

DEFAULT_MQTT_HOST = 'localhost'
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_TOPIC = 'node'
DEFAULT_INFLUXDB_HOST = 'localhost'
DEFAULT_INFLUXDB_PORT = 8086


def mgtt_on_connect(client, userdata, flags, rc):
    log.info('Connected to MQTT broker with (code %s)', rc)

    database = userdata['base_topic'].strip('/')
    userdata['influx'].create_database(database)
    userdata['influx'].switch_database(database)

    client.subscribe(userdata['base_topic'] + '+/+/+/+')


def mgtt_on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
    except Exception as e:
        return

    topic = msg.topic.split('/')
    now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    if isinstance(payload, str):
        return

    if isinstance(payload, dict):
        return

    tags = {
        'device_id': topic[1],
        'dev': '/'.join(topic[2:4])
    }
    json_body = [{
        'measurement': topic[4],
        'time': now,
        'tags': tags,
        'fields': {
            'value': payload
        }
    }]

    if topic[2] == 'pir' and topic[4] == 'event-count':
        json_body.append({
            'measurement': 'movement',
            'time': now,
            'tags': tags,
            'fields': {
                'value': 1
            }
        })

    userdata['influx'].write_points(json_body)

def main():
    arguments = docopt(__doc__, version='bc-gateway %s' % __version__)
    opts = {k.lstrip('-').replace('-', '_'): v
            for k, v in arguments.items() if v}

    log.basicConfig(level=DEBUG if opts.get('debug') else INFO, format=LOG_FORMAT)

    client = InfluxDBClient(opts.get('influxdb_host', DEFAULT_INFLUXDB_HOST),
                            opts.get('influxdb_port', DEFAULT_INFLUXDB_PORT),
                            'root', 'root')

    base_topic = opts.get('base_topic', DEFAULT_MQTT_TOPIC).rstrip('/') + '/'

    mqttc = mqtt.Client(userdata={'influx': client, 'base_topic': base_topic})
    mqttc.on_connect = mgtt_on_connect
    mqttc.on_message = mgtt_on_message

    mqttc.connect(opts.get('host', DEFAULT_MQTT_HOST),
                  opts.get('port', DEFAULT_MQTT_PORT),
                  keepalive=10)
    mqttc.loop_forever()

if __name__ == '__main__':
    main()
