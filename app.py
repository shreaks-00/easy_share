from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    logger.info(f"Serve index from {request.remote_addr}")
    return render_template('index.html')

@socketio.on('connect')
def on_connect():
    emit('update_rooms', list(active_rooms.keys()))

@socketio.on('create_room')
def handle_create(data):
    try:
        name = data.get('name', '').strip()
        pw = data.get('password', '').strip()
        if name and name not in active_rooms:
            active_rooms[name] = {"password": pw, "history": []}
            room_counts[name] = 1
            user_sessions[request.sid] = name
            join_room(name)
            emit('update_rooms', list(active_rooms.keys()), broadcast=True)
            emit('join_success', {'name': name, 'history': []})
            emit('room_status', {'count': 1}, to=name)
        else:
            emit('error', 'Room name taken or invalid!')
    except Exception as e:
        emit('error', f'Server Error: {str(e)}')

@socketio.on('join_room')
def handle_join(data):
    try:
        name = data.get('name', '').strip()
        pw = data.get('password', '').strip()
        if name in active_rooms and active_rooms[name]["password"] == pw:
            join_room(name)
            room_counts[name] = room_counts.get(name, 0) + 1
            user_sessions[request.sid] = name
            emit('join_success', {
                'name': name, 
                'history': active_rooms[name]["history"] 
            })
            emit('room_status', {'count': room_counts[name]}, to=name)
        else:
            emit('error', 'Wrong name or password!')
    except Exception as e:
        emit('error', f'Server Error: {str(e)}')

@socketio.on('send_message')
def handle_message(data):
    try:
        room = data.get('room')
        if room in active_rooms:
            # RESTRICTION: Data is only shareable when both users have joined
            if room_counts.get(room, 0) < 2:
                emit('error', 'Waiting for partner to join...')
                return

            # Support for universal files (text, image, or generic file)
            # data can now contain: text, fileData, fileName, fileType
            active_rooms[room]["history"].append(data)
            if len(active_rooms[room]["history"]) > 50:
                active_rooms[room]["history"].pop(0)
                
            emit('receive_message', data, to=room)
    except Exception as e:
        emit('error', f'Broadcast Error: {str(e)}')

@socketio.on('typing')
def handle_typing(data):
    room = data.get('room')
    is_typing = data.get('isTyping')
    emit('user_typing', {'sid': request.sid, 'isTyping': is_typing}, to=room, include_self=False)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    room = user_sessions.get(sid)
    if room:
        room_counts[room] -= 1
        current_count = room_counts[room]
        
        # Notify others in the room
        emit('room_status', {'count': current_count}, to=room)
        
        if current_count <= 0:
            active_rooms.pop(room, None)
            room_counts.pop(room, None)
            emit('update_rooms', list(active_rooms.keys()), broadcast=True)
        
        user_sessions.pop(sid, None)

if __name__ == '__main__':
    # Use 0.0.0.0 so you can access it from your phone on the same WiFi
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
