import os
DB_name = "MolifyChat"
COLLECTION_NAME = "system_chatRoom"
DEFAULT_EXPIRE_TIME = 7 * 24 * 60 * 60 * 1000
FILE_SUFFIXS = ("pdf", "jpeg", "png", "jpg")

keysInformation ={"mongodb.auth.enabled": os.environ["mongodb.auth.enabled"],
                  "mongodb.server.url": os.environ["mongodb.server.url"]}

USERNAME = "root"
PASSWORD = "cool"
MQTT_KEEPALIVE = 100
MQTT_HOST = "localhost"
MQTT_PORT = 1883
