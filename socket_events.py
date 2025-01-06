from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from app import socketio, db
from models import Message, Channel, Thread, Reaction, UserBookmark
from datetime import datetime

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        current_user.is_online = True
        db.session.commit()
        emit('status_change', {
            'user_id': current_user.id,
            'status': 'online'
        }, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        current_user.is_online = False
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        emit('status_change', {
            'user_id': current_user.id,
            'status': 'offline'
        }, broadcast=True)

@socketio.on('join')
def handle_join(data):
    room = data['channel']
    join_room(room)
    emit('status', {'msg': f'{current_user.username} has joined the channel.'}, room=room)

@socketio.on('message')
def handle_message(data):
    if current_user.is_authenticated:
        message = Message(
            content=data['content'],
            user_id=current_user.id,
            channel_id=data['channel_id']
        )
        db.session.add(message)
        db.session.commit()

        emit('message', {
            'id': message.id,
            'content': message.content,
            'user': current_user.username,
            'timestamp': message.timestamp.isoformat()
        }, room=data['channel_id'])

@socketio.on('pin_message')
def handle_pin_message(data):
    if current_user.is_authenticated:
        message = Message.query.get(data['message_id'])
        if message:
            message.is_pinned = not message.is_pinned
            if message.is_pinned:
                message.pinned_at = datetime.utcnow()
                message.pinned_by_id = current_user.id
            else:
                message.pinned_at = None
                message.pinned_by_id = None
            db.session.commit()

            emit('message_pinned', {
                'message_id': message.id,
                'is_pinned': message.is_pinned,
                'pinned_by': current_user.username,
                'pinned_at': message.pinned_at.isoformat() if message.pinned_at else None
            }, room=message.channel_id)

@socketio.on('bookmark_message')
def handle_bookmark_message(data):
    if current_user.is_authenticated:
        existing_bookmark = UserBookmark.query.filter_by(
            user_id=current_user.id,
            message_id=data['message_id']
        ).first()

        if existing_bookmark:
            db.session.delete(existing_bookmark)
            is_bookmarked = False
        else:
            bookmark = UserBookmark(
                user_id=current_user.id,
                message_id=data['message_id'],
                note=data.get('note', '')
            )
            db.session.add(bookmark)
            is_bookmarked = True

        db.session.commit()

        emit('message_bookmarked', {
            'message_id': data['message_id'],
            'is_bookmarked': is_bookmarked,
            'user_id': current_user.id
        }, room=current_user.id)

@socketio.on('thread_reply')
def handle_thread_reply(data):
    if current_user.is_authenticated:
        thread = Thread(
            message_id=data['parent_id'],
            content=data['content'],
            user_id=current_user.id
        )
        db.session.add(thread)
        db.session.commit()

        emit('thread_message', {
            'id': thread.id,
            'content': thread.content,
            'user': current_user.username,
            'parent_id': data['parent_id'],
            'timestamp': thread.timestamp.isoformat()
        }, room=data['channel_id'])

@socketio.on('reaction')
def handle_reaction(data):
    if current_user.is_authenticated:
        reaction = Reaction(
            emoji=data['emoji'],
            message_id=data['message_id'],
            user_id=current_user.id
        )
        db.session.add(reaction)
        db.session.commit()

        emit('reaction_added', {
            'message_id': data['message_id'],
            'emoji': data['emoji'],
            'user_id': current_user.id
        }, broadcast=True)