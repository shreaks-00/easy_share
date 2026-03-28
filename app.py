from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key'

# INCREASE BOTH PAYLOAD AND PACKET SIZE
# 10MB limit (10 * 1024 * 1024) to be safe for mobile uploads
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    max_http_payload_size=10 * 1024 * 1024,
    max_decode_packets_size=10 * 1024 * 1024 
)

active_rooms = {}  
room_counts = {}   
user_sessions = {} 

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def on_connect():
    emit('update_rooms', list(active_rooms.keys()))

@socketio.on('create_room')
def handle_create(data):
    name = data.get('name')
    pw = data.get('password')
    if name and name not in active_rooms:
        active_rooms[name] = {"password": pw, "history": []}
        room_counts[name] = 1
        user_sessions[request.sid] = name
        join_room(name)
        emit('update_rooms', list(active_rooms.keys()), broadcast=True)
        # Send empty history for new room
        emit('join_success', {'name': name, 'history': []})
    else:
        emit('error', 'Room name taken or invalid!')

@socketio.on('join_room')
def handle_join(data):
    name = data.get('name')
    pw = data.get('password')
    if name in active_rooms and active_rooms[name]["password"] == pw:
        join_room(name)
        room_counts[name] = room_counts.get(name, 0) + 1
        user_sessions[request.sid] = name
        # Send the existing history
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
        # Limit history to last 50 messages to prevent server crash
        active_rooms[room]["history"].append(data)
        if len(active_rooms[room]["history"]) > 50:
            active_rooms[room]["history"].pop(0)
            
        # Broadcast the message to everyone in the room
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
    # Use 0.0.0.0 so you can access it from your phone on the same WiFi
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
