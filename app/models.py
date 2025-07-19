from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class User(UserMixin, db.Model):
    """User model for authentication."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class Article(db.Model):
    """Article model to store research paper information."""

    id = db.Column(db.Integer, primary_key=True)
    doi = db.Column(db.String(120), unique=True, nullable=True, index=True)
    title = db.Column(db.Text, nullable=True)
    abstract = db.Column(db.Text, nullable=True)
    year = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f"<Article {self.title}>"
