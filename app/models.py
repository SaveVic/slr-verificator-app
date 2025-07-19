import json

from sqlalchemy import UniqueConstraint
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


class Article(db.Model):
    """Article model to store research paper information."""

    id = db.Column(db.Integer, primary_key=True)
    doi = db.Column(db.String(120), unique=True, nullable=True, index=True)
    title = db.Column(db.Text, nullable=True)
    abstract = db.Column(db.Text, nullable=True)
    year = db.Column(db.Integer, nullable=True)
    source = db.Column(db.String(100), nullable=True)

    # UPDATED: One-to-Many relationship to LLMResult
    llm_results = db.relationship(
        "LLMResult", backref="article", lazy=True, cascade="all, delete-orphan"
    )


class LLMResult(db.Model):
    """Stores a result from an LLM analysis for a given article."""

    id = db.Column(db.Integer, primary_key=True)
    success = db.Column(db.Boolean, nullable=False)
    raw = db.Column(db.Text, nullable=True)
    is_relevant = db.Column(db.Boolean, nullable=True)
    _addressed_areas = db.Column("addressed_areas", db.Text, nullable=True)
    justification = db.Column(db.Text, nullable=True)
    duration = db.Column(db.Float, nullable=True)
    num_token_in = db.Column(db.Float, nullable=True)
    num_token_out = db.Column(db.Float, nullable=True)
    llm_model_name = db.Column(db.String(100), nullable=False)

    article_id = db.Column(db.Integer, db.ForeignKey("article.id"), nullable=False)

    # UPDATED: Add a unique constraint for article_id and llm_model_name
    __table_args__ = (
        UniqueConstraint("article_id", "llm_model_name", name="_article_model_uc"),
    )

    @property
    def addressed_areas(self):
        if self._addressed_areas:
            return json.loads(self._addressed_areas)
        return []

    @addressed_areas.setter
    def addressed_areas(self, value):
        if value:
            self._addressed_areas = json.dumps(value)
        else:
            self._addressed_areas = None

    def __repr__(self):
        return f"<LLMResult {self.llm_model_name} for Article {self.article_id}>"
