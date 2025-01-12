from app import app, socketio
from socket_events import *  # Register socket events

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5001, debug=True, allow_unsafe_werkzeug=True)