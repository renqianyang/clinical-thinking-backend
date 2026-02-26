from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


class UserRole(str, enum.Enum):
    TEACHER = "teacher"
    STUDENT = "student"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    taught_classes = relationship("Class", back_populates="teacher", foreign_keys="Class.teacher_id")
    enrolled_classes = relationship("Class", secondary="class_students", back_populates="students")
    sessions = relationship("Session", back_populates="student")
    created_cases = relationship("Case", back_populates="creator")


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    teacher = relationship("User", back_populates="taught_classes", foreign_keys=[teacher_id])
    students = relationship("User", secondary="class_students", back_populates="enrolled_classes")


class ClassStudent(Base):
    __tablename__ = "class_students"

    class_id = Column(Integer, ForeignKey("classes.id"), primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), primary_key=True)


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    patient_info = Column(JSON, default=dict)
    symptoms = Column(JSON, default=list)
    questions = Column(JSON, default=list)
    answers = Column(JSON, default=list)
    diagnosis = Column(String, nullable=False)
    difficulty = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    creator = relationship("User", back_populates="created_cases")
    sessions = relationship("Session", back_populates="case")


class SessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.IN_PROGRESS)
    score = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    diagnosis_submitted = Column(DateTime(timezone=True), nullable=True)
    student_diagnosis = Column(Text, nullable=True)

    # Relationships
    student = relationship("User", back_populates="sessions")
    case = relationship("Case", back_populates="sessions")
    dialogues = relationship("Dialogue", back_populates="session", order_by="Dialogue.timestamp")


class DialogueRole(str, enum.Enum):
    USER = "user"
    AI = "ai"


class Dialogue(Base):
    __tablename__ = "dialogues"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    message = Column(Text, nullable=False)
    role = Column(Enum(DialogueRole), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", back_populates="dialogues")
