import os
import logging
from flask import Flask, render_template, redirect, url_for, send_from_directory, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, join_room, leave_room
from flask_login import LoginManager, login_required, current_user
from sqlalchemy.orm import DeclarativeBase
from werkzeug.utils import secure_filename

logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')
login_manager = LoginManager()

app = Flask(__name__,
           template_folder='templates',
           static_folder='static')
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "dev_key_only"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///teamflow.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 280,
    "pool_pre_ping": True,
    "pool_size": 10,
    "max_overflow": 20,
}
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

# Ensure upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db.init_app(app)
socketio.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "auth.login"

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

# Add this route to serve uploaded files
@app.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        flash('File not found')
        return redirect(url_for('files'))

@app.route('/files')
@login_required
def files():
    # Query all messages that have files attached
    files = Message.query.filter(
        Message.file_name.isnot(None),
        Message.file_path.isnot(None)
    ).order_by(Message.timestamp.desc()).all()
    
    # Get all channels for the upload form
    channels = Channel.query.all()
    
    return render_template('files.html', files=files, channels=channels)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    try:
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(url_for('files'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(url_for('files'))
        
        # Validate channel_id
        channel_id = request.form.get('channel')
        if not channel_id:
            flash('Please select a channel')
            return redirect(url_for('files'))
            
        # Verify channel exists
        channel = Channel.query.get(channel_id)
        if not channel:
            flash('Invalid channel selected')
            return redirect(url_for('files'))
        
        if file:
            # Secure the filename and ensure it's unique
            original_filename = secure_filename(file.filename)
            file_name = original_filename
            counter = 1
            
            while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], file_name)):
                name, ext = os.path.splitext(original_filename)
                file_name = f"{name}_{counter}{ext}"
                counter += 1
            
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
            
            try:
                # Save the file
                file.save(file_path)
            except Exception as e:
                logging.error(f"Error saving file: {str(e)}")
                flash('Error saving file')
                return redirect(url_for('files'))
            
            # Create a message to track the file
            description = request.form.get('description', '')
            
            message = Message(
                content=description,
                user_id=current_user.id,
                channel_id=int(channel_id),  # Ensure channel_id is an integer
                file_name=file_name,
                file_path=file_path,
                file_type=file.content_type
            )
            
            try:
                db.session.add(message)
                db.session.commit()
                flash('File uploaded successfully')
            except Exception as e:
                db.session.rollback()
                logging.error(f"Database error: {str(e)}")
                # Clean up the file if database operation fails
                if os.path.exists(file_path):
                    os.remove(file_path)
                flash('Error uploading file')
                
            return redirect(url_for('files'))
        
        flash('Error uploading file')
        return redirect(url_for('files'))
        
    except Exception as e:
        logging.error(f"Unexpected error in upload_file: {str(e)}")
        flash('An unexpected error occurred')
        return redirect(url_for('files'))

@app.route('/delete-file', methods=['POST'])
@login_required
def delete_file():
    file_id = request.form.get('file_id')
    if not file_id:
        flash('No file specified')
        return redirect(url_for('files'))
    
    # Get the message containing the file information
    message = Message.query.get_or_404(file_id)
    
    # Security check: only allow users to delete their own files or admin users
    if message.user_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to delete this file')
        return redirect(url_for('files'))
    
    try:
        # Delete the physical file
        if message.file_path and os.path.exists(message.file_path):
            os.remove(message.file_path)
        
        # Delete the database record
        db.session.delete(message)
        db.session.commit()
        
        flash('File deleted successfully')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting file')
        logging.error(f"Error deleting file: {str(e)}")
    
    return redirect(url_for('files'))

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    try:
        content = request.form.get('content', '')
        channel_id = request.form.get('channel_id')
        
        if not channel_id:
            return 'Channel ID is required', 400
            
        # Verify channel exists
        channel = Channel.query.get(channel_id)
        if not channel:
            return 'Invalid channel', 400
            
        file = request.files.get('file')
        file_name = None
        file_path = None
        file_type = None
        
        if file and file.filename:
            # Secure the filename and ensure it's unique
            original_filename = secure_filename(file.filename)
            file_name = original_filename
            counter = 1
            
            while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], file_name)):
                name, ext = os.path.splitext(original_filename)
                file_name = f"{name}_{counter}{ext}"
                counter += 1
            
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
            file_type = file.content_type
            
            try:
                # Save the file
                file.save(file_path)
            except Exception as e:
                logging.error(f"Error saving file: {str(e)}")
                return 'Error saving file', 500
        
        # Create the message
        message = Message(
            content=content,
            user_id=current_user.id,
            channel_id=channel_id,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type
        )
        
        db.session.add(message)
        db.session.commit()
        
        # Emit the message through socket.io
        message_data = {
            'id': message.id,
            'content': message.content,
            'user': current_user.username,
            'user_id': current_user.id,
            'timestamp': message.timestamp.isoformat(),
            'channel_id': message.channel_id,
            'file_name': message.file_name,
            'file_type': message.file_type,
            'reactions': []
        }
        
        socketio.emit('message', message_data, room=f'channel_{channel_id}')
        return 'Message sent successfully', 200
        
    except Exception as e:
        logging.error(f"Error sending message: {str(e)}")
        db.session.rollback()
        return str(e), 500

@socketio.on('join')
def on_join(data):
    channel = data.get('channel')
    if channel:
        room = f'channel_{channel}'
        socketio.join_room(room)
        socketio.emit('join_success', {'channel': channel}, room=request.sid)

@socketio.on('leave')
def on_leave(data):
    channel = data.get('channel')
    if channel:
        room = f'channel_{channel}'
        socketio.leave_room(room)

@app.route('/rag')
@login_required
def rag_interface():
    return render_template('rag_query.html')

@app.route('/rag/query', methods=['POST'])
@login_required
def process_rag_query():
    data = request.get_json()
    query = data.get('query', '')
    
    # TODO: Implement actual RAG processing here
    # For now, return a placeholder response
    response = {
        'response': f'This is a placeholder response for the query: "{query}"\nRAG implementation coming soon!'
    }
    
    return jsonify(response)