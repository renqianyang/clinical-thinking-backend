from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============== Enums ==============

class UserRole(str, Enum):
    TEACHER = "teacher"
    STUDENT = "student"


class SessionStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class DialogueRole(str, Enum):
    USER = "user"
    AI = "ai"


# ============== User Schemas ==============

class UserBase(BaseModel):
    username: str
    role: UserRole
    full_name: str
    email: Optional[EmailStr] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserInDB(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserResponse(UserInDB):
    pass


# ============== Auth Schemas ==============

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# ============== Class Schemas ==============

class ClassBase(BaseModel):
    name: str


class ClassCreate(ClassBase):
    pass


class ClassUpdate(BaseModel):
    name: Optional[str] = None


class ClassInDB(ClassBase):
    id: int
    teacher_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ClassResponse(ClassInDB):
    teacher: Optional[UserResponse] = None
    students: List[UserResponse] = []


class ClassStudentAdd(BaseModel):
    student_id: int


# ============== Case Schemas ==============

class CaseBase(BaseModel):
    title: str
    description: str
    patient_info: Dict[str, Any] = Field(default_factory=dict)
    symptoms: List[str] = Field(default_factory=list)
    questions: List[str] = Field(default_factory=list)
    answers: List[str] = Field(default_factory=list)
    diagnosis: str
    difficulty: str


class CaseCreate(CaseBase):
    pass


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    patient_info: Optional[Dict[str, Any]] = None
    symptoms: Optional[List[str]] = None
    questions: Optional[List[str]] = None
    answers: Optional[List[str]] = None
    diagnosis: Optional[str] = None
    difficulty: Optional[str] = None


class CaseInDB(CaseBase):
    id: int
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


class CaseResponse(CaseInDB):
    creator: Optional[UserResponse] = None


class CaseListResponse(BaseModel):
    id: int
    title: str
    difficulty: str
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Session Schemas ==============

class SessionBase(BaseModel):
    case_id: int


class SessionCreate(SessionBase):
    pass


class SessionUpdate(BaseModel):
    status: Optional[SessionStatus] = None
    score: Optional[int] = None
    student_diagnosis: Optional[str] = None


class SessionInDB(BaseModel):
    id: int
    student_id: int
    case_id: int
    status: SessionStatus
    score: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    diagnosis_submitted: Optional[datetime] = None
    student_diagnosis: Optional[str] = None

    class Config:
        from_attributes = True


class SessionResponse(SessionInDB):
    case: Optional[CaseResponse] = None
    student: Optional[UserResponse] = None


class SessionSubmitDiagnosis(BaseModel):
    diagnosis: str


# ============== Dialogue Schemas ==============

class DialogueBase(BaseModel):
    message: str
    role: DialogueRole


class DialogueCreate(DialogueBase):
    session_id: int


class DialogueInDB(DialogueBase):
    id: int
    session_id: int
    timestamp: datetime

    class Config:
        from_attributes = True


class DialogueResponse(DialogueInDB):
    pass


# ============== Statistics Schemas ==============

class StudentStats(BaseModel):
    total_sessions: int
    completed_sessions: int
    average_score: Optional[float] = None
    total_cases_attempted: int


class TeacherStats(BaseModel):
    total_classes: int
    total_students: int
    total_cases_created: int
    total_sessions: int
