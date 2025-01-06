import os
import logging
from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_login import LoginManager, login_required, current_user
from sqlalchemy.orm import DeclarativeBase

logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
socketio = SocketIO()
login_manager = LoginManager()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "dev_key_only"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size

db.init_app(app)
socketio.init_app(app, cors_allowed_origins="*")
login_manager.init_app(app)
login_manager.login_view = "auth.login"

with app.app_context():
    # Import models before creating tables
    from models import User, Channel, Message, Thread, Reaction, UserBookmark

    # Drop all tables and recreate them with the new schema
    db.drop_all()
    db.create_all()

    # Create default channel if it doesn't exist
    default_channel = Channel.query.filter_by(name="General").first()
    if not default_channel:
        default_channel = Channel(
            name="General",
            description="Default channel for general discussions"
        )
        db.session.add(default_channel)
        db.session.commit()

    # Register blueprints
    from auth import auth_bp
    app.register_blueprint(auth_bp)

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Add root route
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return redirect(url_for('auth.login'))

# Add chat route
@app.route('/chat')
@login_required
def chat():
    channels = Channel.query.all()
    return render_template('chat.html', channels=channels)