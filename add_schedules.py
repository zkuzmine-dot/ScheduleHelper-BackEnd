from sqlalchemy import create_engine, Column, Integer, String, DateTime, Time, Date, Boolean, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
from datetime import datetime, time, date
import pytz
from dotenv import load_dotenv
import os

# Загрузка переменных окружения
load_dotenv()

# Конфигурация базы данных
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Base = declarative_base()

# Временная зона
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# Модель UserDB
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
    created_at = Column(DateTime, default=lambda: datetime.now(MOSCOW_TZ))
    last_login = Column(DateTime, nullable=True)

# Модель Schedule
class Schedule(Base):
    __tablename__ = 'schedules'
    id = Column(Integer, primary_key=True)
    group_number = Column(String(20), nullable=False)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    lesson_type = Column(String)
    subject = Column(String(100), nullable=False)
    classroom = Column(String(50))
    teacher_name = Column(String(100))
    subgroup = Column(Integer)
    week_type = Column(String)
    valid_from = Column(Date)
    valid_to = Column(Date)
    is_active = Column(Boolean, default=True)

# Создание таблиц
Base.metadata.create_all(bind=engine)

# Создание сессии
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# Хеширование пароля
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Данные администратора
admin_data = {
    "username": "admin",
    "password": "admin123",  # Пароль будет захеширован
    "telegram_id": 703026424,  # Укажите реальный Telegram ID
    "role": "admin",
    "group_number": "ИБ-31БО",
    "subgroup": 1,
    "department": "Администрация",
    "notification_settings": '{"event_reminder": 4000}',
    "last_notified_event_ids": [],
    "created_at": datetime.now(MOSCOW_TZ),
    "last_login": None
}

# Данные расписания
schedules = [
    # Числитель (numerator) для ИБ-11БО
    {"group_number": "ИБ-11БО", "day_of_week": 1, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Иностранный язык", "classroom": "208", "teacher_name": "Умнова И.В.", "subgroup": 1, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 1, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Математический анализ", "classroom": "418", "teacher_name": "Ухалов А.Ю.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 1, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Математический анализ", "classroom": "401", "teacher_name": "Литвинов В.В.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 2, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Языки программирования", "classroom": "415", "teacher_name": "Власова О.В.", "subgroup": 2, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 2, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "practice", "subject": "Прикладная физическая культура", "classroom": "Спортзал", "teacher_name": "ИБ-11БО", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 2, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Основы экономики и принятия решений", "classroom": "409", "teacher_name": "Зеткина О.В.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 2, "start_time": time(16, 50), "end_time": time(18, 25), "lesson_type": "lecture", "subject": "История России с XIX века", "classroom": "414", "teacher_name": "Смирнов Я.А.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 3, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "История России с XIX века", "classroom": "418", "teacher_name": "Смирнов Я.А.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 3, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Алгебра", "classroom": "420", "teacher_name": "Сорокина М.Е.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 3, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Алгебра", "classroom": "420", "teacher_name": "Куликов Е.А.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 3, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Алгебра", "classroom": "420", "teacher_name": "Куликов Е.А.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 3, "start_time": time(16, 50), "end_time": time(18, 25), "lesson_type": "lecture", "subject": "Деловое общение на русском языке", "classroom": "414", "teacher_name": "Виноградова М.В.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 4, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Безопасность жизнедеятельности", "classroom": "410", "teacher_name": "Петроченко Е.П.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 4, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "practice", "subject": "Прикладная физическая культура", "classroom": "Спортзал", "teacher_name": "ИБ-11БО", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 4, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Языки программирования", "classroom": "418", "teacher_name": "Власова О.В.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 4, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Языки программирования", "classroom": "408", "teacher_name": "Власова О.В.", "subgroup": 1, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 4, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Безопасность жизнедеятельности", "classroom": "410", "teacher_name": "Петроченко Е.П.", "subgroup": 2, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 4, "start_time": time(16, 50), "end_time": time(18, 25), "lesson_type": "lecture", "subject": "Иностранный язык", "classroom": "305", "teacher_name": "Мастакова Н.К.", "subgroup": 2, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 5, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Математический анализ", "classroom": "420", "teacher_name": "Литвинов В.В.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 5, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Физика", "classroom": "315", "teacher_name": "Романов Д.Ф.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 5, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Физика", "classroom": "315", "teacher_name": "Романов Д.Ф.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    # Знаменатель (denominator) для ИБ-11БО
    {"group_number": "ИБ-11БО", "day_of_week": 1, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Математический анализ", "classroom": "401", "teacher_name": "Литвинов В.В.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 1, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Иностранный язык", "classroom": "208", "teacher_name": "Умнова И.В.", "subgroup": 1, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 1, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Иностранный язык", "classroom": "305", "teacher_name": "Мастакова Н.К.", "subgroup": 2, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 1, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Математический анализ", "classroom": "418", "teacher_name": "Ухалов А.Ю.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 1, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "История России с XIX века", "classroom": "418", "teacher_name": "Смирнов Я.А.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 1, "start_time": time(16, 50), "end_time": time(18, 25), "lesson_type": "lecture", "subject": "История России с XIX века", "classroom": "418", "teacher_name": "Смирнов Я.А.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 2, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Языки программирования", "classroom": "415", "teacher_name": "Власова О.В.", "subgroup": 2, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 2, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "practice", "subject": "Прикладная физическая культура", "classroom": "Спортзал", "teacher_name": "ИБ-11БО", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 2, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Основы экономики и принятия решений", "classroom": "412", "teacher_name": "Зеткина О.В.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 2, "start_time": time(16, 50), "end_time": time(18, 25), "lesson_type": "lecture", "subject": "История России с XIX века", "classroom": "414", "teacher_name": "Смирнов Я.А.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 3, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Алгебра", "classroom": "420", "teacher_name": "Сорокина М.Е.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 3, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Алгебра", "classroom": "420", "teacher_name": "Сорокина М.Е.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 3, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Алгебра", "classroom": "420", "teacher_name": "Куликов Е.А.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 3, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Математический анализ", "classroom": "418", "teacher_name": "Ухалов А.Ю.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 3, "start_time": time(16, 50), "end_time": time(18, 25), "lesson_type": "lecture", "subject": "Деловое общение на русском языке", "classroom": "414", "teacher_name": "Виноградова М.В.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 4, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Языки программирования", "classroom": "408", "teacher_name": "Власова О.В.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 4, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "practice", "subject": "Прикладная физическая культура", "classroom": "Спортзал", "teacher_name": "ИБ-11БО", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 4, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Языки программирования", "classroom": "418", "teacher_name": "Власова О.В.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 4, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Безопасность жизнедеятельности", "classroom": "410", "teacher_name": "Петроченко Е.П.", "subgroup": 1, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 4, "start_time": time(18, 35), "end_time": time(20, 0), "lesson_type": "lecture", "subject": "Иностранный язык", "classroom": "412", "teacher_name": "Виноградова М.В.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 5, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Физика", "classroom": "315", "teacher_name": "Романов Д.Ф.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-11БО", "day_of_week": 5, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Физика", "classroom": "315", "teacher_name": "Романов Д.Ф.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    # Числитель (numerator) для ИБ-21БО
    {"group_number": "ИБ-21БО", "day_of_week": 1, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Иностранный язык", "classroom": "418", "teacher_name": "Чвягина Т.В.", "subgroup": 2, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 1, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Дискретная математика", "classroom": "420", "teacher_name": "Безуглова И.И.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 2, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Электротехника", "classroom": "107а (1 корпус)", "teacher_name": "Колбнева Н.Ю.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 2, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Электроника и схемотехника", "classroom": "207 (2 корпус)", "teacher_name": "Артёмова Т.К.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 2, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Теория кодирования", "classroom": "319", "teacher_name": "Казарин Л.С.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 4, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Дискретная математика", "classroom": "407", "teacher_name": "Безуглова И.И.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 4, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "practice", "subject": "Прикладная физическая культура", "classroom": "Спортзал", "teacher_name": "ИБ-21БО", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 4, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Основы информационной безопасности", "classroom": "319", "teacher_name": "Белов А.Р.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 4, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Иностранный язык", "classroom": "427", "teacher_name": "Москалева Н.В.", "subgroup": 1, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 5, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Теория функций комплексной переменной", "classroom": "409", "teacher_name": "Невский М.В.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 5, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Теория функций комплексной переменной", "classroom": "409", "teacher_name": "Невский М.В.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 5, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Теория чисел", "classroom": "319", "teacher_name": "Казарин Л.С.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 5, "start_time": time(18, 35), "end_time": time(20, 0), "lesson_type": "lecture", "subject": "Компьютерные сети", "classroom": "online", "teacher_name": "Семакин И.Д.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 6, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Компьютерные сети", "classroom": "314", "teacher_name": "Семакин И.Д.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 6, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Операционные системы", "classroom": "314", "teacher_name": "Семакин И.Д.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 6, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Операционные системы", "classroom": "412", "teacher_name": "Савинов Д.А.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 6, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Введение в разработку приложений под платформу .Net", "classroom": "403", "teacher_name": "Алексеев С.С.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 6, "start_time": time(16, 50), "end_time": time(18, 25), "lesson_type": "lecture", "subject": "Введение в разработку приложений под платформу .Net", "classroom": "403", "teacher_name": "Алексеев С.С.", "subgroup": 1, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 6, "start_time": time(18, 35), "end_time": time(20, 0), "lesson_type": "lecture", "subject": "Введение в разработку приложений под платформу .Net", "classroom": "403", "teacher_name": "Алексеев С.С.", "subgroup": 1, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    # Знаменатель (denominator) для ИБ-21БО
    {"group_number": "ИБ-21БО", "day_of_week": 1, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Иностранный язык", "classroom": "427", "teacher_name": "Москалева Н.В.", "subgroup": 1, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 1, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Иностранный язык", "classroom": "416", "teacher_name": "Чвягина Т.В.", "subgroup": 2, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 1, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Теория кодирования", "classroom": "319", "teacher_name": "Заводчиков М.А.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 1, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Дискретная математика", "classroom": "420", "teacher_name": "Безуглова И.И.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 2, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Электроника и схемотехника", "classroom": "207 (2 корпус)", "teacher_name": "Артёмова Т.К.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 2, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Теория кодирования", "classroom": "319", "teacher_name": "Казарин Л.С.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 2, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Теория чисел", "classroom": "319", "teacher_name": "Казарин Л.С.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 4, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Дискретная математика", "classroom": "407", "teacher_name": "Безуглова И.И.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 4, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "practice", "subject": "Прикладная физическая культура", "classroom": "Спортзал", "teacher_name": "ИБ-21БО", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 4, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Основы информационной безопасности", "classroom": "319", "teacher_name": "Белов А.Р.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 5, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Теория функций комплексной переменной", "classroom": "409", "teacher_name": "Невский М.В.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 5, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Теория чисел", "classroom": "319", "teacher_name": "Казарин Л.С.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 5, "start_time": time(18, 35), "end_time": time(20, 0), "lesson_type": "lecture", "subject": "Компьютерные сети", "classroom": "online", "teacher_name": "Семакин И.Д.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 6, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Компьютерные сети", "classroom": "314", "teacher_name": "Семакин И.Д.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 6, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Операционные системы", "classroom": "314", "teacher_name": "Семакин И.Д.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 6, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Операционные системы", "classroom": "412", "teacher_name": "Савинов Д.А.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 6, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Введение в разработку приложений под платформу .Net", "classroom": "403", "teacher_name": "Алексеев С.С.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 6, "start_time": time(16, 50), "end_time": time(18, 25), "lesson_type": "lecture", "subject": "Введение в разработку приложений под платформу .Net", "classroom": "403", "teacher_name": "Алексеев С.С.", "subgroup": 2, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-21БО", "day_of_week": 6, "start_time": time(18, 35), "end_time": time(20, 0), "lesson_type": "lecture", "subject": "Введение в разработку приложений под платформу .Net", "classroom": "403", "teacher_name": "Алексеев С.С.", "subgroup": 2, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    # Числитель (numerator) для ИБ-31БО
    {"group_number": "ИБ-31БО", "day_of_week": 1, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Теория информации", "classroom": "218 (2 корпус)", "teacher_name": "Гвоздарёв А.С.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 2, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Аппаратные средства вычислительной техники", "classroom": "207 (2 корпус)", "teacher_name": "Артёмова Т.К.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 2, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Программно-аппаратные средства защиты информации", "classroom": "317", "teacher_name": "Фролов Д.Г.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 2, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Программно-аппаратные средства защиты информации", "classroom": "317", "teacher_name": "Фролов Д.Г.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 3, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Аппаратные средства вычислительной техники", "classroom": "107а (1 корпус)", "teacher_name": "Афонин А.А.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 3, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Теория вероятностей и математическая статистика", "classroom": "412", "teacher_name": "Бережной Е.И.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 3, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Сети и системы передачи информации", "classroom": "317", "teacher_name": "Захаров А.С.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 4, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Основы JavaScript", "classroom": "405", "teacher_name": "Ковалева А.М.", "subgroup": 2, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 4, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Основы JavaScript", "classroom": "405", "teacher_name": "Ковалева А.М.", "subgroup": 2, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 4, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Методы программирования", "classroom": "412", "teacher_name": "Якимова О.П.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 5, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Системы управления базами данных", "classroom": "403", "teacher_name": "Власова О.В.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 5, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Теория вероятностей и математическая статистика", "classroom": "420", "teacher_name": "Дундуков М.Ю.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 5, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Системы управления базами данных", "classroom": "403", "teacher_name": "Власова О.В.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 6, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Разработка web-приложений в среде ASP.Net", "classroom": "402", "teacher_name": "Левшинский А.С.", "subgroup": 1, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 6, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Разработка web-приложений в среде ASP.Net", "classroom": "402", "teacher_name": "Левшинский А.С.", "subgroup": 1, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 6, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Методы программирования", "classroom": "403", "teacher_name": "Бурганов В.О.", "subgroup": None, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 6, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Методы программирования", "classroom": "403", "teacher_name": "Бурганов В.О.", "subgroup": 1, "week_type": "numerator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    # Знаменатель (denominator) для ИБ-31БО
    {"group_number": "ИБ-31БО", "day_of_week": 1, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Теория информации", "classroom": "218 (2 корпус)", "teacher_name": "Гвоздарёв А.С.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 1, "start_time": time(16, 50), "end_time": time(18, 25), "lesson_type": "lecture", "subject": "Теория информации", "classroom": "218 (2 корпус)", "teacher_name": "Гвоздарёв А.С.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 2, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Аппаратные средства вычислительной техники", "classroom": "207 (2 корпус)", "teacher_name": "Артёмова Т.К.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 2, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Программно-аппаратные средства защиты информации", "classroom": "314", "teacher_name": "Фролов Д.Г.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 3, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Аппаратные средства вычислительной техники", "classroom": "107а (1 корпус)", "teacher_name": "Афонин А.А.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 3, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Теория вероятностей и математическая статистика", "classroom": "412", "teacher_name": "Бережной Е.И.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 3, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Сети и системы передачи информации", "classroom": "317", "teacher_name": "Захаров А.С.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 4, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Основы JavaScript", "classroom": "405", "teacher_name": "Ковалева А.М.", "subgroup": 2, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 4, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Основы JavaScript", "classroom": "405", "teacher_name": "Ковалева А.М.", "subgroup": 2, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 4, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Методы программирования", "classroom": "412", "teacher_name": "Якимова О.П.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 5, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Системы управления базами данных", "classroom": "403", "teacher_name": "Власова О.В.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 5, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Системы управления базами данных", "classroom": "403", "teacher_name": "Власова О.В.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 5, "start_time": time(15, 5), "end_time": time(16, 40), "lesson_type": "lecture", "subject": "Теория вероятностей и математическая статистика", "classroom": "420", "teacher_name": "Дундуков М.Ю.", "subgroup": None, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 6, "start_time": time(9, 0), "end_time": time(10, 35), "lesson_type": "lecture", "subject": "Разработка web-приложений в среде ASP.Net", "classroom": "402", "teacher_name": "Левшинский А.С.", "subgroup": 1, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 6, "start_time": time(10, 45), "end_time": time(12, 20), "lesson_type": "lecture", "subject": "Разработка web-приложений в среде ASP.Net", "classroom": "402", "teacher_name": "Левшинский А.С.", "subgroup": 1, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
    {"group_number": "ИБ-31БО", "day_of_week": 6, "start_time": time(13, 20), "end_time": time(14, 55), "lesson_type": "lecture", "subject": "Методы программирования", "classroom": "403", "teacher_name": "Бурганов В.О.", "subgroup": 2, "week_type": "denominator", "valid_from": date(2026, 1, 1), "valid_to": date(2026, 12, 31), "is_active": True},
]

# Логика добавления данных
try:
    # Проверка, существует ли администратор
    existing_admin = db.query(UserDB).filter(UserDB.username == admin_data["username"]).first()
    if existing_admin:
        print(f"Администратор с username={admin_data['username']} уже существует. Пропускаем создание.")
    else:
        # Хешируем пароль
        hashed_password = pwd_context.hash(admin_data["password"])
        admin_data["password_hash"] = hashed_password
        del admin_data["password"]  # Удаляем пароль из словаря, так как нужен password_hash
        db_admin = UserDB(**admin_data)
        db.add(db_admin)
        print(f"Администратор {admin_data['username']} успешно создан.")

    # Очищаем старые расписания и добавляем новые
    db.query(Schedule).delete()
    print("Старые расписания удалены.")
    
    # Собираем все группы из schedules
    groups = {schedule["group_number"] for schedule in schedules}
    
    # Добавляем расписание для каждой группы
    for group in groups:
        # Фильтруем расписание для текущей группы
        group_schedules = [schedule for schedule in schedules if schedule["group_number"] == group]
        for schedule_data in group_schedules:
            db_schedule = Schedule(**schedule_data)
            db.add(db_schedule)
        print(f"Успешно добавлено {len(group_schedules)} записей расписания для группы {group}.")

    # Коммит изменений
    db.commit()

except Exception as e:
    print(f"Ошибка при добавлении данных: {e}")
    db.rollback()

finally:
    db.close()
