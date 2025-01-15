import os
import logging
from flask import Flask, render_template, redirect, url_for, send_from_directory, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, join_room, leave_room
from flask_login import LoginManager, login_required, current_user
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase
from werkzeug.utils import secure_filename
from rag_utils import rag_manager
from datetime import datetime

logging.basicConfig(level=logging.DEBUG)

def extract_text_from_file(file_path, file_type):
    """Extract text content from uploaded file based on its type."""
    try:
        logging.info(f"Attempting to extract text from file: {file_path} (type: {file_type})")
        
        if file_type.startswith('text/') or any(file_path.endswith(ext) for ext in ['.txt', '.md', '.py', '.js', '.html', '.css']):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    logging.info(f"Successfully extracted {len(content)} characters from {file_path}")
                    return content
            except UnicodeDecodeError:
                # Try with a different encoding if UTF-8 fails
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
                    logging.info(f"Successfully extracted {len(content)} characters from {file_path} using latin-1 encoding")
                    return content
        elif file_type == 'application/pdf':
            # Add PDF extraction if needed
            logging.warning(f"PDF extraction not implemented for {file_path}")
            return None
        else:
            logging.info(f"Unsupported file type {file_type} for {file_path}")
            return None
    except Exception as e:
        logging.error(f"Error extracting text from file {file_path}: {str(e)}", exc_info=True)
        return None

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')
login_manager = LoginManager()
migrate = Migrate()

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
migrate.init_app(app, db)
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
                logging.info(f"File saved successfully: {file_path}")
                
                # Extract text and add to RAG system if it's a text file
                embedding_status = 'pending'
                if file.content_type.startswith('text/') or any(file_name.endswith(ext) for ext in ['.txt', '.md', '.py', '.js', '.html', '.css']):
                    logging.info(f"Processing text file for RAG: {file_name}")
                    text_content = extract_text_from_file(file_path, file.content_type)
                    if text_content:
                        metadata = {
                            "source": file_name,
                            "channel": channel.name,
                            "uploader": current_user.username,
                            "content_type": file.content_type
                        }
                        logging.info(f"Attempting to add document to RAG system: {file_name}")
                        success = rag_manager.add_documents([text_content], [metadata])
                        embedding_status = 'success' if success else 'failed'
                        logging.info(f"RAG processing result for {file_name}: {embedding_status}")
                    else:
                        embedding_status = 'failed'
                        logging.error(f"Failed to extract text content from {file_name}")
                else:
                    logging.info(f"Skipping RAG processing for non-text file: {file_name}")
                
            except Exception as e:
                logging.error(f"Error processing file {file_name}: {str(e)}", exc_info=True)
                flash('Error saving file')
                embedding_status = 'failed'
                return redirect(url_for('files'))
            
            # Create a message to track the file
            description = request.form.get('description', '')
            
            message = Message(
                content=description,
                user_id=current_user.id,
                channel_id=int(channel_id),
                file_name=file_name,
                file_path=file_path,
                file_type=file.content_type,
                embedding_status=embedding_status
            )
            
            try:
                db.session.add(message)
                db.session.commit()
                logging.info(f"File record created successfully: {file_name} (status: {embedding_status})")
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
        embedding_status = None
        
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
                logging.info(f"File saved successfully in message: {file_path}")
                
                # Extract text and add to RAG system if it's a text file
                embedding_status = 'pending'
                if file_type.startswith('text/') or any(file_name.endswith(ext) for ext in ['.txt', '.md', '.py', '.js', '.html', '.css']):
                    logging.info(f"Processing text file for RAG in message: {file_name}")
                    text_content = extract_text_from_file(file_path, file_type)
                    if text_content:
                        metadata = {
                            "source": file_name,
                            "channel": channel.name,
                            "uploader": current_user.username,
                            "content_type": file_type
                        }
                        logging.info(f"Attempting to add document to RAG system from message: {file_name}")
                        success = rag_manager.add_documents([text_content], [metadata])
                        embedding_status = 'success' if success else 'failed'
                        logging.info(f"RAG processing result for message file {file_name}: {embedding_status}")
                    else:
                        embedding_status = 'failed'
                        logging.error(f"Failed to extract text content from message file {file_name}")
                else:
                    logging.info(f"Skipping RAG processing for non-text message file: {file_name}")
            except Exception as e:
                logging.error(f"Error processing message file {file_name}: {str(e)}", exc_info=True)
                return 'Error saving file', 500
        
        # Create the message
        message = Message(
            content=content,
            user_id=current_user.id,
            channel_id=channel_id,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            embedding_status=embedding_status
        )
        
        db.session.add(message)
        db.session.commit()
        logging.info(f"Message created successfully{' with file: ' + file_name if file_name else ''}")
        
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
            'embedding_status': message.embedding_status,
            'reactions': []
        }
        
        socketio.emit('message', message_data, room=f'channel_{channel_id}')
        return 'Message sent successfully', 200
        
    except Exception as e:
        logging.error(f"Error sending message: {str(e)}", exc_info=True)
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

from rag_utils import rag_manager

@app.route('/rag')
@login_required
def rag_interface():
    return render_template('rag_query.html')

@app.route('/rag/query', methods=['POST'])
@login_required
def process_rag_query():
    try:
        data = request.get_json()
        query = data.get('query')
        query_type = data.get('type', 'question')  # 'question' or 'documentation'
        
        if not query:
            return jsonify({
                'error': 'No query provided',
                'response': 'Please provide a query.'
            }), 400
            
        # Process the query
        result = rag_manager.query(query)
        
        # Format the response based on query type
        if query_type == 'documentation':
            response = f"Documentation:\n\n{result['answer']}\n\nSources:\n"
            for source in result.get('sources', []):
                response += f"\n- {source['file']}"
        else:
            response = f"{result['answer']}\n\nRelevant Sources:\n"
            for source in result.get('sources', []):
                response += f"\n- {source['file']}"
        
        return jsonify({
            'response': response,
            'raw_result': result
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'response': 'An error occurred while processing your query.'
        }), 500

@app.route('/rag/ingest', methods=['POST'])
@login_required
def ingest_documents():
    try:
        if not request.files:
            logging.warning("No files provided in request")
            return jsonify({
                'error': 'No files provided',
                'message': 'Please provide files to ingest.'
            }), 400
            
        files = request.files.getlist('files')
        successful_files = []
        failed_files = []
        
        for file in files:
            try:
                logging.info(f"Processing file: {file.filename}")
                
                # Get file extension
                _, ext = os.path.splitext(file.filename)
                ext = ext.lower()
                
                # Check if it's a supported text-based file
                is_text_file = (
                    file.content_type.startswith('text/') or
                    ext in ['.txt', '.md', '.py', '.js', '.html', '.css']
                )
                
                if not is_text_file:
                    error_msg = f"Unsupported file type: {file.content_type}"
                    logging.warning(f"{file.filename}: {error_msg}")
                    failed_files.append(f"{file.filename} ({error_msg})")
                    continue
                
                try:
                    # Try to read and decode the file content
                    content = file.read().decode('utf-8')
                    logging.info(f"Successfully read {file.filename} with UTF-8 encoding")
                except UnicodeDecodeError:
                    # If UTF-8 fails, try with a different encoding
                    file.seek(0)  # Reset file pointer
                    content = file.read().decode('latin-1')
                    logging.info(f"Successfully read {file.filename} with latin-1 encoding")
                
                # Log content length for debugging
                logging.info(f"Content length for {file.filename}: {len(content)} characters")
                
                metadata = {
                    'source': file.filename,
                    'type': 'text/markdown' if ext == '.md' else file.content_type,
                    'uploader': current_user.username,
                    'upload_time': datetime.utcnow().isoformat()
                }
                
                logging.info(f"Attempting to add {file.filename} to vector store")
                # Add to vector store
                success = rag_manager.add_documents(
                    texts=[content],
                    metadatas=[metadata]
                )
                
                if success:
                    logging.info(f"Successfully processed {file.filename}")
                    successful_files.append(file.filename)
                else:
                    error_msg = "Failed to add to vector store"
                    logging.error(f"{file.filename}: {error_msg}")
                    failed_files.append(f"{file.filename} ({error_msg})")
                    
            except Exception as e:
                logging.error(f"Error processing {file.filename}: {str(e)}", exc_info=True)
                failed_files.append(f"{file.filename} ({str(e)})")
        
        result = {
            'message': 'Document ingestion complete',
            'successful_files': successful_files,
            'failed_files': failed_files
        }
        logging.info(f"Ingestion result: {result}")
        return jsonify(result)
        
    except Exception as e:
        error_msg = f"An error occurred during document ingestion: {str(e)}"
        logging.error(error_msg, exc_info=True)
        return jsonify({
            'error': str(e),
            'message': error_msg
        }), 500