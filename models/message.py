class Message(db.Model):
    __tablename__ = "messages"
    
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # New field to store the reference/identifier of the uploaded file
    attachment_path = db.Column(db.String(255), nullable=True)
    attachment_name = db.Column(db.String(255), nullable=True)
    attachment_size = db.Column(db.Integer, nullable=True)
    
    def __init__(self, text, attachment_path=None, attachment_name=None, attachment_size=None):
        self.text = text
        self.attachment_path = attachment_path
        self.attachment_name = attachment_name
        self.attachment_size = attachment_size 