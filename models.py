from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=True)
    matches_left = db.Column(db.Integer, default=10)
    auth_provider = db.Column(db.String(50), nullable=True,default='email')  # e.g., 'google', 'github', etc.
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(120), unique=True, nullable=True)
    token_expiration = db.Column(db.DateTime, nullable=True)

    match_history = db.relationship("MatchHistory", backref="user", lazy=True)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class MatchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resume_name = db.Column(db.String(255))
    score = db.Column(db.Float)
    timestamp = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
