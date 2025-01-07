import os
import logging
from flask import Flask, render_template, redirect, url_for, request
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_login import LoginManager, login_required, current_user
from sqlalchemy.orm import DeclarativeBase

logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')
login_manager = LoginManager()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "dev_key_only"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///teamflow.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 280,
    "pool_pre_ping": True,
    "pool_size": 10,
    "max_overflow": 20,
}
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size

db.init_app(app)
socketio.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "auth.login"

# Add file upload route
@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return {'error': 'No file provided'}, 400
        
    file = request.files['file']
    text = request.form.get('text', '')
    
    if not file.filename:
        return {'error': 'No file selected'}, 400
        
    # Create uploads directory if it doesn't exist
    upload_dir = os.path.join(app.static_folder, 'uploads')
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        
    # Save file
    filename = secure_filename(file.filename)
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)
    
    return {'success': True, 'filename': filename}, 200

with app.app_context():
    # Import models before creating tables
    from models import User, Channel, Message, Thread, Reaction, UserBookmark

    # Only create tables if they don't exist
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