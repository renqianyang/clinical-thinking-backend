from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

from database import engine, Base, get_db, SessionLocal
from models import User, Class, Case, Session as SessionModel, Dialogue, UserRole, SessionStatus, DialogueRole, ClassStudent
from schemas import *
from config import settings

# Create tables
Base.metadata.create_all(bind=engine)

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI(
    title="Clinical Thinking Training System",
    description="Backend API for clinical thinking training with teacher/student roles",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Auth Helpers ==============

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    # bcrypt has 72 byte limit, truncate if necessary
    return pwd_context.hash(password[:72])


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_teacher(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Teacher access required")
    return current_user


async def get_current_student(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Student access required")
    return current_user


# ============== Auth Endpoints ==============

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/auth/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if username exists
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email exists
    if user.email and db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    db_user = User(
        username=user.username,
        password_hash=get_password_hash(user.password),
        role=user.role,
        full_name=user.full_name,
        email=user.email
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.get("/auth/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


# ============== User Endpoints ==============

@app.get("/users", response_model=List[UserResponse])
async def list_users(
    role: Optional[UserRole] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher)
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return query.all()


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Students can only view themselves
    if current_user.role == UserRole.STUDENT and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return user


# ============== Class Endpoints (Teacher only for create/update) ==============

@app.post("/classes", response_model=ClassResponse)
async def create_class(
    class_data: ClassCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher)
):
    db_class = Class(
        name=class_data.name,
        teacher_id=current_user.id
    )
    db.add(db_class)
    db.commit()
    db.refresh(db_class)
    return db_class


@app.get("/classes", response_model=List[ClassResponse])
async def list_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == UserRole.TEACHER:
        return db.query(Class).filter(Class.teacher_id == current_user.id).all()
    else:
        return current_user.enrolled_classes


@app.get("/classes/{class_id}", response_model=ClassResponse)
async def get_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")
    
    # Check access
    if current_user.role == UserRole.TEACHER:
        if class_obj.teacher_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        if current_user not in class_obj.students:
            raise HTTPException(status_code=403, detail="Not enrolled in this class")
    
    return class_obj


@app.post("/classes/{class_id}/students", response_model=ClassResponse)
async def add_student_to_class(
    class_id: int,
    student_data: ClassStudentAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher)
):
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")
    if class_obj.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    student = db.query(User).filter(
        User.id == student_data.student_id,
        User.role == UserRole.STUDENT
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if student not in class_obj.students:
        class_obj.students.append(student)
        db.commit()
        db.refresh(class_obj)
    
    return class_obj


@app.delete("/classes/{class_id}/students/{student_id}")
async def remove_student_from_class(
    class_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher)
):
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")
    if class_obj.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    student = db.query(User).filter(User.id == student_id).first()
    if student and student in class_obj.students:
        class_obj.students.remove(student)
        db.commit()
    
    return {"message": "Student removed from class"}


# ============== Case Endpoints ==============

@app.post("/cases", response_model=CaseResponse)
async def create_case(
    case: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher)
):
    db_case = Case(
        **case.model_dump(),
        created_by=current_user.id
    )
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    return db_case


@app.get("/cases", response_model=List[CaseListResponse])
async def list_cases(
    difficulty: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Case)
    if difficulty:
        query = query.filter(Case.difficulty == difficulty)
    return query.all()


@app.get("/cases/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.put("/cases/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: int,
    case_update: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Can only edit your own cases")
    
    update_data = case_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(case, field, value)
    
    db.commit()
    db.refresh(case)
    return case


@app.delete("/cases/{case_id}")
async def delete_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Can only delete your own cases")
    
    db.delete(case)
    db.commit()
    return {"message": "Case deleted successfully"}


# ============== Session Endpoints ==============

@app.post("/sessions", response_model=SessionResponse)
async def create_session(
    session_data: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student)
):
    # Verify case exists
    case = db.query(Case).filter(Case.id == session_data.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Check if there's an existing incomplete session
    existing = db.query(SessionModel).filter(
        SessionModel.student_id == current_user.id,
        SessionModel.case_id == session_data.case_id,
        SessionModel.status == SessionStatus.IN_PROGRESS
    ).first()
    
    if existing:
        return existing
    
    db_session = SessionModel(
        student_id=current_user.id,
        case_id=session_data.case_id,
        status=SessionStatus.IN_PROGRESS
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session


@app.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    status: Optional[SessionStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == UserRole.STUDENT:
        query = db.query(SessionModel).filter(SessionModel.student_id == current_user.id)
    else:
        # Teachers see all sessions
        query = db.query(SessionModel)
    
    if status:
        query = query.filter(SessionModel.status == status)
    
    return query.order_by(SessionModel.started_at.desc()).all()


@app.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if current_user.role == UserRole.STUDENT and session.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return session


@app.post("/sessions/{session_id}/diagnosis", response_model=SessionResponse)
async def submit_diagnosis(
    session_id: int,
    diagnosis_data: SessionSubmitDiagnosis,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student)
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    session.student_diagnosis = diagnosis_data.diagnosis
    session.diagnosis_submitted = datetime.utcnow()
    session.status = SessionStatus.COMPLETED
    
    # Simple scoring (can be improved)
    correct_diagnosis = session.case.diagnosis.lower().strip()
    student_diagnosis = diagnosis_data.diagnosis.lower().strip()
    if correct_diagnosis in student_diagnosis or student_diagnosis in correct_diagnosis:
        session.score = 100
    else:
        session.score = 0
    
    db.commit()
    db.refresh(session)
    return session


# ============== Dialogue Endpoints ==============

@app.post("/dialogues", response_model=DialogueResponse)
async def create_dialogue(
    dialogue: DialogueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student)
):
    session = db.query(SessionModel).filter(SessionModel.id == dialogue.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Session is not active")
    
    db_dialogue = Dialogue(
        session_id=dialogue.session_id,
        message=dialogue.message,
        role=dialogue.role
    )
    db.add(db_dialogue)
    db.commit()
    db.refresh(db_dialogue)
    return db_dialogue


@app.get("/sessions/{session_id}/dialogues", response_model=List[DialogueResponse])
async def get_session_dialogues(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if current_user.role == UserRole.STUDENT and session.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return session.dialogues


# ============== Statistics Endpoints ==============

@app.get("/stats/student", response_model=StudentStats)
async def get_student_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student)
):
    sessions = db.query(SessionModel).filter(SessionModel.student_id == current_user.id).all()
    completed = [s for s in sessions if s.status == SessionStatus.COMPLETED]
    scores = [s.score for s in completed if s.score is not None]
    
    return StudentStats(
        total_sessions=len(sessions),
        completed_sessions=len(completed),
        average_score=sum(scores) / len(scores) if scores else None,
        total_cases_attempted=len(set(s.case_id for s in sessions))
    )


@app.get("/stats/teacher", response_model=TeacherStats)
async def get_teacher_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher)
):
    classes_count = db.query(Class).filter(Class.teacher_id == current_user.id).count()
    cases_count = db.query(Case).filter(Case.created_by == current_user.id).count()
    
    # Get all students in teacher's classes
    teacher_classes = db.query(Class).filter(Class.teacher_id == current_user.id).all()
    student_ids = set()
    for cls in teacher_classes:
        for student in cls.students:
            student_ids.add(student.id)
    
    # Get sessions for these students
    sessions_count = db.query(SessionModel).filter(
        SessionModel.student_id.in_(student_ids)
    ).count() if student_ids else 0
    
    return TeacherStats(
        total_classes=classes_count,
        total_students=len(student_ids),
        total_cases_created=cases_count,
        total_sessions=sessions_count
    )


# ============== Seed Data ==============

@app.on_event("startup")
async def seed_data():
    db = SessionLocal()
    try:
        # Create default users if they don't exist
        if not db.query(User).filter(User.username == "teacher").first():
            teacher = User(
                username="teacher",
                password_hash=get_password_hash("teacher123"),
                role=UserRole.TEACHER,
                full_name="Default Teacher",
                email="teacher@example.com"
            )
            db.add(teacher)
        
        if not db.query(User).filter(User.username == "student").first():
            student = User(
                username="student",
                password_hash=get_password_hash("student123"),
                role=UserRole.STUDENT,
                full_name="Default Student",
                email="student@example.com"
            )
            db.add(student)
        
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
