# This file contains all database tables/models

import datetime

from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func
from db import engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# ---------------- USER TABLE ----------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(100))
    email = Column(String(100), unique=True)
    password = Column(String(255))

    phone = Column(String(20), nullable=True)
    language = Column(String(50), nullable=True)
    profile_image = Column(Text, nullable=True)

# ---------------- DOCUMENT HISTORY TABLE ----------------
class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    user_email = Column(String(100))

    file_name = Column(String(255))

    file_path = Column(Text)

    extracted_text = Column(Text)

    guidance_text = Column(Text)

    audio_path = Column(Text)

    pdf_path = Column(Text, nullable=True)

    created_at = Column(
        TIMESTAMP,
        server_default=func.now()
    )

# ---------------- FEEDBACK TABLE ----------------

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)

    user_email = Column(String(100))
    app_experience = Column(String(50), nullable=True)
    voice_guidance_helpful = Column(String(50), nullable=True)
    recommend_app = Column(String(50), nullable=True)
    additional_comments = Column(Text, nullable=True)
    rating = Column(String(50), nullable=True)
    feedback_text = Column(Text, nullable=True)

    created_at = Column(
        TIMESTAMP,
        server_default=func.now()
    )

# ---------------- DEVELOPER DETAILS TABLE ----------------

class DeveloperDetails(Base):
    __tablename__ = "developer_details"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=True)
    father_name = Column(String(100), nullable=True)
    role = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    email = Column(String(100), nullable=True)
    github = Column(String(255), nullable=True)
    linkedin = Column(String(255), nullable=True)
    portfolio = Column(String(255), nullable=True)
    profile_image = Column(Text, nullable=True)

# Create all tables automatically

Base.metadata.create_all(bind=engine)