from flask import request, current_app
from flask_restful import Resource
from services.message_service import MessageService

class MessageController(Resource):
    def __init__(self, **kwargs):
        self.message_service = MessageService()

    @app.route("/messages/upload", methods=["POST"])
    def upload_file(self):
        """
        Endpoint to receive a file upload and attach it to a message
        """
        try:
            # Assuming the file is called 'attachment' in the form data
            uploaded_file = request.files.get("attachment")
            message_text = request.form.get("text", "")
            
            if not uploaded_file:
                current_app.logger.warning(f"No file found in the request")
                return {"error": "No file provided"}, 400
            
            # Pass the file and text to the service layer
            result = self.message_service.handle_file_upload(
                file=uploaded_file, 
                text=message_text
            )
            
            return result, 200
        
        except Exception as e:
            current_app.logger.error(f"File upload failed with error: {e}")
            return {"error": "File upload failed, please try again later"}, 500