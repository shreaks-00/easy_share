from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key'

# Allow up to 5MB for images to prevent mobile crashes
socketio = SocketIO(app, cors_allowed_origins="*", max_http_payload_size=5 * 1024 * 1024)

# Data storage
active_rooms = {}  # { "room_name": {"password": "...", "history": []} }
room_counts = {}   # { "room_name": int }
user_sessions = {} # { "session_id": "room_name" }

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def on_connect():
    emit('update_rooms', list(active_rooms.keys()))

@socketio.on('create_room')
def handle_create(data):
    name, pw = data.get('name'), data.get('password')
    if name and name not in active_rooms:
        active_rooms[name] = {"password": pw, "history": []}
        room_counts[name] = 1
        user_sessions[request.sid] = name
        join_room(name)
        emit('update_rooms', list(active_rooms.keys()), broadcast=True)
        emit('join_success', {'name': name, 'history': []})
    else:
        emit('error', 'Room name taken or invalid!')

@socketio.on('join_room')
def handle_join(data):
    name, pw = data.get('name'), data.get('password')
    if name in active_rooms and active_rooms[name]["password"] == pw:
        join_room(name)
        room_counts[name] += 1
        user_sessions[request.sid] = name
        emit('join_success', {
            'name': name, 
            'history': active_rooms[name]["history"] 
        })
    else:
        emit('error', 'Wrong name or password!')

@socketio.on('send_message')
def handle_message(data):
    room = data.get('room')
    if room in active_rooms:
        active_rooms[room]["history"].append(data)
        emit('receive_message', data, to=room)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    room = user_sessions.get(sid)
    if room:
        room_counts[room] -= 1
        if room_counts[room] <= 0:
            active_rooms.pop(room, None)
            room_counts.pop(room, None)
            emit('update_rooms', list(active_rooms.keys()), broadcast=True)
        user_sessions.pop(sid, None)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
