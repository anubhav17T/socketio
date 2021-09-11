import os
import time
from pathlib import Path

from flask import Flask, request, flash, render_template, url_for
from flask_socketio import SocketIO, join_room, leave_room
from werkzeug.utils import redirect, secure_filename

from utils.cache import update_chatroom_chats, get_chatroom_chats
from utils.common import translate_message_for_mongo, upload_to_s3, return_response, allowed_file
from utils.messageEncoder import translateMessage
from utils.mongo.mongo_client import MongoConfig
from utils.properties import DB_name
from utils.properties import FILE_SUFFIXS
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = os.getcwd() + "/images/"
ALLOWED_EXTENSIONS = FILE_SUFFIXS

Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


socketio = SocketIO(app, cors_allowed_origins="*")


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


@app.route('/create_chatroom', methods=['POST'])
def create_chatroom():
    if request.method == "POST":
        try:
            room_id: str = request.form.get("chatroomId")
            if room_id is None:
                return return_response({}, "roomid is none", 400)
            doctor: str = request.form.get("doctorId")
            if doctor is None:
                return return_response({}, "doctor id is none", 400)
            client: str = request.form.get("clientId")
            if client is None:
                return return_response({}, "client id is none", 400)
            # if get_chatroom_chats(room_id) is not None:
            #     return return_response({}, "room already exist", 200)
            else:
                current_time = time.time()
                to_save = {"chatroomId": room_id,
                           "doctorId": doctor,
                           "clientId": client,
                           "createdAt": int(current_time * 1000),
                           "messages": []}
                update_chatroom_chats(room_id, to_save)
                MongoConfig().insert(DB_name, room_id, to_save)
                return return_response(to_save, "Success", code=200)
        except Exception as e:
            print(f"error due to {e}")
            return_response({"error": f"e"}, f"e", 400)


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
            if chat is None:
                chat = MongoConfig().find(DB_name, room_id, {"chatroomId": room_id})
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
                MongoConfig().update(DB_name, room_id, {"chatroomId": room_id},
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
        room_id = request.args.get("chatroomId")
        user_name = request.args.get("userId")
        count: int = request.args.get("count")
        messages = get_chatroom_chats(room_id)
        if messages is None:
            response = MongoConfig().find(DB_name, room_id, {"chatroomId": room_id})
            if response is not None and len(response) > 0:
                for i in response[0].get("messages"):
                    temp_message = i.get("message")
                    i["message"] = translateMessage(room_id, temp_message, 'decrypt')
                update_chatroom_chats(room_id, response[0])
                messages = response[0]
            else:
                return return_response([], "chatroom not found", 200)
        final_message = []
        if messages is not None:
            for i in messages.get("messages")[-50 * count:]:
                if i.get("sender") == user_name:
                    i["sender"] = "you"
                final_message.append(i)
            # template = get_template("index_chatroom.html")
            # return HttpResponse(
            #     template.render(
            #         {'userName': user_name, 'messages': final_message},
            #         request))
        else:
            return return_response([], "chatroom not found", 200)
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
                return return_response({}, "room id is none", 400)
            sender: str = data.get("username")
            if sender is None:
                return return_response({}, "senderId is none", 400)
            chat = get_chatroom_chats(room_id)
            if chat is None:
                chat = MongoConfig().find(DB_name, room_id, {"chatroomId": room_id})
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
                MongoConfig().update(DB_name, room_id, {"chatroomId": room_id},
                                     {"$push": {"messages": temp_data}})
                socketio.emit('receive_message', data, room=data['room'])
        except Exception as e:
            return return_response({"error": str(e)}, str(e), 400)


@socketio.on('join_room')
def handle_join_room_event(data):
    app.logger.info("{} has joined the room {}".format(data['username'], data['room'], data['accountType']))

    to_search = {"chatroomId": data.get("room")}
    if data['accountType'] == "doctor":
        to_search["doctorId"] = data['username']

        if MongoConfig().find(DB_name, data.get("room"), to_search) is not None:
            MongoConfig().update(DB_name, data.get("room"),
                                 to_search,
                                 {"$push": {"history": {"checkIn": int(time.time() * 1000)}}})
    join_room(data['room'])
    socketio.emit('join_room_announcement', data, room=data['room'])


@socketio.on('typing')
def handle_join_room_event(data):
    app.logger.info("{} is typing in room {}".format(data['username'], data['room'], data['accountType']))
    socketio.emit('person_typing', data, room=data['room'])


@socketio.on('leave_room')
def handle_leave_room_event(data):
    app.logger.info("{} has left the room {}".format(data['username'], data['room'], data['accountType']))
    print("leave room")
    to_search = {"chatroomId": data.get("room")}
    if data['accountType'] == "doctor":
        to_search["doctorId"] = data['username']
    elif data['accountType'] == "client":
        to_search["clientId"] = data['username']
    if data.get("room") is not None:
        MongoConfig().update(DB_name, data.get("room"), to_search,
                             {"$push": {"history": {"checkOut": int(time.time() * 1000)}}})
    leave_room(data['room'])
    socketio.emit('leave_room_announcement', data, room=data['room'])


if __name__ == '__main__':
    socketio.run(app, debug=True)
