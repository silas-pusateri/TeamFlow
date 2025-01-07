from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from app import socketio, db
from models import Message, Channel, Thread, Reaction, UserBookmark, User
from datetime import datetime
from sqlalchemy import and_
import logging

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        try:
            current_user.is_online = True
            db.session.commit()
            emit('status_change', {
                'user_id': current_user.id,
                'status': 'online'
            }, broadcast=True)
            # Send current user information
            emit('current_user', {
                'user_id': current_user.id
            })
        except Exception as e:
            logging.error(f"Error in handle_connect: {str(e)}")
            db.session.rollback()

@socketio.on('join')
def handle_join(data):
    try:
        room = data['channel']
        join_room(room)

        # Load messages from database with proper error handling
        try:
            # Get all messages for the channel, ordered by timestamp
            messages = Message.query.filter_by(channel_id=room)\
                .order_by(Message.timestamp.asc())\
                .all()

            # Send messages in batches to avoid overwhelming the socket
            batch_size = 100
            for i in range(0, len(messages), batch_size):
                batch = messages[i:i + batch_size]
                for message in batch:
                    message_data = create_message_data(message)
                    if message_data:
                        emit('message', message_data)

        except Exception as e:
            logging.error(f"Error loading messages for channel {room}: {str(e)}")
            db.session.rollback()

    except Exception as e:
        logging.error(f"Error in handle_join: {str(e)}")
        db.session.rollback()

@socketio.on('leave')
def handle_leave(data):
    if 'channel' in data:
        leave_room(data['channel'])

def create_message_data(message):
    """Helper function to create message data dictionary with proper error handling"""
    try:
        # Get reactions for the message
        reactions = [{
            'emoji': reaction.emoji,
            'user_id': reaction.user_id,
            'user': reaction.user.username if reaction.user else 'Unknown'
        } for reaction in message.reactions]

        # Get thread messages
        threads = []
        thread_messages = Thread.query.filter_by(message_id=message.id)\
            .order_by(Thread.timestamp)\
            .all()

        for thread in thread_messages:
            thread_data = {
                'id': thread.id,
                'content': thread.content,
                'user': thread.user.username if thread.user else 'Unknown',
                'timestamp': thread.timestamp.isoformat()
            }
            threads.append(thread_data)

        # Get replies (nested messages)
        replies = []
        if message.replies:
            for reply in message.replies:
                reply_data = {
                    'id': reply.id,
                    'content': reply.content,
                    'user': reply.user.username if reply.user else 'Unknown',
                    'timestamp': reply.timestamp.isoformat()
                }
                replies.append(reply_data)

        return {
            'id': message.id,
            'content': message.content,
            'user': message.user.username if message.user else 'Unknown',
            'timestamp': message.timestamp.isoformat(),
            'is_pinned': message.is_pinned,
            'pinned_by': message.pinned_by.username if message.pinned_by else None,
            'pinned_at': message.pinned_at.isoformat() if message.pinned_at else None,
            'reactions': reactions,
            'threads': threads,
            'replies': replies,
            'parent_id': message.parent_id
        }
    except Exception as e:
        logging.error(f"Error creating message data for message {message.id}: {str(e)}")
        return None

@socketio.on('message')
def handle_message(data):
    if current_user.is_authenticated:
        try:
            # Create and save new message to database
            message = Message(
                content=data['content'],
                user_id=current_user.id,
                channel_id=data['channel_id'],
                parent_id=data.get('parent_id')  # For threaded replies
            )
            db.session.add(message)
            db.session.commit()

            # Create message data for broadcast
            message_data = create_message_data(message)
            if message_data:
                emit('message', message_data, room=data['channel_id'])

        except Exception as e:
            logging.error(f"Error in handle_message: {str(e)}")
            db.session.rollback()

@socketio.on('reaction')
def handle_reaction(data):
    if current_user.is_authenticated:
        try:
            message_id = data['message_id']
            emoji = data['emoji']
            is_thread = data.get('is_thread', False)

            # Check if user already reacted with this emoji
            existing_reaction = Reaction.query.filter(
                and_(
                    Reaction.message_id == message_id,
                    Reaction.user_id == current_user.id,
                    Reaction.emoji == emoji
                )
            ).first()

            if is_thread:
                message = Thread.query.get(message_id)
            else:
                message = Message.query.get(message_id)
                
            if not message:
                return

            if existing_reaction:
                # Remove reaction if it exists
                db.session.delete(existing_reaction)
            else:
                # Add new reaction
                reaction = Reaction(
                    emoji=emoji,
                    message_id=message_id,
                    user_id=current_user.id
                )
                db.session.add(reaction)

            db.session.commit()

            # Get channel ID to broadcast to all clients
            channel_id = None
            if is_thread:
                parent_message = Message.query.get(message.message_id)
                if parent_message:
                    channel_id = parent_message.channel_id
            else:
                channel_id = message.channel_id

            if channel_id:
                # Broadcast the reaction update
                emit('reaction_added', {
                    'message_id': message_id,
                    'emoji': emoji,
                    'user_id': current_user.id,
                    'user': current_user.username,
                    'is_thread': is_thread
                }, broadcast=True, room=channel_id)

        except Exception as e:
            logging.error(f"Error in handle_reaction: {str(e)}")
            db.session.rollback()

@socketio.on('thread_reply')
def handle_thread_reply(data):
    if current_user.is_authenticated:
        try:
            # Create and save thread message
            thread = Thread(
                message_id=data['parent_id'],
                content=data['content'],
                user_id=current_user.id
            )
            db.session.add(thread)
            db.session.commit()

            # Broadcast thread message
            thread_data = {
                'id': thread.id,
                'content': thread.content,
                'user': current_user.username,
                'parent_id': data['parent_id'],
                'timestamp': thread.timestamp.isoformat()
            }
            emit('thread_message', thread_data, room=data['channel_id'])

        except Exception as e:
            logging.error(f"Error in handle_thread_reply: {str(e)}")
            db.session.rollback()

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        try:
            current_user.is_online = False
            current_user.last_seen = datetime.utcnow()
            db.session.commit()
            emit('status_change', {
                'user_id': current_user.id,
                'status': 'offline'
            }, broadcast=True)
        except Exception as e:
            logging.error(f"Error in handle_disconnect: {str(e)}")
            db.session.rollback()

@socketio.on('create_channel')
def handle_create_channel(data):
    if current_user.is_authenticated:
        try:
            channel = Channel(
                name=data['name'],
                description=data['description'],
                created_by_id=current_user.id
            )
            db.session.add(channel)
            db.session.commit()

            # Broadcast new channel to all users
            emit('channel_created', {
                'id': channel.id,
                'name': channel.name,
                'description': channel.description,
                'created_by': current_user.username
            }, broadcast=True)
        except Exception as e:
            logging.error(f"Error in handle_create_channel: {str(e)}")
            db.session.rollback()


# Add these new socket event handlers after the existing handlers

@socketio.on('get_user_status')
def handle_get_user_status(data):
    if current_user.is_authenticated:
        try:
            username = data.get('username')
            user = User.query.filter_by(username=username).first()
            if user:
                emit('user_status', {
                    'username': user.username,
                    'is_online': user.is_online,
                    'custom_status': user.custom_status,
                    'last_seen': user.last_seen.isoformat() if user.last_seen else None
                })
        except Exception as e:
            logging.error(f"Error in handle_get_user_status: {str(e)}")

@socketio.on('update_custom_status')
def handle_update_custom_status(data):
    if current_user.is_authenticated:
        try:
            status = data.get('status', '').strip()
            if len(status) <= 100:  # Enforce maximum length
                current_user.custom_status = status
                db.session.commit()

                # Broadcast status update to all users
                emit('user_status_updated', {
                    'user_id': current_user.id,
                    'username': current_user.username,
                    'is_online': current_user.is_online,
                    'custom_status': current_user.custom_status
                }, broadcast=True)
        except Exception as e:
            logging.error(f"Error in handle_update_custom_status: {str(e)}")
            db.session.rollback()