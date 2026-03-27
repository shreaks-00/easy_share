from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key'
# Allow up to 5MB for images
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
        # 1. Update global list for everyone
        emit('update_rooms', list(active_rooms.keys()), broadcast=True)
        # 2. Tell the creator they joined and send (empty) history
        emit('join_success', {'name': name, 'history': []})
    else:
        emit('error', 'Room name taken!')

@socketio.on('join_room')
def handle_join(data):
    name, pw = data.get('name'), data.get('password')
    if name in active_rooms and active_rooms[name]["password"] == pw:
        join_room(name)
        room_counts[name] += 1
        user_sessions[request.sid] = name
        # IMPORTANT: Send the stored history ONLY to the user who just joined
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
        # Save message to the list so it persists for future joiners
        active_rooms[room]["history"].append(data)
        # Broadcast to everyone in the room (including sender)
        emit('receive_message', data, to=room)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    room = user_sessions.get(sid)
    if room:
        room_counts[room] -= 1
        if room_counts[room] <= 0:
            # If zero users left, delete room and history
            active_rooms.pop(room, None)
            room_counts.pop(room, None)
            emit('update_rooms', list(active_rooms.keys()), broadcast=True)
        user_sessions.pop(sid, None)

if __name__ == '__main__':
    # 'allow_unsafe_werkzeug=True' helps in some cloud environments
    # but for true production, 'eventlet' or 'gevent' is used automatically by socketio.run
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)