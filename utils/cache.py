from utils.mongo.mongo_client import MongoConfig
from utils.properties import DB_name, COLLECTION_NAME

cache_maintainer = {}


def update_user_cache(user_id, data):
    print(data)
    if cache_maintainer.get(user_id) is None:
        cache_maintainer[user_id] = data
        return False
    else:
        return True


def get_user_details(user_id):
    return cache_maintainer.get(user_id)


chatroom_messages = {}


def update_chatroom_chats(chatroom_id, data):
    print(data)
    if chatroom_messages.get(chatroom_id) is None:
        chatroom_messages[chatroom_id] = data
        return False
    else:
        return True


def get_chatroom_chats(chatroom_id):

    data = chatroom_messages.get(chatroom_id)
    if data is None:
        data = MongoConfig().find(DB_name, COLLECTION_NAME, {"chatroomId": chatroom_id}, projection={"_id": 0})
        if data is not None:
            data["decrypted"] = False
            update_chatroom_chats(chatroom_id, data)
    return chatroom_messages.get(chatroom_id)