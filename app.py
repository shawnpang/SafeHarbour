# main.py

from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Sequence, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from passlib.context import CryptContext
from jose import JWTError, jwt
from typing import List, Optional
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta

# 配置
DATABASE_URL = "sqlite:///./test.db"
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 创建 FastAPI 应用程序
app = FastAPI()

# 设置 SQLAlchemy 数据库
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# SQLAlchemy 模型
Base = declarative_base()

class Audit(Base):
    __tablename__ = "audits"

    id = Column(Integer, Sequence('audit_id_seq'), primary_key=True, index=True)
    name = Column(String, index=True)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# Pydantic 模型用于审计
class AuditCreate(BaseModel):
    name: str
    status: str

class Audit(BaseModel):
    id: int
    name: str
    status: str
    created_at: datetime

# 用户认证
class User(BaseModel):
    username: str

class UserCreate(User):
    password: str

class UserInDB(User):
    hashed_password: str

# 密码散列化
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 创建用户表
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, Sequence('user_id_seq'), primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

# OAuth2 用于基于令牌的身份验证
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 生成 JWT 令牌的密钥
def generate_secret_key():
    return os.urandom(24).hex()

# 创建访问令牌
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 校验密码与散列密码是否匹配
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# 根据用户名获取用户
def get_user(db, username: str):
    return db.query(User).filter(User.username == username).first()

# 创建新用户
def create_user(db, user: UserCreate):
    hashed_password = pwd_context.hash(user.password)
    db_user = User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# 从令牌中获取当前用户的依赖项
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无法验证凭证", headers={"WWW-Authenticate": "Bearer"})
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无法验证凭证", headers={"WWW-Authenticate": "Bearer"})
    return username

# 创建新审计（已验证）
@app.post("/audits/", response_model=Audit)
async def create_audit(audit: AuditCreate, db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    db_audit = Audit(**audit.dict())
    db.add(db_audit)
    db.commit()
    db.refresh(db_audit)
    return db_audit

# 获取审计列表（已验证）
@app.get("/audits/", response_model=List[Audit])
async def get_audits(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    audits = db.query(Audit).offset(skip).limit(limit).all()
    return audits

# 创建新用户
@app.post("/users/", response_model=User)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="用户名已注册")
    return create_user(db, user)

# 用户身份验证的令牌端点
@app.post("/token", response_model=dict)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_user(db, username=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

# 获取数据库会话的依赖项
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
