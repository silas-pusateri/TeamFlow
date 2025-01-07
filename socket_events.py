from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from app import socketio, db
from models import Message, Channel, Thread, Reaction, UserBookmark, User
from datetime import datetime
from sqlalchemy import and_, or_
import logging

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        try:
            current_user.is_online = True
            db.session.commit()

            # Send channel list for search filter
            channels = Channel.query.all()
            emit('channel_list', {
                'channels': [{'id': channel.id, 'name': channel.name} for channel in channels]
            })

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

        # Get thread messages with proper nesting
        threads = []
        thread_messages = Thread.query.filter_by(message_id=message.id, replied_to_id=None)\
            .order_by(Thread.timestamp)\
            .all()

        for thread in thread_messages:
            thread_data = create_thread_data(thread)
            if thread_data:
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

def create_thread_data(thread):
    """Helper function to create thread data with nested replies"""
    try:
        # Get the replied-to message content if it exists
        replied_to_content = None
        if thread.replied_to_id:
            replied_to = Thread.query.get(thread.replied_to_id)
            if replied_to:
                replied_to_content = replied_to.content[:100]  # Get first 100 chars

        thread_data = {
            'id': thread.id,
            'content': thread.content,
            'user': thread.user.username if thread.user else 'Unknown',
            'timestamp': thread.timestamp.isoformat(),
            'depth': thread.thread_depth,
            'replied_to_id': thread.replied_to_id,
            'replied_to_content': replied_to_content,  # Add content of replied-to message
            'reactions': [{
                'emoji': reaction.emoji,
                'user_id': reaction.user_id,
                'user': reaction.user.username if reaction.user else 'Unknown'
            } for reaction in thread.message.reactions],
            'replies': []
        }

        # Recursively add nested replies
        for reply in thread.replies:
            reply_data = create_thread_data(reply)
            if reply_data:
                thread_data['replies'].append(reply_data)

        return thread_data
    except Exception as e:
        logging.error(f"Error creating thread data for thread {thread.id}: {str(e)}")
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
            parent_id = data['parent_id']  # This is always the top-level message ID
            replied_to_id = data.get('replied_to_id')  # ID of immediate message being replied to
            
            # Create the thread reply
            thread = Thread(
                message_id=parent_id,  # Always the top-level message
                content=data['content'],
                user_id=current_user.id,
                replied_to_id=replied_to_id  # Store immediate reply context
            )
            db.session.add(thread)
            db.session.commit()

            # Get parent message for channel info
            parent_message = Message.query.get(parent_id)
            if not parent_message:
                raise ValueError(f"Parent message {parent_id} not found")
            
            # Get the username of the message being replied to
            replied_to_username = None
            if replied_to_id:
                replied_to_thread = Thread.query.get(replied_to_id)
                if replied_to_thread:
                    replied_to_username = replied_to_thread.user.username

            # Create thread data with proper nesting
            thread_data = create_thread_data(thread)
            if thread_data:
                thread_data.update({
                    'channel_id': parent_message.channel_id,
                    'message_id': parent_id,  # Add top-level message ID
                    'replied_to_username': replied_to_username,  # Add username for UI context
                    'parent_message_content': parent_message.content[:100]  # Add snippet of parent message
                })
                emit('thread_message', thread_data, room=thread_data['channel_id'])

        except Exception as e:
            logging.error(f"Error in handle_thread_reply: {str(e)}")
            db.session.rollback()

@socketio.on('fetch_thread_history')
def handle_fetch_thread_history(data):
    """Fetch the complete thread history for a message"""
    if current_user.is_authenticated:
        try:
            message_id = data['message_id']
            message = Message.query.get(message_id)
            if not message:
                return

            # Get all thread messages for this top-level message
            threads = Thread.query.filter_by(message_id=message_id)\
                .order_by(Thread.timestamp)\
                .all()

            thread_data = []
            for thread in threads:
                data = create_thread_data(thread)
                if data:
                    thread_data.append(data)

            emit('thread_history', {
                'message_id': message_id,
                'threads': thread_data
            })
        except Exception as e:
            logging.error(f"Error fetching thread history: {str(e)}")
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


@socketio.on('get_user_status')
def handle_get_user_status(data):
    if current_user.is_authenticated:
        try:
            username = data.get('username')
            user = User.query.filter_by(username=username).first()
            if user:
                # Get user activity stats
                stats = user.get_activity_stats()
                recent_activity = [
                    {
                        'content': msg.content,
                        'timestamp': msg.timestamp.isoformat()
                    } for msg in user.get_recent_activity()
                ]

                emit('user_status', {
                    'username': user.username,
                    'is_online': user.is_online,
                    'custom_status': user.custom_status,
                    'status_emoji': user.status_emoji,
                    'last_seen': user.last_seen.isoformat() if user.last_seen else None,
                    'role': user.role,
                    'join_date': user.join_date.isoformat(),
                    'bio': user.bio,
                    'stats': stats,
                    'recent_activity': recent_activity
                })
        except Exception as e:
            logging.error(f"Error in handle_get_user_status: {str(e)}")

@socketio.on('update_custom_status')
def handle_update_custom_status(data):
    if current_user.is_authenticated:
        try:
            status = data.get('status', '').strip()
            emoji = data.get('emoji', '').strip()

            if len(status) <= 100 and len(emoji) <= 32:  # Enforce maximum lengths
                current_user.custom_status = status
                current_user.status_emoji = emoji
                db.session.commit()

                # Get updated stats
                stats = current_user.get_activity_stats()
                recent_activity = [
                    {
                        'content': msg.content,
                        'timestamp': msg.timestamp.isoformat()
                    } for msg in current_user.get_recent_activity()
                ]

                # Broadcast status update to all users
                emit('user_status_updated', {
                    'user_id': current_user.id,
                    'username': current_user.username,
                    'is_online': current_user.is_online,
                    'custom_status': current_user.custom_status,
                    'status_emoji': current_user.status_emoji,
                    'stats': stats,
                    'recent_activity': recent_activity
                }, broadcast=True)
        except Exception as e:
            logging.error(f"Error in handle_update_custom_status: {str(e)}")
            db.session.rollback()

@socketio.on('search_messages')
def handle_search(data):
    if current_user.is_authenticated:
        try:
            keyword = data.get('keyword', '').strip()
            if not keyword:
                return

            logging.info(f"Searching for keyword: {keyword}")

            # Get filters
            user_filter = data.get('username', '').strip()
            channel_filter = data.get('channel_id')
            date_from = data.get('date_from')
            date_to = data.get('date_to')
            include_threads = data.get('include_threads', True)  # Default to True

            # Build base query
            query = Message.query

            # Apply filters
            if user_filter:
                query = query.join(User).filter(User.username.ilike(f'%{user_filter}%'))

            if channel_filter:
                query = query.filter(Message.channel_id == channel_filter)

            if date_from:
                query = query.filter(Message.timestamp >= date_from)

            if date_to:
                query = query.filter(Message.timestamp <= date_to)

            # Search in messages and threads (now always included by default)
            query = query.filter(
                or_(
                    Message.content.ilike(f'%{keyword}%'),
                    Thread.content.ilike(f'%{keyword}%')
                )
            ).join(Message.threads, isouter=True)

            messages = query.order_by(Message.timestamp.desc()).limit(50).all()

            logging.info(f"Found {len(messages)} messages matching the search")

            # Format results
            results = []
            for message in messages:
                try:
                    # Get channel name
                    channel = Channel.query.get(message.channel_id)
                    channel_name = channel.name if channel else 'Unknown Channel'

                    # Highlight the keyword in content
                    content = message.content
                    keyword_lower = keyword.lower()
                    content_lower = content.lower()

                    # Find all occurrences of the keyword
                    start_idx = 0
                    highlighted_content = ''
                    while True:
                        idx = content_lower.find(keyword_lower, start_idx)
                        if idx == -1:
                            highlighted_content += content[start_idx:]
                            break
                        highlighted_content += content[start_idx:idx]
                        highlighted_content += f'<span class="search-highlight">{content[idx:idx+len(keyword)]}</span>'
                        start_idx = idx + len(keyword)

                    results.append({
                        'id': message.id,
                        'content': highlighted_content,
                        'user': message.user.username if message.user else 'Unknown User',
                        'channel': channel_name,
                        'timestamp': message.timestamp.isoformat(),
                        'user_id': message.user_id
                    })
                except Exception as e:
                    logging.error(f"Error processing message {message.id}: {str(e)}")
                    continue

            logging.info("Sending search results to client")
            emit('search_results', {'results': results})

        except Exception as e:
            logging.error(f"Error in handle_search: {str(e)}")
            db.session.rollback()

@socketio.on('get_channel_info')
def handle_channel_info(data):
    if current_user.is_authenticated:
        try:
            channel_id = data['channel_id']
            channel = Channel.query.get(channel_id)
            
            if channel:
                creator = User.query.get(channel.created_by_id)
                message_count = Message.query.filter_by(channel_id=channel_id, parent_id=None).count()
                reply_count = Message.query.filter_by(channel_id=channel_id).filter(Message.parent_id.isnot(None)).count()

                emit('channel_info', {
                    'name': channel.name,
                    'description': channel.description,
                    'creator': creator.username if creator else 'Unknown',
                    'created_at': channel.created_at.isoformat(),
                    'message_count': message_count,
                    'reply_count': reply_count
                })

        except Exception as e:
            logging.error(f"Error in handle_channel_info: {str(e)}")
            db.session.rollback()

@socketio.on('delete_message')
def handle_delete_message(data):
    if current_user.is_authenticated:
        try:
            message_id = data['message_id']
            message = Message.query.get(message_id)

            if message and message.user_id == current_user.id:
                db.session.delete(message)
                db.session.commit()

                emit('message_deleted', {
                    'message_id': message_id
                }, room=message.channel_id)

        except Exception as e:
            logging.error(f"Error in handle_delete_message: {str(e)}")
            db.session.rollback()