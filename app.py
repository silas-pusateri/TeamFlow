import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_login import LoginManager
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
    from models import User, Channel, Message, Thread, Reaction
    db.create_all()

    # Register blueprints
    from auth import auth_bp
    app.register_blueprint(auth_bp)

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))
