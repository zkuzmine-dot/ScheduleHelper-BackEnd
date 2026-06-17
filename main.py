import html
import hmac
import hashlib
from urllib.parse import parse_qsl
from fastapi import FastAPI, Depends, HTTPException, status, Request, WebSocket, WebSocketDisconnect, Query, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Time, Date, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import Text, ForeignKey, func
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
import pytz
import logging
from enum import Enum
import json
import telegram
from telegram.ext import Application
from dotenv import load_dotenv
import os
import asyncio
import redis.asyncio as redis
import re
from cryptography.fernet import Fernet
from contextlib import asynccontextmanager
# ====================== ШИФРОВАНИЕ СООБЩЕНИЙ ======================
MASTER_KEY = os.getenv("MASTER_KEY")

if not MASTER_KEY:
    raise ValueError("MASTER_KEY is required for message encryption. Please add it to .env file")

# Проверка корректности ключа
if len(MASTER_KEY) != 44:
    raise ValueError("MASTER_KEY must be a valid Fernet key (44 characters long)")


fernet_master = Fernet(MASTER_KEY.encode())

def sanitize_message(content: str) -> str:
    if not content:
        return ""
    
    # 1. Ограничиваем длину сообщения
    if len(content) > 2000:
        content = content[:2000] + "..."
    
    # 2. Экранируем HTML (основная защита от XSS)
    content = html.escape(content)
    
    # 3. Дополнительно удаляем потенциально опасные атрибуты (на всякий случай)
    content = re.sub(r'on\w+\s*=', '', content, flags=re.IGNORECASE)
    
    return content

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
DATABASE_URL = os.getenv("DATABASE_URL")
MOSCOW_TZ = pytz.timezone("Europe/Moscow")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")

if not all([SECRET_KEY, DATABASE_URL, TELEGRAM_BOT_TOKEN]):
    raise ValueError("Missing required environment variables")
#if len(SECRET_KEY) < 32:
    #raise ValueError("SECRET_KEY must be at least 32 characters long")


redis_client = redis.Redis(host="redis", port=6379, db=1, decode_responses=True)


# Инициализация Telegram-бота с настройкой пула соединений
application = Application.builder().token(TELEGRAM_BOT_TOKEN).pool_timeout(30).concurrent_updates(10).build()
bot = application.bot

# FastAPI

# SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Перечисления
class WeekType(str, Enum):
    NUMERATOR = "numerator"
    DENOMINATOR = "denominator"
    BOTH = "both"

class LessonType(str, Enum):
    LECTURE = "lecture"
    PRACTICE = "practice"
    LAB = "lab"
    SEMINAR = "seminar"

class EventType(str, Enum):
    TEST = "Тест"
    QUIZ = "Контрольная"
    EXAM = "Экзамен"
    OTHER = "Другое"

# Вспомогательные функции для работы с часовыми поясами
def to_utc(moscow_time: datetime) -> datetime:
    if moscow_time.tzinfo is None:
        moscow_time = MOSCOW_TZ.localize(moscow_time)
    return moscow_time.astimezone(pytz.UTC)

def to_moscow(utc_time: datetime) -> datetime:
    if utc_time.tzinfo is None:
        utc_time = pytz.UTC.localize(utc_time)
    return utc_time.astimezone(MOSCOW_TZ)

# Модель пользователя
class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    telegram_id = Column(Integer, unique=True)
    role = Column(String)
    full_name = Column(String, nullable=True)
    group_number = Column(String, nullable=True)
    subgroup = Column(Integer, nullable=True)
    department = Column(String, nullable=True)
    notification_settings = Column(String, nullable=True)
    last_notified_event_ids = Column(JSON, default=[])
    created_at = Column(DateTime(timezone=True), default=lambda: to_utc(datetime.now(MOSCOW_TZ)))
    last_login = Column(DateTime(timezone=True), nullable=True)
    sent_messages = relationship("Message", back_populates="sender", cascade="all, delete-orphan")

# Модель расписания
class Schedule(Base):
    __tablename__ = 'schedules'
    id = Column(Integer, primary_key=True)
    group_number = Column(String, nullable=False)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    lesson_type = Column(String)
    subject = Column(String, nullable=False)
    classroom = Column(String)
    teacher_name = Column(String)
    subgroup = Column(Integer)
    week_type = Column(String)
    valid_from = Column(Date)
    valid_to = Column(Date)
    is_active = Column(Boolean, default=True)

# Модель события
class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    start_datetime = Column(DateTime(timezone=True), nullable=False)
    group_number = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

# ====================== НОВАЯ МОДЕЛЬ СООБЩЕНИЙ ======================
class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, nullable=False, index=True)           # group:ИВТ-21-1 | teachers | private:123_456
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # None = системное сообщение
    sender_username = Column(String, nullable=True)                # денормализация для быстрого отображения
    sender_full_name = Column(String, nullable=True)               # ФИО отправителя для чата
    content = Column(Text, nullable=False)
    is_encrypted = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    edited_at = Column(DateTime(timezone=True), nullable=True)

    # Связь с пользователем (для удобства)
    sender = relationship("UserDB", foreign_keys=[sender_id], back_populates="sent_messages")


# Добавляем обратную связь в модель UserDB (найди class UserDB и добавь внутрь класса):
# sent_messages = relationship("Message", back_populates="sender", cascade="all, delete-orphan")
# ====================== МОДЕЛЬ КЛЮЧЕЙ КОМНАТ ======================
class RoomKey(Base):
    __tablename__ = 'room_keys'

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, unique=True, nullable=False, index=True)   # group:ИБ-2 или private:5_12
    encrypted_key = Column(String, nullable=False)                     # Зашифрованный ключ комнаты (Fernet)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ====================== LIFESPAN ======================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Автоматически создаём таблицы при старте"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Все таблицы успешно созданы (или уже существуют)")
    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблиц: {e}")
    yield


# ====================== СОЗДАНИЕ ПРИЛОЖЕНИЯ ======================
app = FastAPI(lifespan=lifespan)

# ====================== CUSTOM MIDDLEWARE ======================
@app.middleware("http")
async def add_x_forwarded_proto(request: Request, call_next):
    if "X-Forwarded-Proto" in request.headers:
        request.scope["scheme"] = request.headers["X-Forwarded-Proto"]
    response = await call_next(request)
    return response
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:5173", "http://127.0.0.1:5500","https://schedulefrontend.timeofthestars.online"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic модели
class UserCreate(BaseModel):
    username: str
    password: str
    telegram_id: int
    role: str
    full_name: str | None = None
    group_number: str | None = None
    subgroup: int | None = None
    department: str | None = None
    notification_settings: str | None = None

class UserUpdate(BaseModel):
    username: str | None = None
    telegram_id: int | None = None
    role: str | None = None
    full_name: str | None = None
    group_number: str | None = None
    subgroup: int | None = None
    department: str | None = None
    notification_settings: str | None = None

class UserResponse(BaseModel):
    id: int
    username: str
    telegram_id: int
    role: str
    full_name: str | None
    group_number: str | None
    subgroup: int | None
    department: str | None
    notification_settings: str | None
    created_at: str
    last_login: str | None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class ScheduleCreate(BaseModel):
    group_number: str
    day_of_week: int
    start_time: str
    end_time: str
    lesson_type: LessonType
    subject: str
    classroom: str | None = None
    teacher_name: str | None = None
    subgroup: int | None = None
    week_type: WeekType
    valid_from: str | None = None
    valid_to: str | None = None
    is_active: bool = True

class ScheduleUpdate(BaseModel):
    group_number: str | None = None
    day_of_week: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    lesson_type: LessonType | None = None
    subject: str | None = None
    classroom: str | None = None
    teacher_name: str | None = None
    subgroup: int | None = None
    week_type: WeekType | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    is_active: bool | None = None

class ScheduleResponse(BaseModel):
    id: int
    group_number: str
    day_of_week: int
    start_time: str
    end_time: str
    lesson_type: LessonType
    subject: str
    classroom: str | None
    teacher_name: str | None
    subgroup: int | None
    week_type: WeekType
    valid_from: str | None
    valid_to: str | None
    is_active: bool

class EventCreate(BaseModel):
    title: str
    event_type: EventType
    start_datetime: str
    group_number: str
    description: str | None = None
    is_active: bool = True

class EventUpdate(BaseModel):
    title: str | None = None
    event_type: EventType | None = None
    start_datetime: str | None = None
    group_number: str | None = None
    description: str | None = None
    is_active: bool | None = None

class EventResponse(BaseModel):
    id: int
    title: str
    event_type: EventType
    start_datetime: str
    group_number: str
    description: str | None
    is_active: bool

class NotificationSettingsUpdate(BaseModel):
    notification_settings: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class MessageResponse(BaseModel):
    id: int
    room_id: str
    sender_id: int | None
    sender_username: str | None
    sender_full_name: str | None
    content: str
    created_at: str
    edited_at: str | None = None

class TeacherResponse(BaseModel):
    id: int
    username: str
    full_name: str | None
    department: str | None

class MessageCreate(BaseModel):
    room_id: str
    content: str

class ChatHistoryResponse(BaseModel):
    messages: list[MessageResponse]
    has_more: bool

# Зависимости
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = to_utc(datetime.now(MOSCOW_TZ)) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = to_utc(datetime.now(MOSCOW_TZ)) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ====================== REVOKE TOKEN ======================

async def add_token_to_blacklist(token: str, expires_in: int):
    """Добавляет токен в чёрный список"""
    key = f"blacklist:token:{token}"
    await redis_client.setex(key, expires_in, "revoked")


async def is_token_blacklisted(token: str) -> bool:
    """Проверяет, отозван ли токен"""
    if not token:
        return True
    key = f"blacklist:token:{token}"
    return await redis_client.exists(key) == 1

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        # Проверка чёрного списка
        if await is_token_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked"
            )

    except JWTError:
        raise credentials_exception

    user = db.query(UserDB).filter(UserDB.username == username).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin(current_user: UserDB = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user

async def get_current_admin_teacher_or_leader(current_user: UserDB = Depends(get_current_user)):
    if current_user.role not in ["admin", "teacher", "group_leader"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user

# Асинхронная функция отправки уведомления в Telegram
async def send_telegram_notification(telegram_id: int, message: str):
    try:
        await bot.send_message(chat_id=telegram_id, text=message)
        logger.info(f"Уведомление отправлено на telegram_id={telegram_id}: {message}")
    except telegram.error.TelegramError as e:
        logger.error(f"Ошибка отправки уведомления на telegram_id={telegram_id}: {e}")


# Отправка алерта администратору
async def send_admin_alert(message: str):
    if ADMIN_TELEGRAM_ID:
        await send_telegram_notification(int(ADMIN_TELEGRAM_ID), f"⚠️ Alert: {message}")
    else:
        logger.warning("ADMIN_TELEGRAM_ID not set, alert not sent")

# Проверка лимита попыток входа
async def check_rate_limit(ip: str, max_attempts: int = 5, window_seconds: int = 60) -> bool:
    key = f"rate_limit:{ip}"
    current_time = int(datetime.now().timestamp())
    
    async with redis_client.pipeline() as pipe:
        pipe.get(key)
        pipe.ttl(key)
        count, ttl = await pipe.execute()
        
        if count is None:
            await redis_client.setex(key, window_seconds, 1)
            return True
        
        count = int(count)
        if count < max_attempts:
            await redis_client.incr(key)
            return True
        
        remaining_ttl = ttl if ttl > 0 else window_seconds
        logger.warning(f"Rate limit exceeded for IP {ip}, remaining TTL: {remaining_ttl} seconds")
        return False
    
# Rate limit для отправки сообщений в чат
async def check_chat_rate_limit(user_id: int, max_messages: int = 15, window_seconds: int = 60) -> bool:
    key = f"chat_rate:{user_id}"
    
    async with redis_client.pipeline() as pipe:
        pipe.get(key)
        pipe.ttl(key)
        count, ttl = await pipe.execute()
        
        if count is None:
            await redis_client.setex(key, window_seconds, 1)
            return True
        
        count = int(count)
        if count < max_messages:
            await redis_client.incr(key)
            return True
        
        # Если лимит превышен — возвращаем False
        return False


# Эндпоинты
@app.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    tgid: int | None = None,
    db: Session = Depends(get_db),
    request: Request = None
):
    client_ip = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For") or request.client.host
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

    if not await check_rate_limit(client_ip):
        await send_admin_alert(f"Too many login attempts from IP {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts, please try again later",
        )

    user = db.query(UserDB).filter(UserDB.username == form_data.username).first()
    if not user:
        await send_admin_alert(f"Failed login attempt for unknown user {form_data.username} from IP {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form_data.password, user.password_hash):
        await send_admin_alert(f"Failed login attempt for user {user.id} from IP {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.last_login = to_utc(datetime.now(MOSCOW_TZ))
    
    if tgid is not None and user.telegram_id != tgid:
        existing_user = db.query(UserDB).filter(UserDB.telegram_id == tgid).first()
        if not existing_user:
            user.telegram_id = tgid

    db.commit()

    # Создаём два токена
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

def verify_telegram_init_data(init_data: str) -> dict | None:
    """Верифицирует Telegram WebApp initData через HMAC-SHA256, возвращает user dict если валидно"""
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

        secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_hash, received_hash):
            return None

        return json.loads(parsed.get("user", "{}"))
    except Exception as e:
        logger.error(f"Telegram initData verification error: {e}")
        return None


@app.post("/token/telegram", response_model=TokenResponse)
async def telegram_login(
    init_data: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    tg_user = verify_telegram_init_data(init_data)
    if not tg_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительные данные Telegram"
        )

    telegram_id = tg_user.get("id")
    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram ID не найден в данных"
        )

    user = db.query(UserDB).filter(UserDB.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь с таким Telegram не зарегистрирован. Обратитесь к администратору."
        )

    user.last_login = to_utc(datetime.now(MOSCOW_TZ))
    db.commit()

    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@app.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate, current_user: UserDB = Depends(get_current_admin), db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    db_user = db.query(UserDB).filter(UserDB.telegram_id == user.telegram_id).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Telegram ID already registered")
    
    hashed_password = get_password_hash(user.password)
    db_user = UserDB(
        username=user.username,
        password_hash=hashed_password,
        telegram_id=user.telegram_id,
        role=user.role,
        full_name=user.full_name,
        group_number=user.group_number,
        subgroup=user.subgroup,
        department=user.department,
        notification_settings=user.notification_settings,
        last_notified_event_ids=[],
    )
    db.add(db_user)
    db.commit()                                      # ← сохраняем пользователя

    # ====================== АВТОМАТИЧЕСКОЕ СОЗДАНИЕ БЕСЕДЫ ГРУППЫ ======================
    if user.role == "student" and user.group_number:
        # Проверяем, первый ли это студент в группе
        student_count = db.query(UserDB).filter(
            UserDB.group_number == user.group_number,
            UserDB.role == "student"
        ).count()

        if student_count == 1:  # Это первый студент → создаём беседу
            room_id = f"group:{user.group_number}"
            room_key = get_or_create_room_key(room_id, db)
            welcome_content = (
                f"👋 Беседа группы {user.group_number} успешно создана!\n\n"
                f"Здесь можно обсуждать расписание, домашку, вопросы к преподавателям и всё остальное."
            )
            welcome_message = Message(
                room_id=room_id,
                sender_id=None,
                sender_username="Система",
                content=encrypt_content(welcome_content, room_key),
                is_encrypted=True
            )
            db.add(welcome_message)
            db.commit()  # сохраняем системное сообщение
            logger.info(f"Создана беседа группы {user.group_number} (первый студент: {user.username})")

    db.refresh(db_user)  # ← теперь можно безопасно обновить объект
    
    return UserResponse(
        id=db_user.id,
        username=db_user.username,
        telegram_id=db_user.telegram_id,
        role=db_user.role,
        full_name=db_user.full_name,
        group_number=db_user.group_number,
        subgroup=db_user.subgroup,
        department=db_user.department,
        notification_settings=db_user.notification_settings,
        created_at=to_moscow(db_user.created_at).strftime("%Y-%m-%d %H:%M"),
        last_login=to_moscow(db_user.last_login).strftime("%Y-%m-%d %H:%M") if db_user.last_login else None
    )

@app.get("/users/", response_model=list[UserResponse])
async def get_users(
    current_user: UserDB = Depends(get_current_admin),
    db: Session = Depends(get_db),
    role: str | None = None,
    group_number: str | None = None
):
    query = db.query(UserDB)
    
    if role:
        query = query.filter(UserDB.role == role)
    if group_number:
        query = query.filter(UserDB.group_number == group_number)
    
    users = query.all()
    return [
        UserResponse(
            id=user.id,
            username=user.username,
            telegram_id=user.telegram_id,
            role=user.role,
            full_name=user.full_name,
            group_number=user.group_number,
            subgroup=user.subgroup,
            department=user.department,
            notification_settings=user.notification_settings,
            created_at=to_moscow(user.created_at).strftime("%Y-%m-%d %H:%M"),
            last_login=to_moscow(user.last_login).strftime("%Y-%m-%d %H:%M") if user.last_login else None
        )
        for user in users
    ]

@app.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user: UserUpdate,
    current_user: UserDB = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    db_user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user.dict(exclude_unset=True)
    
    # Проверка уникальности username, если он изменяется
    if "username" in update_data and update_data["username"] != db_user.username:
        existing_user = db.query(UserDB).filter(UserDB.username == update_data["username"]).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already registered")
        db_user.username = update_data["username"]
    
    # Проверка уникальности telegram_id, если он изменяется
    if "telegram_id" in update_data and update_data["telegram_id"] != db_user.telegram_id:
        existing_user = db.query(UserDB).filter(UserDB.telegram_id == update_data["telegram_id"]).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Telegram ID already registered")
        db_user.telegram_id = update_data["telegram_id"]
    
    # Обновление остальных полей
    if "role" in update_data:
        db_user.role = update_data["role"]
    if "full_name" in update_data:
        db_user.full_name = update_data["full_name"]
    if "group_number" in update_data:
        db_user.group_number = update_data["group_number"]
    if "subgroup" in update_data:
        db_user.subgroup = update_data["subgroup"]
    if "department" in update_data:
        db_user.department = update_data["department"]
    if "notification_settings" in update_data:
        try:
            if update_data["notification_settings"]:
                json.loads(update_data["notification_settings"])
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format for notification_settings")
        db_user.notification_settings = update_data["notification_settings"]
    
    db.commit()
    db.refresh(db_user)

    return UserResponse(
        id=db_user.id,
        username=db_user.username,
        telegram_id=db_user.telegram_id,
        role=db_user.role,
        full_name=db_user.full_name,
        group_number=db_user.group_number,
        subgroup=db_user.subgroup,
        department=db_user.department,
        notification_settings=db_user.notification_settings,
        created_at=to_moscow(db_user.created_at).strftime("%Y-%m-%d %H:%M"),
        last_login=to_moscow(db_user.last_login).strftime("%Y-%m-%d %H:%M") if db_user.last_login else None
    )

@app.delete("/users/{user_id}", response_model=dict)
async def delete_user(
    user_id: int,
    current_user: UserDB = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    db_user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(db_user)
    db.commit()
    
    return {"message": f"User {user_id} deleted successfully"}

@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: UserDB = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        telegram_id=current_user.telegram_id,
        role=current_user.role,
        full_name=current_user.full_name,
        group_number=current_user.group_number,
        subgroup=current_user.subgroup,
        department=current_user.department,
        notification_settings=current_user.notification_settings,
        created_at=to_moscow(current_user.created_at).strftime("%Y-%m-%d %H:%M"),
        last_login=to_moscow(current_user.last_login).strftime("%Y-%m-%d %H:%M") if current_user.last_login else None
    )

@app.put("/users/me/notification-settings", response_model=UserResponse)
async def update_notification_settings(
    settings: NotificationSettingsUpdate,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        current_settings = json.loads(current_user.notification_settings or '{}')
    except json.JSONDecodeError:
        logger.warning(f"Некорректные данные в notification_settings для пользователя {current_user.username}. Сбрасываем в пустой JSON.")
        current_settings = {}

    try:
        parsed_settings = json.loads(settings.notification_settings)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for notification_settings")

    if "event_reminder" in parsed_settings:
        # Разрешаем -1, но запрещаем другие отрицательные значения
        if not isinstance(parsed_settings["event_reminder"], int) or (parsed_settings["event_reminder"] < -1):
            raise HTTPException(
                status_code=400,
                detail="event_reminder must be a non-negative integer or -1 to disable notifications"
            )

    new_event_reminder = parsed_settings.get("event_reminder")
    old_event_reminder = current_settings.get("event_reminder")
    if new_event_reminder != old_event_reminder:
        current_user.last_notified_event_ids = []
        logger.info(f"Сброшены уведомления для пользователя {current_user.username} из-за изменения event_reminder")

    current_user.notification_settings = settings.notification_settings
    db.commit()
    db.refresh(current_user)
    
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        telegram_id=current_user.telegram_id,
        role=current_user.role,
        group_number=current_user.group_number,
        subgroup=current_user.subgroup,
        department=current_user.department,
        notification_settings=current_user.notification_settings,
        created_at=to_moscow(current_user.created_at).strftime("%Y-%m-%d %H:%M"),
        last_login=to_moscow(current_user.last_login).strftime("%Y-%m-%d %H:%M") if current_user.last_login else None
    )

@app.put("/users/me/password", response_model=dict)
async def change_password(
    password_data: PasswordChange,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect current password"
        )
    
    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password"
        )
    
    hashed_password = get_password_hash(password_data.new_password)
    current_user.password_hash = hashed_password
    db.commit()
    
    logger.info(f"Password changed successfully for user {current_user.username}")
    return {"message": "Password changed successfully"}

@app.post("/schedules/", response_model=ScheduleResponse)
async def create_schedule(schedule: ScheduleCreate, current_user: UserDB = Depends(get_current_admin_teacher_or_leader), db: Session = Depends(get_db)):
    try:
        start_time = datetime.strptime(schedule.start_time, "%H:%M").time()
        end_time = datetime.strptime(schedule.end_time, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM")
    
    valid_from = None
    valid_to = None
    if schedule.valid_from:
        try:
            valid_from = datetime.strptime(schedule.valid_from, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid valid_from format. Use YYYY-MM-DD")
    if schedule.valid_to:
        try:
            valid_to = datetime.strptime(schedule.valid_to, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid valid_to format. Use YYYY-MM-DD")

    if not 1 <= schedule.day_of_week <= 7:
        raise HTTPException(status_code=400, detail="Day of week must be between 1 and 7")

    db_schedule = Schedule(
        group_number=schedule.group_number,
        day_of_week=schedule.day_of_week,
        start_time=start_time,
        end_time=end_time,
        lesson_type=schedule.lesson_type.value,
        subject=schedule.subject,
        classroom=schedule.classroom,
        teacher_name=schedule.teacher_name,
        subgroup=schedule.subgroup,
        week_type=schedule.week_type.value,
        valid_from=valid_from,
        valid_to=valid_to,
        is_active=schedule.is_active
    )
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)

    return ScheduleResponse(
        id=db_schedule.id,
        group_number=db_schedule.group_number,
        day_of_week=db_schedule.day_of_week,
        start_time=db_schedule.start_time.strftime("%H:%M"),
        end_time=db_schedule.end_time.strftime("%H:%M"),
        lesson_type=LessonType(db_schedule.lesson_type),
        subject=db_schedule.subject,
        classroom=db_schedule.classroom,
        teacher_name=db_schedule.teacher_name,
        subgroup=db_schedule.subgroup,
        week_type=WeekType(db_schedule.week_type),
        valid_from=db_schedule.valid_from.strftime("%Y-%m-%d") if db_schedule.valid_from else None,
        valid_to=db_schedule.valid_to.strftime("%Y-%m-%d") if db_schedule.valid_to else None,
        is_active=db_schedule.is_active
    )

@app.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    schedule: ScheduleUpdate,
    current_user: UserDB = Depends(get_current_admin_teacher_or_leader),
    db: Session = Depends(get_db)
):
    db_schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    update_data = schedule.dict(exclude_unset=True)
    
    if "start_time" in update_data:
        try:
            db_schedule.start_time = datetime.strptime(update_data["start_time"], "%H:%M").time()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_time format. Use HH:MM")
    
    if "end_time" in update_data:
        try:
            db_schedule.end_time = datetime.strptime(update_data["end_time"], "%H:%M").time()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_time format. Use HH:MM")
    
    if "valid_from" in update_data and update_data["valid_from"]:
        try:
            db_schedule.valid_from = datetime.strptime(update_data["valid_from"], "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid valid_from format. Use YYYY-MM-DD")
    
    if "valid_to" in update_data and update_data["valid_to"]:
        try:
            db_schedule.valid_to = datetime.strptime(update_data["valid_to"], "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid valid_to format. Use YYYY-MM-DD")
    
    if "day_of_week" in update_data and update_data["day_of_week"] is not None:
        if not 1 <= update_data["day_of_week"] <= 7:
            raise HTTPException(status_code=400, detail="Day of week must be between 1 and 7")
        db_schedule.day_of_week = update_data["day_of_week"]
    
    if "group_number" in update_data and update_data["group_number"] is not None:
        db_schedule.group_number = update_data["group_number"]
    
    if "lesson_type" in update_data and update_data["lesson_type"] is not None:
        db_schedule.lesson_type = update_data["lesson_type"].value
    
    if "subject" in update_data and update_data["subject"] is not None:
        db_schedule.subject = update_data["subject"]
    
    if "classroom" in update_data:
        db_schedule.classroom = update_data["classroom"]
    
    if "teacher_name" in update_data:
        db_schedule.teacher_name = update_data["teacher_name"]
    
    if "subgroup" in update_data:
        db_schedule.subgroup = update_data["subgroup"]
    
    if "week_type" in update_data and update_data["week_type"] is not None:
        db_schedule.week_type = update_data["week_type"].value
    
    if "is_active" in update_data and update_data["is_active"] is not None:
        db_schedule.is_active = update_data["is_active"]
    
    db.commit()
    db.refresh(db_schedule)

    return ScheduleResponse(
        id=db_schedule.id,
        group_number=db_schedule.group_number,
        day_of_week=db_schedule.day_of_week,
        start_time=db_schedule.start_time.strftime("%H:%M"),
        end_time=db_schedule.end_time.strftime("%H:%M"),
        lesson_type=LessonType(db_schedule.lesson_type),
        subject=db_schedule.subject,
        classroom=db_schedule.classroom,
        teacher_name=db_schedule.teacher_name,
        subgroup=db_schedule.subgroup,
        week_type=WeekType(db_schedule.week_type),
        valid_from=db_schedule.valid_from.strftime("%Y-%m-%d") if db_schedule.valid_from else None,
        valid_to=db_schedule.valid_to.strftime("%Y-%m-%d") if db_schedule.valid_to else None,
        is_active=db_schedule.is_active
    )

@app.get("/schedules/", response_model=list[ScheduleResponse])
async def get_schedules(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
    group_number: str | None = None,
    week: str | None = None
):
    query = db.query(Schedule).filter(Schedule.is_active == True)
    
    if group_number:
        query = query.filter(Schedule.group_number == group_number)
    elif current_user.role in ["student", "group_leader"] and not group_number:
        if not current_user.group_number:
            raise HTTPException(status_code=400, detail="User has no group assigned")
        query = query.filter(Schedule.group_number == current_user.group_number)

    if week in ["current", "next"]:
        today = datetime.now(MOSCOW_TZ)
        week_number = today.isocalendar()[1]
        if week == "next":
            week_number += 1
        week_type = "numerator" if week_number % 2 == 0 else "denominator"
        query = query.filter((Schedule.week_type == week_type) | (Schedule.week_type == "both"))

    today = to_utc(datetime.now(MOSCOW_TZ)).date()
    query = query.filter(
        (Schedule.valid_from.is_(None) | (Schedule.valid_from <= today)),
        (Schedule.valid_to.is_(None) | (Schedule.valid_to >= today))
    )

    schedules = query.all()
    return [
        ScheduleResponse(
            id=s.id,
            group_number=s.group_number,
            day_of_week=s.day_of_week,
            start_time=s.start_time.strftime("%H:%M"),
            end_time=s.end_time.strftime("%H:%M"),
            lesson_type=LessonType(s.lesson_type),
            subject=s.subject,
            classroom=s.classroom,
            teacher_name=s.teacher_name,
            subgroup=s.subgroup,
            week_type=WeekType(s.week_type),
            valid_from=s.valid_from.strftime("%Y-%m-%d") if s.valid_from else None,
            valid_to=s.valid_to.strftime("%Y-%m-%d") if s.valid_to else None,
            is_active=s.is_active
        )
        for s in schedules
    ]

@app.delete("/schedules/{schedule_id}", response_model=dict)
async def delete_schedule(
    schedule_id: int,
    current_user: UserDB = Depends(get_current_admin_teacher_or_leader),
    db: Session = Depends(get_db)
):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    schedule.is_active = False
    db.commit()
    return {"message": f"Schedule {schedule_id} deleted successfully"}

@app.post("/events/", response_model=EventResponse)
async def create_event(event: EventCreate, current_user: UserDB = Depends(get_current_admin_teacher_or_leader), db: Session = Depends(get_db)):
    try:
        start_datetime_moscow = datetime.strptime(event.start_datetime, "%Y-%m-%d %H:%M")
        start_datetime_utc = to_utc(start_datetime_moscow)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid start_datetime format. Use YYYY-MM-DD HH:MM")

    db_event = Event(
        title=event.title,
        event_type=event.event_type.value,
        start_datetime=start_datetime_utc,
        group_number=event.group_number,
        description=event.description,
        is_active=event.is_active
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    start_datetime_moscow_response = to_moscow(db_event.start_datetime)
    return EventResponse(
        id=db_event.id,
        title=db_event.title,
        event_type=EventType(db_event.event_type),
        start_datetime=start_datetime_moscow_response.strftime("%Y-%m-%d %H:%M"),
        group_number=db_event.group_number,
        description=db_event.description,
        is_active=db_event.is_active
    )

@app.put("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    event: EventUpdate,
    current_user: UserDB = Depends(get_current_admin_teacher_or_leader),
    db: Session = Depends(get_db)
):
    db_event = db.query(Event).filter(Event.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Получаем исходную группу события
    original_group_number = db_event.group_number

    update_data = event.dict(exclude_unset=True)
    
    if "start_datetime" in update_data and update_data["start_datetime"]:
        try:
            start_datetime_moscow = datetime.strptime(update_data["start_datetime"], "%Y-%m-%d %H:%M")
            db_event.start_datetime = to_utc(start_datetime_moscow)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_datetime format. Use YYYY-MM-DD HH:MM")
    
    if "title" in update_data and update_data["title"] is not None:
        db_event.title = update_data["title"]
    
    if "event_type" in update_data and update_data["event_type"] is not None:
        db_event.event_type = update_data["event_type"].value
    
    if "group_number" in update_data and update_data["group_number"] is not None:
        db_event.group_number = update_data["group_number"]
    
    if "description" in update_data:
        db_event.description = update_data["description"]
    
    if "is_active" in update_data and update_data["is_active"] is not None:
        db_event.is_active = update_data["is_active"]

    # Обновляем last_notified_event_ids для пользователей исходной группы
    group_to_update = original_group_number
    if "group_number" in update_data and update_data["group_number"] is not None:
        # Если группа изменилась, также нужно сбросить уведомления для пользователей новой группы
        group_to_update = [original_group_number, update_data["group_number"]]
    else:
        group_to_update = [group_to_update]

    for group in set(group_to_update):
        users = db.query(UserDB).filter(UserDB.group_number == group).all()
        for user in users:
            if user.last_notified_event_ids and event_id in user.last_notified_event_ids:
                user.last_notified_event_ids.remove(event_id)
                flag_modified(user, "last_notified_event_ids")
                db.add(user)
                logger.info(f"Удалён event_id {event_id} из last_notified_event_ids пользователя {user.username}")

    db.commit()
    db.refresh(db_event)

    start_datetime_moscow_response = to_moscow(db_event.start_datetime)
    return EventResponse(
        id=db_event.id,
        title=db_event.title,
        event_type=EventType(db_event.event_type),
        start_datetime=start_datetime_moscow_response.strftime("%Y-%m-%d %H:%M"),
        group_number=db_event.group_number,
        description=db_event.description,
        is_active=db_event.is_active
    )

@app.get("/events/", response_model=list[EventResponse])
async def get_events(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
    group_number: str | None = None
):
    now_moscow = datetime.now(MOSCOW_TZ)
    now_utc = to_utc(now_moscow)
    query = db.query(Event).filter(Event.is_active == True, Event.start_datetime > now_utc)
    
    if group_number:
        query = query.filter(Event.group_number == group_number)
    elif current_user.role in ["student", "group_leader"] and not group_number:
        if not current_user.group_number:
            raise HTTPException(status_code=400, detail="User has no group assigned")
        query = query.filter(Event.group_number == current_user.group_number)

    events = query.all()
    return [
        EventResponse(
            id=e.id,
            title=e.title,
            event_type=EventType(e.event_type),
            start_datetime=to_moscow(e.start_datetime).strftime("%Y-%m-%d %H:%M"),
            group_number=e.group_number,
            description=e.description,
            is_active=e.is_active
        )
        for e in events
    ]

@app.delete("/events/{event_id}", response_model=dict)
async def delete_event(
    event_id: int,
    current_user: UserDB = Depends(get_current_admin_teacher_or_leader),
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event.is_active = False
    db.commit()
    return {"message": f"Event {event_id} deleted successfully"}

# ====================== ЧАТ: ИСТОРИЯ СООБЩЕНИЙ ======================

def check_room_access(room_id: str, current_user: UserDB, db: Session) -> bool:
    """Строгая проверка доступа к комнате + защита от некорректных room_id"""
    
    if not room_id or len(room_id) > 100:
        return False

    # 1. Групповой чат
    if room_id.startswith("group:"):
        group = room_id[6:]  # после "group:"
        # Разрешаем буквы, цифры, дефис, подчёркивание и кириллицу
        if not re.match(r'^[\w\-]+$', group, re.UNICODE):
            return False
        if current_user.role in ["student", "group_leader"]:
            return current_user.group_number == group
        return False

    # 2. Чат преподавателей
    elif room_id == "teachers":
        return current_user.role in ["teacher", "admin"]

    # 3. Личный чат (private)
    elif room_id.startswith("private:"):
        try:
            ids_part = room_id[8:]  # после "private:"
            # Строгая проверка формата: два числа через одно подчёркивание
            if not re.match(r'^\d+_\d+$', ids_part):
                return False
            
            user1_str, user2_str = ids_part.split("_")
            user1 = int(user1_str)
            user2 = int(user2_str)

            # Защита от слишком больших ID
            if user1 < 1 or user2 < 1 or user1 > 10_000_000 or user2 > 10_000_000:
                return False

            # Пользователь должен быть одним из участников
            if current_user.id not in (user1, user2):
                return False

            users = db.query(UserDB).filter(UserDB.id.in_([user1, user2])).all()
            if len(users) != 2:
                return False
            u_a, u_b = users[0], users[1]
            roles = {u_a.role, u_b.role}

            # Один из участников — преподаватель или админ (покрывает: студент-препод, препод-препод, препод-админ)
            if "teacher" in roles or "admin" in roles:
                return True

            # Студент/старший <-> старшина своей же группы
            if "group_leader" in roles and u_a.group_number is not None and u_a.group_number == u_b.group_number:
                return True

            return False

        except:
            return False

    return False

def get_or_create_room_key(room_id: str, db: Session) -> Fernet:
    """Получает или создаёт ключ шифрования для конкретной комнаты"""
    room_key_record = db.query(RoomKey).filter(RoomKey.room_id == room_id).first()

    if not room_key_record:
        # Генерируем новый ключ для комнаты
        new_key = Fernet.generate_key()
        encrypted_key = fernet_master.encrypt(new_key)

        room_key_record = RoomKey(
            room_id=room_id,
            encrypted_key=encrypted_key.decode()
        )
        db.add(room_key_record)
        db.commit()
        logger.info(f"Создан новый ключ шифрования для комнаты: {room_id}")

    # Расшифровываем ключ комнаты с помощью MASTER_KEY
    decrypted_key = fernet_master.decrypt(room_key_record.encrypted_key.encode())
    return Fernet(decrypted_key)


def encrypt_content(content: str, room_key: Fernet) -> str:
    """Шифрует текст сообщения"""
    return room_key.encrypt(content.encode()).decode()


def decrypt_content(encrypted_content: str, room_key: Fernet) -> str:
    """Расшифровывает текст сообщения"""
    if not encrypted_content:
        return ""
    try:
        return room_key.decrypt(encrypted_content.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to decrypt message in room: {e}")
        return "[Сообщение не удалось расшифровать]"

@app.get("/chat/history/{room_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    room_id: str,
    limit: int = 50,
    offset: int = 0,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Проверка прав доступа к комнате
    if not check_room_access(room_id, current_user, db):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to access this chat"
        )

    # 2. Получаем ключ шифрования для этой комнаты
    room_key = get_or_create_room_key(room_id, db)

    # 3. Получаем сообщения из базы
    query = db.query(Message).filter(Message.room_id == room_id)

    total = query.count()
    messages = (
        query.order_by(Message.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # 4. Расшифровываем сообщения перед отправкой пользователю
    decrypted_messages = []
    for m in messages:
        content = m.content
        if m.is_encrypted and content:
            try:
                content = decrypt_content(m.content, room_key)
            except Exception as e:
                logger.error(f"Failed to decrypt message {m.id} in room {room_id}: {e}")
                content = "[Сообщение не удалось расшифровать]"

        decrypted_messages.append(
            MessageResponse(
                id=m.id,
                room_id=m.room_id,
                sender_id=m.sender_id,
                sender_username=m.sender_username,
                sender_full_name=m.sender_full_name,
                content=content,                    # ← расшифрованное содержимое
                created_at=to_moscow(m.created_at).isoformat(),
                edited_at=to_moscow(m.edited_at).isoformat() if m.edited_at else None
            )
        )

    return ChatHistoryResponse(
        messages=decrypted_messages,
        has_more=(offset + limit) < total
    )

@app.get("/my-chats")
async def get_my_chats(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chats = []

    # 1. Групповой чат
    if current_user.group_number and current_user.role in ["student", "group_leader"]:
        chats.append({
            "room_id": f"group:{current_user.group_number}",
            "name": f"Группа {current_user.group_number}",
            "type": "group",
            "unread": 0
        })

    # 2. Общий чат преподавателей
    if current_user.role in ["teacher", "admin"]:
        chats.append({
            "room_id": "teachers",
            "name": "Чат преподавателей",
            "type": "teachers",
            "unread": 0
        })

    # 3. Старшина группы — всегда виден студенту/старосте своей группы, даже без переписки
    if current_user.role in ["student", "group_leader"] and current_user.group_number:
        leader = db.query(UserDB).filter(
            UserDB.role == "group_leader",
            UserDB.group_number == current_user.group_number,
            UserDB.id != current_user.id
        ).first()
        if leader:
            user1 = min(current_user.id, leader.id)
            user2 = max(current_user.id, leader.id)
            display_name = leader.full_name.strip() if leader.full_name else leader.username
            chats.append({
                "room_id": f"private:{user1}_{user2}",
                "name": f"{display_name} (староста)",
                "type": "private",
                "leader_id": leader.id,
                "unread": 0
            })

    # 4. Личные чаты — показываем только те, где уже есть переписка
    partners = []
    if current_user.role in ["student", "group_leader"]:
        partners = db.query(UserDB).filter(UserDB.role.in_(["teacher", "admin"])).all()
    elif current_user.role in ["teacher", "admin"]:
        partners = db.query(UserDB).filter(
            UserDB.role.in_(["student", "group_leader", "teacher"]),
            UserDB.id != current_user.id
        ).all()

    if partners:
        partner_by_room = {}
        for partner in partners:
            user1 = min(current_user.id, partner.id)
            user2 = max(current_user.id, partner.id)
            partner_by_room[f"private:{user1}_{user2}"] = partner

        active_room_ids = {
            row[0] for row in db.query(Message.room_id)
                .filter(Message.room_id.in_(list(partner_by_room.keys())))
                .distinct()
                .all()
        }

        existing_room_ids = {c["room_id"] for c in chats}

        for room_id, partner in partner_by_room.items():
            if room_id not in active_room_ids or room_id in existing_room_ids:
                continue

            display_name = partner.full_name.strip() if partner.full_name else partner.username

            if current_user.role in ["student", "group_leader"]:
                chats.append({
                    "room_id": room_id,
                    "name": display_name,
                    "type": "private",
                    "teacher_id": partner.id,
                    "unread": 0
                })
            elif partner.role == "teacher":
                chats.append({
                    "room_id": room_id,
                    "name": display_name,
                    "type": "private",
                    "teacher_id": partner.id,
                    "unread": 0
                })
            else:
                label = f"{display_name} ({partner.group_number})" if partner.group_number else display_name
                chats.append({
                    "room_id": room_id,
                    "name": label,
                    "type": "private",
                    "student_id": partner.id,
                    "unread": 0
                })

    # Сортировка: сначала группа, потом общий чат, потом личные
    type_order = {"group": 0, "teachers": 1, "private": 2}
    chats.sort(key=lambda x: type_order.get(x["type"], 3))

    return chats


@app.get("/chat/contacts")
async def get_chat_contacts(
    query: str | None = None,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Список людей, с которыми можно начать новый личный чат (для поиска собеседника)"""
    results = []

    if current_user.role in ["student", "group_leader"]:
        q = db.query(UserDB).filter(UserDB.role.in_(["teacher", "admin"]))
        if query:
            like = f"%{query}%"
            q = q.filter((UserDB.full_name.ilike(like)) | (UserDB.username.ilike(like)))
        contacts = q.all()

        for c in contacts:
            user1, user2 = min(current_user.id, c.id), max(current_user.id, c.id)
            display_name = c.full_name.strip() if c.full_name else c.username
            results.append({
                "user_id": c.id,
                "room_id": f"private:{user1}_{user2}",
                "name": display_name,
                "subtitle": c.department,
            })

    elif current_user.role in ["teacher", "admin"]:
        q = db.query(UserDB).filter(
            UserDB.role.in_(["student", "group_leader", "teacher"]),
            UserDB.id != current_user.id
        )
        if query:
            like = f"%{query}%"
            q = q.filter(
                (UserDB.full_name.ilike(like)) |
                (UserDB.username.ilike(like)) |
                (UserDB.group_number.ilike(like))
            )
        contacts = q.all()

        for c in contacts:
            user1, user2 = min(current_user.id, c.id), max(current_user.id, c.id)
            display_name = c.full_name.strip() if c.full_name else c.username
            subtitle = c.group_number if c.role in ("student", "group_leader") else (c.department or "Преподаватель")
            results.append({
                "user_id": c.id,
                "room_id": f"private:{user1}_{user2}",
                "name": display_name,
                "subtitle": subtitle,
            })

    results.sort(key=lambda x: x["name"])
    return results


class ConnectionManager:
    def __init__(self):
        # room_id → set of (user_id, username, full_name)
        self.active_users: dict[str, set[tuple[int, str, str]]] = {}
        # room_id → list of WebSocket connections
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, user: UserDB):
        """Подключаем пользователя к комнате"""
        await websocket.accept()

        if room_id not in self.active_users:
            self.active_users[room_id] = set()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []

        user_tuple = (user.id, user.username, user.full_name or user.username)
        self.active_users[room_id].add(user_tuple)
        self.active_connections[room_id].append(websocket)

        await self.broadcast_online(room_id)

    async def disconnect(self, websocket: WebSocket, room_id: str, user: UserDB):
        """Отключаем пользователя"""
        changed = False

        if room_id in self.active_users:
            user_tuple = (user.id, user.username, user.full_name or user.username)
            if user_tuple in self.active_users[room_id]:
                self.active_users[room_id].discard(user_tuple)
                changed = True

            # Если в комнате больше никого нет — удаляем комнату
            if not self.active_users[room_id]:
                del self.active_users[room_id]

        if room_id in self.active_connections:
            try:
                self.active_connections[room_id].remove(websocket)
            except ValueError:
                pass
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

        if changed:
            await self.broadcast_online(room_id)

    def get_online_list(self, room_id: str) -> list[dict]:
        users = self.active_users.get(room_id, set())
        return [{"user_id": uid, "username": un, "full_name": fn} for uid, un, fn in users]

    async def broadcast_online(self, room_id: str):
        await self.broadcast({"type": "online_users", "users": self.get_online_list(room_id)}, room_id)

    async def broadcast(self, message: dict, room_id: str):
        """Рассылаем обычное сообщение всем в комнате"""
        if room_id not in self.active_connections:
            return

        disconnected = []
        for websocket in self.active_connections[room_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Broadcasting error: {e}")
                disconnected.append(websocket)

        # Удаляем закрытые соединения
        for websocket in disconnected:
            try:
                self.active_connections[room_id].remove(websocket)
            except ValueError:
                pass

manager = ConnectionManager()


@app.websocket("/ws/chat")
async def websocket_endpoint(
    websocket: WebSocket,
    room: str = Query(...),
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    if not token:
        await websocket.close(code=4001)
        logger.warning("WebSocket: No token provided")
        return

    try:
        current_user = await get_current_user(token=token, db=db)
    except Exception as e:
        await websocket.close(code=4001)
        logger.warning(f"WebSocket: Invalid token - {e}")
        return

    if not check_room_access(room, current_user, db):
        await websocket.close(code=4003)
        logger.warning(f"WebSocket: Access denied for user {current_user.username} to room {room}")
        return

    logger.info(f"WebSocket: User {current_user.username} connecting to room {room}")

    # Получаем ключ шифрования для этой комнаты
    room_key = get_or_create_room_key(room, db)

    await manager.connect(websocket, room, current_user)

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action", "send")

            # === ОТПРАВКА НОВОГО СООБЩЕНИЯ ===
            if action == "send":
                raw_content = data.get("content", "").strip()

                if not raw_content:
                    await websocket.send_json({
                        "type": "error",
                        "content": "Сообщение не может быть пустым"
                    })
                    continue

                if not await check_chat_rate_limit(current_user.id):
                    await websocket.send_json({
                        "type": "error",
                        "content": "Вы отправляете сообщения слишком часто. Подождите немного."
                    })
                    continue

                content = sanitize_message(raw_content)
                encrypted_content = encrypt_content(content, room_key)

                db_message = Message(
                    room_id=room,
                    sender_id=current_user.id,
                    sender_username=current_user.username,
                    sender_full_name=current_user.full_name or current_user.username,
                    content=encrypted_content,             # ← сохраняем зашифрованное
                    is_encrypted=True
                )
                db.add(db_message)
                db.commit()
                db.refresh(db_message)

                message = {
                    "type": "message",
                    "id": db_message.id,
                    "room_id": room,
                    "sender_id": current_user.id,
                    "sender_username": current_user.username,
                    "sender_full_name": current_user.full_name or current_user.username,
                    "content": content,                    # клиенту отправляем открытый текст
                    "created_at": to_moscow(db_message.created_at).isoformat()
                }

                await manager.broadcast(message, room)

            # === РЕДАКТИРОВАНИЕ СООБЩЕНИЯ (только своё, в течение 24 часов) ===
            elif action == "edit":
                message_id = data.get("message_id")
                new_content_raw = (data.get("content") or "").strip()

                if not message_id or not new_content_raw:
                    await websocket.send_json({"type": "error", "content": "Некорректные данные для редактирования"})
                    continue

                db_message = db.query(Message).filter(Message.id == message_id, Message.room_id == room).first()
                if not db_message:
                    await websocket.send_json({"type": "error", "content": "Сообщение не найдено"})
                    continue

                if db_message.sender_id != current_user.id:
                    await websocket.send_json({"type": "error", "content": "Нельзя редактировать чужое сообщение"})
                    continue

                created_at = db_message.created_at
                if created_at.tzinfo is None:
                    created_at = pytz.UTC.localize(created_at)
                if datetime.now(pytz.UTC) - created_at > timedelta(hours=24):
                    await websocket.send_json({"type": "error", "content": "Редактирование доступно только в течение 24 часов после отправки"})
                    continue

                new_content = sanitize_message(new_content_raw)
                db_message.content = encrypt_content(new_content, room_key)
                db_message.edited_at = to_utc(datetime.now(MOSCOW_TZ))
                db.commit()

                await manager.broadcast({
                    "type": "message_edited",
                    "id": db_message.id,
                    "content": new_content,
                    "edited_at": to_moscow(db_message.edited_at).isoformat()
                }, room)

            # === УДАЛЕНИЕ СООБЩЕНИЯ (только своё) ===
            elif action == "delete":
                message_id = data.get("message_id")
                if not message_id:
                    continue

                db_message = db.query(Message).filter(Message.id == message_id, Message.room_id == room).first()
                if not db_message:
                    await websocket.send_json({"type": "error", "content": "Сообщение не найдено"})
                    continue

                if db_message.sender_id != current_user.id:
                    await websocket.send_json({"type": "error", "content": "Нельзя удалить чужое сообщение"})
                    continue

                db.delete(db_message)
                db.commit()

                await manager.broadcast({
                    "type": "message_deleted",
                    "id": message_id
                }, room)

            else:
                await websocket.send_json({"type": "error", "content": "Неизвестное действие"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket: User {current_user.username} disconnected from room {room}")
        await manager.disconnect(websocket, room, current_user)

    except Exception as e:
        logger.error(f"WebSocket error for user {current_user.username} in room {room}: {e}")
        await manager.disconnect(websocket, room, current_user)

    finally:
        await manager.disconnect(websocket, room, current_user)

# ====================== СПИСОК ПРЕПОДАВАТЕЛЕЙ ДЛЯ СТУДЕНТА ======================

@app.get("/teachers", response_model=list[TeacherResponse])
async def get_teachers(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Возвращает список преподавателей, доступных для общения"""
    
    teachers = db.query(UserDB).filter(UserDB.role == "teacher").all()

    return [
        TeacherResponse(
            id=t.id,
            username=t.username,
            full_name=t.full_name or t.username,
            department=t.department
        )
        for t in teachers
    ]

@app.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = db.query(UserDB).filter(UserDB.username == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        # Создаём новые токены
        new_access_token = create_access_token(data={"sub": user.username})
        new_refresh_token = create_refresh_token(data={"sub": user.username})

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

@app.post("/logout")
async def logout(
    current_user: UserDB = Depends(get_current_user),
    access_token: str = Depends(oauth2_scheme),
    refresh_token: str = Body(None, embed=True)   # refresh_token можно передавать из фронта
):
    """Отзывает текущий access и refresh токены при выходе"""
    
    # Отзываем access token
    await add_token_to_blacklist(access_token, expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 60)

    # Если фронт передал refresh_token — отзываем и его
    if refresh_token:
        # Refresh токен живёт 7 дней = 604800 секунд
        await add_token_to_blacklist(refresh_token, expires_in=REFRESH_TOKEN_EXPIRE_DAYS * 86400 + 3600)

    return {"message": "Successfully logged out. All tokens revoked."}

@app.get("/chat/online/{room_id}")
async def get_online_users(
    room_id: str,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not check_room_access(room_id, current_user, db):
        raise HTTPException(status_code=403, detail="Access denied")

    users = manager.active_users.get(room_id, set())
    return {
        "users": [
            {"user_id": uid, "username": un, "full_name": fn}
            for uid, un, fn in users
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
