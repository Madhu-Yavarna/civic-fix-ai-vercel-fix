from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(String(20), default="citizen", nullable=False)  # "citizen" or "admin"
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    complaints = relationship("Complaint", back_populates="citizen", cascade="all, delete-orphan")


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    code = Column(String(20), nullable=False)
    contact_email = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    jurisdiction_notes = Column(Text, nullable=True)

    # Relationships
    complaints = relationship("Complaint", back_populates="department")


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    complaint_no = Column(String(30), unique=True, index=True, nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(255), nullable=False)
    image_path = Column(String(255), nullable=True)
    status = Column(String(30), default="Pending", nullable=False)
    citizen_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    ai_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    citizen = relationship("User", back_populates="complaints")
    department = relationship("Department", back_populates="complaints")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    filename = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    page_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    category_tag = Column(String(50), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
