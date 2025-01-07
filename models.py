from datetime import datetime
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_online = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50), default="Available")
    custom_status = db.Column(db.String(100))
    status_emoji = db.Column(db.String(32))  # New: Status emoji
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    role = db.Column(db.String(20), default="member")  # New: User role
    join_date = db.Column(db.DateTime, default=datetime.utcnow)  # New: Join date
    bio = db.Column(db.String(500))  # New: User bio
    messages = db.relationship('Message', backref='user', lazy=True, foreign_keys='Message.user_id')
    pinned_messages = db.relationship('Message', backref='pinned_by', lazy=True, foreign_keys='Message.pinned_by_id')
    bookmarks = db.relationship('UserBookmark', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_activity_stats(self):
        """Get user activity statistics"""
        # Get distinct channels the user has posted in
        channels_joined = db.session.query(Message.channel_id)\
            .filter(Message.user_id == self.id)\
            .distinct()\
            .count()
            
        return {
            'total_messages': len(self.messages),
            'reactions_given': len(self.reactions),
            'channels_joined': channels_joined,
            'threads_participated': len(set(thread.message_id for thread in self.thread_messages))
        }

    def get_recent_activity(self, limit=5):
        """Get recent activity summary"""
        recent_messages = Message.query.filter_by(user_id=self.id)\
            .order_by(Message.timestamp.desc())\
            .limit(limit)\
            .all()
        return recent_messages

class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_private = db.Column(db.Boolean, default=False)
    messages = db.relationship('Message', backref='channel', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('message.id'))
    file_url = db.Column(db.String(256))
    is_pinned = db.Column(db.Boolean, default=False)
    pinned_at = db.Column(db.DateTime)
    pinned_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    reactions = db.relationship('Reaction', backref='message', lazy=True, cascade='all, delete-orphan')
    threads = db.relationship(
        'Thread',
        backref='parent_message',
        lazy=True,
        cascade='all, delete-orphan',
        primaryjoin="Message.id==Thread.message_id"
    )
    replies = db.relationship(
        'Message',
        backref=db.backref('parent', remote_side=[id]),
        lazy=True,
        cascade='all, delete-orphan',
        order_by="Message.timestamp"  # Ensure replies are ordered by timestamp
    )

    @property
    def is_thread_reply(self):
        """Check if this message is a reply in a thread"""
        return self.parent_id is not None

    @property
    def thread_depth(self):
        """Get the depth of this message in the thread hierarchy"""
        depth = 0
        current = self
        while current.parent_id is not None:
            depth += 1
            current = current.parent
        return depth

class Thread(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('thread_messages', lazy=True))

class Reaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emoji = db.Column(db.String(32), nullable=False)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id', ondelete='CASCADE'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('reactions', lazy=True))

class UserBookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.String(256))