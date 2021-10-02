import datetime
import json
import os
import time
from asyncio.log import logger
from concurrent.futures.thread import ThreadPoolExecutor
from pathlib import Path
from flask import Flask, request, flash, render_template, url_for
from flask_socketio import SocketIO, join_room, leave_room
from werkzeug.utils import redirect, secure_filename
from prevous_chat import get_previous_chat
from utils.cache import update_chatroom_chats, get_chatroom_chats
from utils.common import translate_message_for_mongo, upload_to_s3, return_response, allowed_file, error_message
from utils.messageEncoder import translateMessage
from utils.mongo.mongo_client import MongoConfig
from utils.mqtt import send_response, run_mqtt
from utils.properties import DB_name, COLLECTION_NAME
from utils.properties import FILE_SUFFIXS
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
UPLOAD_FOLDER = os.getcwd() + "/images/"
ALLOWED_EXTENSIONS = FILE_SUFFIXS

Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
socketio = SocketIO(app, cors_allowed_origins="*")


def before_requests(application):
    with application.app_context():
        thread = ThreadPoolExecutor(3)
        thread.submit(run_mqtt)
        thread.shutdown(wait=True)


@app.before_first_request
def test():
    print("hello guys")
    before_requests(app)


@app.route('/')
def home():
    return render_template("index.html")


@app.route('/chat')
def chat():
    username = request.args.get('username')
    room = request.args.get('room')
    account = request.args.get('accountType')

    if username and room:
        return render_template('chat.html', username=username, room=room, accountType=account)
    else:
        return redirect(url_for('home'))


@app.route("/get_config", methods=["GET"])
def get_config():
    import os
    return return_response({"data": os.environ["mongodb.server.url"]})


@app.route('/create_chatroom', methods=['POST'])
def create_chatroom():
    if request.method == "POST":
        try:
            content = request.json
            logger.info("###### CONTENT {}".format(content))
            doctor: str = content.get("doctorId")
            if doctor is None:
                return return_response({}, "doctor id is none", 400)
            client: str = content.get("clientId")
            if client is None:
                return return_response({}, "client id is none", 400)
            room_id = f"{doctor}_{client}"
            if get_chatroom_chats(room_id) is not None:
                return return_response({}, "room already exist", 200)
            else:
                to_save = {"chatroomId": room_id,
                           "doctorId": doctor,
                           "clientId": client,
                           "createdAt": str(datetime.datetime.now()),
                           "messages": []}
                update_chatroom_chats(room_id, to_save)
                MongoConfig().insert(DB_name, COLLECTION_NAME, to_save)
                to_save.pop("_id")
                return return_response(to_save, "Success", code=200)
        except Exception as e:
            print(f"error due to {e}")
            return return_response({"error": f"{e}"}, f"{e}", 400)


@app.route('/update_message', methods=['POST'])
def update_chat():
    if request.method == "POST":
        try:
            room_id: str = request.form.get("chatroomId")
            if room_id is None:
                return return_response({}, "room id is none", 400)
            sender: str = request.form.get("sender")
            if sender is None:
                return return_response({}, "senderId is none", 400)
            chat = get_chatroom_chats(room_id)
            timestamp = time.time() * 1000
            data = {"sender": sender,
                    "message": request.form.get("message"),
                    "time": timestamp}
            if chat is not None:
                if 'file' not in request.files:
                    flash('No file part')
                    return redirect(request.url)
                files = []
                for file in request.files.getlist('file'):

                    # If the user does not select a file, the browser submits an
                    # empty file without a filename.
                    if file.filename == '':
                        flash('No selected file')
                        return redirect(request.url)
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(file_path)
                        files.append({"type": file.content_type,
                                      "url": upload_to_s3(None, file_path)})
                    else:
                        return return_response({"fileName": file.name}, "file does not support", 400)
                    data["isFile"] = files
                messages = chat.get("messages")
                messages.append(data)
                chat["messages"] = messages
                update_chatroom_chats(room_id, chat)
                data['message'] = translate_message_for_mongo(room_id, request.form.get("message"))
                MongoConfig().update(DB_name, COLLECTION_NAME, {"chatroomId": room_id},
                                     {"$push": {"messages": data}})
                return return_response({}, "message_updated", 200)
        except Exception as e:
            print(f"error due to {e}")
            return return_response({"error": f"{e}"}, f"{e}", 400)
        else:
            return return_response({}, "room does not exist", 400)


@app.route('/getChat', methods=['GET'])
def get_chat():
    try:
        # todo use skip and limit for get data
        room_id = request.args.get("roomId")
        user_name = request.args.get("id")
        count: int = request.args.get("count")
        logger.info(f"Get chat details for {room_id}, {user_name}, {count}")
        data = get_previous_chat(count, room_id, user_name)
        return return_response(data, "Success", 200)
    except Exception as e:
        return return_response({"error": str(e)}, str(e), 400)


@app.route('/getChats', methods=['GET'])
def get_chats():
    try:
        user_type = request.args.get("type")
        user_name = request.args.get("id")
        if user_type == "doctor":
            to_search = {"doctorId": user_name}
        else:
            to_search = {"clientID": user_name}
        list_of_chats = list(MongoConfig().find_all(DB_name, COLLECTION_NAME, to_search,
                                                    projection={"_id": 0, "history": 0, "messages": {"$slice": -1}}))
        for current_chat in list_of_chats:
            if len(current_chat.get("messages")) > 0:
                current_chat.get("messages")[0]["message"] = translateMessage(current_chat.get("chatroomId"),
                                                                              current_chat.get("messages")[0].get(
                                                                                  "message"), 'decrypt')
                current_chat["messages"] = current_chat.get("messages")[0]

        return return_response(list_of_chats,message="Please find recent chats")
    except Exception as e:
        return return_response({"error": str(e)}, str(e), 400)


@socketio.on('send_message')
def handle_send_message_event(data):
    app.logger.info("{} has sent message to the room {}: {}".format(data['username'],
                                                                    data['room'],
                                                                    data['message']))

    if data.get("room") is not None:
        try:
            room_id: str = data.get("room")
            if room_id is None:
                send_response(error_message("ROOM_ID MISMATCH", "SEND_MESSAGE", "room id does not exist", 400),
                              data['room'], data['username'])
            sender: str = data.get("username")
            if sender is None:
                send_response(error_message("SENDER_ID MISMATCH", "SEND_MESSAGE", "sender id does not exist", 400),
                              data['room'], data['username'])
            chat = get_chatroom_chats(room_id)
            if chat is None:
                chat = MongoConfig().find(DB_name, COLLECTION_NAME, {"chatroomId": room_id})

            if chat is not None:
                timestamp = time.time() * 1000
                temp_data = {"sender": sender,
                             "message": data.get("message"),
                             "time": timestamp}
                messages = chat.get("messages")
                messages.append(data)
                chat["messages"] = messages
                update_chatroom_chats(room_id, chat)
                temp_data['message'] = translate_message_for_mongo(room_id, data.get("message"))
                MongoConfig().update(DB_name, COLLECTION_NAME, {"chatroomId": room_id},
                                     {"$push": {"messages": temp_data}})
                socketio.emit('receive_message', data, room=data['room'])
        except Exception as e:
            send_response(error_message(e.__str__(), "SEND_MESSAGE", "Something went wrong broken pipeline"),
                          data['room'], data['username'])


@socketio.on('join_room')
def handle_join_room_event(data):
    app.logger.info("{} has joined the room {} {}".format(data['username'], data['room'], data['accountType']))
    try:
        to_search = {"chatroomId": data.get("room")}
        if data['accountType'] == "doctor":
            to_search["doctorId"] = data['username']
            if to_search.get("doctorId") is not None:
                if MongoConfig().find(DB_name, COLLECTION_NAME, to_search) is not None:
                    MongoConfig().update(DB_name, COLLECTION_NAME,
                                         to_search,
                                         {"$push": {"history": {"checkIn": int(time.time() * 1000)}}})
                    join_room(data['room'])
                    socketio.emit('join_room_announcement', data, room=data['room'])
                else:
                    send_response(error_message("ROOM_ID MISMATCH", "JOIN_ROOM", "room id does not exist", 400),
                                  data['room'], data['username'])
                    logger.info(" room id does not exist")
        elif data['accountType'] == "client":
            to_search["clientId"] = data['username']
            if MongoConfig().find(DB_name, COLLECTION_NAME, to_search) is not None:
                join_room(data['room'])
                socketio.emit('join_room_announcement', data, room=data['room'])
            else:
                send_response(error_message("ROOM_ID MISMATCH", "JOIN_ROOM", "room id does not exist", 400),
                              data['room'], data['username'])
                logger.info(" room id does not exist")
        else:
            send_response(error_message("ACCOUNT TYPE MISMATCH", "JOIN_ROOM", "accountType does not match", 400),
                          data['room'], data['username'])
            logger.info("accountType does not match")
    except Exception as e:
        send_response(error_message(e.__str__(), "JOIN_ROOM", "Something went wrong broken pipeline"), data['room'],
                      data['username'])


@socketio.on('typing')
def handle_join_room_event(data):
    app.logger.info("{} is typing in room {}".format(data['username'], data['room'], data['accountType']))
    if MongoConfig().find(DB_name, COLLECTION_NAME, {"chatroomId": data.get("room")}) is not None:
        socketio.emit('person_typing', data, room=data['room'])
    else:
        send_response(error_message("ROOM_ID MISMATCH", "TYPING", "room does not exist", 400), data['room'],
                      data['username'])
        logger.info("room does not exist")


@socketio.on('leave_room')
def handle_leave_room_event(data):
    app.logger.info("{} has left the room {}".format(data['username'], data['room'], data['accountType']))
    try:
        print("leave room")
        to_search = {"chatroomId": data.get("room")}
        if data['accountType'] == "doctor":
            to_search["doctorId"] = data['username']
            if to_search.get("doctorId") is not None:
                if MongoConfig().find(DB_name, COLLECTION_NAME, to_search) is not None:
                    MongoConfig().update(DB_name, COLLECTION_NAME, to_search,
                                         {"$push": {"history": {"checkOut": int(time.time() * 1000)}}})
                    leave_room(data['room'])
                    socketio.emit('leave_room_announcement', data, room=data['room'])
                else:
                    send_response(error_message("ROOM_ID MISMATCH", "LEAVE_ROOM", "room id does not exist", 400),
                                  data['room'], data['username'])
                    logger.info(" room id does not exist")
        elif data['accountType'] == "client":
            to_search["clientId"] = data['username']
            if MongoConfig().find(DB_name, COLLECTION_NAME, to_search) is not None:
                leave_room(data['room'])
                socketio.emit('leave_room_announcement', data, room=data['room'])
            else:
                send_response(error_message("ROOM_ID MISMATCH", "LEAVE_ROOM", "room id does not exist", 400),
                              data['room'], data['username'])
                logger.info("room id does not exist")
        else:
            send_response(error_message("ACCOUNT TYPE MISMATCH", "LEAVE_ROOM", "accountType does not match", 400),
                          data['room'], data['username'])
            logger.info("accountType does not match")
    except Exception as e:
        send_response(error_message(e.__str__(), "LEAVE_ROOM", "Something went wrong broken pipeline"), data['room'])


if __name__ == '__main__':
    socketio.run(app, debug=True)
