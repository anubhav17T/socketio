import json
from asyncio.log import logger

# from paho.mqtt import client as mqtt

from prevous_chat import get_previous_chat
from utils.properties import USERNAME, PASSWORD, MQTT_KEEPALIVE, MQTT_HOST, MQTT_PORT

post_response = "chatRoom/post/{}/{}"
get_request = "chatRoom/get/#"


class MqttClient:
    try:
        def __init__(self):
            try:
                # self.client = mqtt.Client(clean_session=True)
                # self.client.username_pw_set(username=USERNAME,
                #                             password=PASSWORD)
                print("################ mqtt broker called ###################################  ")

            except Exception as e:
                print("######## SOMETHING IS WRONG WITH MQTT USERNAME OR PASSWORD ##### {}".format(e))

        def clientMqtt(self):
            pass
            # self.client.connect(host=MQTT_HOST, port=MQTT_PORT,
            #                     keepalive=MQTT_KEEPALIVE)
            # return self.client

    except Exception as e:
        logger.error("################ Something is wrong with mqtt publisher################ {}".format(e))


def send_response(response, room_id, user_id, get_msg=False):
    mqtt_client_publish = MqttClient().clientMqtt()
    print(f"to find: {response}")
    if get_msg:
        data = get_previous_chat(response.get("count"), room_id, user_id)
    else:
        data = response
    # mqtt_client_publish.publish(topic=post_response.format(room_id, user_id),
    #                             payload=json.dumps(data))


def on_message(client, userdata, msg):
    print("Message received-> " + msg.topic + " " + str(msg.payload))
    room_id = str(msg.topic).split("/")[-1]
    print("the message = ", json.loads(msg.payload.decode("utf-8", "ignore")))
    response = json.loads(msg.payload.decode("utf-8", "ignore"))
    send_response(response, room_id, response.get("username"), get_msg=True)
    print("Message received-> " + msg.topic + " " + str(msg.payload))


def run_mqtt():
    pass
    # mqtt_client_subscribe = MqttClient().clientMqtt()
    # mqtt_client_subscribe.subscribe(topic=get_request)
    # mqtt_client_subscribe.on_message = on_message
    # mqtt_client_subscribe.loop_start()

# mosquitto_pub -h localhost -t chatRoom/get/ -u root -P cool  -m "{\"value1\":20,\"value2\":40}"
# mosquitto_sub -h localhost -t chatRoom/post/# -u root -P cool