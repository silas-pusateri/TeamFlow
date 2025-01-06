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
            # Get last 50 messages for the channel
            messages = Message.query.filter_by(channel_id=room)\
                .order_by(Message.timestamp.desc())\
                .limit(50)\
                .all()

            for message in reversed(messages):
                message_data = create_message_data(message)
                if message_data:
                    emit('message', message_data)

        except Exception as e:
            logging.error(f"Error loading messages for channel {room}: {str(e)}")

    except Exception as e:
        logging.error(f"Error in handle_join: {str(e)}")

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

        return {
            'id': message.id,
            'content': message.content,
            'user': message.user.username if message.user else 'Unknown',
            'timestamp': message.timestamp.isoformat(),
            'is_pinned': message.is_pinned,
            'pinned_by': message.pinned_by.username if message.pinned_by else None,
            'pinned_at': message.pinned_at.isoformat() if message.pinned_at else None,
            'reactions': reactions,
            'threads': threads
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
                channel_id=data['channel_id']
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

@socketio.on('pin_message')
def handle_pin_message(data):
    if current_user.is_authenticated:
        try:
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
        except Exception as e:
            logging.error(f"Error in handle_pin_message: {str(e)}")
            db.session.rollback()

@socketio.on('bookmark_message')
def handle_bookmark_message(data):
    if current_user.is_authenticated:
        try:
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
        except Exception as e:
            logging.error(f"Error in handle_bookmark_message: {str(e)}")
            db.session.rollback()

@socketio.on('reaction')
def handle_reaction(data):
    if current_user.is_authenticated:
        try:
            message_id = data['message_id']
            emoji = data['emoji']

            # Check if user already reacted with this emoji
            existing_reaction = Reaction.query.filter(and_(
                Reaction.message_id == message_id,
                Reaction.user_id == current_user.id,
                Reaction.emoji == emoji
            )).first()

            if existing_reaction:
                # Remove reaction if it exists
                db.session.delete(existing_reaction)
                db.session.commit()
            else:
                # Add new reaction
                reaction = Reaction(
                    emoji=emoji,
                    message_id=message_id,
                    user_id=current_user.id
                )
                db.session.add(reaction)
                db.session.commit()

            # Broadcast the reaction update
            message = Message.query.get(message_id)
            if message:
                emit('reaction_added', {
                    'message_id': message_id,
                    'emoji': emoji,
                    'user_id': current_user.id,
                    'user': current_user.username
                }, room=message.channel_id)
        except Exception as e:
            logging.error(f"Error in handle_reaction: {str(e)}")
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