from flask import current_app
from app import db
from models import Message
import os
import uuid
import re

def handle_file_upload(file, text):
    """
    Validates the file, saves it, creates a new Message record, 
    or updates an existing one depending on your workflow.
    """
    try:
        if not file.filename:
            current_app.logger.warning(f"Uploaded file without a valid filename")
            return {"error": "Invalid file"}, 400
        
        # Example simple file size check (2MB limit in this snippet)
        if len(file.read()) > 2 * 1024 * 1024:
            current_app.logger.info(f"File {file.filename} is too large")
            return {"error": "File size exceeds limit"}, 400
        
        file.seek(0)  # Reset pointer after size reading
        
        # Add more content checks (e.g., allowed extensions)
        allowed_extensions = {"png", "jpg", "jpeg", "pdf"}
        extension = file.filename.rsplit(".", 1)[-1].lower()
        
        if extension not in allowed_extensions:
            current_app.logger.info(f"File {file.filename} with disallowed extension")
            return {"error": "Unsupported file format"}, 400
        
        # Construct a secure filename and path
        unique_filename = generate_unique_filename(file.filename)
        save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_filename)
        
        file.save(save_path)
        current_app.logger.debug(
            f"File {file.filename} saved as {unique_filename} in {save_path}"
        )
        
        # Insert new Message record, saving metadata
        new_message = Message(
            text=text if text else "",
            attachment_path=save_path,
            attachment_name=unique_filename,
            attachment_size=os.path.getsize(save_path)
        )
        db.session.add(new_message)
        db.session.commit()
        
        current_app.logger.info(f"New message with ID={new_message.id} created")
        
        return {
            "message": "File uploaded successfully",
            "data": {
                "message_id": new_message.id,
                "filename": unique_filename,
                "size": os.path.getsize(save_path),
            },
        }
    
    except OSError as os_error:
        current_app.logger.error(f"OS error during file save: {os_error}")
        return {"error": "File could not be saved, please try again"}, 500
    except Exception as e:
        current_app.logger.error(f"Unhandled error during file upload: {e}")
        return {"error": "A server error occurred"}, 500 

def generate_unique_filename(original_filename):
    """
    Generate a secure, unique filename based on original filename.
    """
    try:
        basename, ext = os.path.splitext(original_filename)
        unique_id = uuid.uuid4().hex
        safe_basename = re.sub(r"[^a-zA-Z0-9_-]+", "_", basename)
        return f"{safe_basename}_{unique_id}{ext}"
    except Exception as e:
        current_app.logger.error(f"Failed to generate unique filename: {e}")
        # Fallback if something unexpected occurs
        return f"upload_{uuid.uuid4().hex}.bin" 

UPLOAD_FOLDER = "/var/www/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB limit 