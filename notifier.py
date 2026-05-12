import json
import logging
from datetime import datetime, timedelta
import pytz
from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm.attributes import flag_modified
from main import UserDB, Event, send_telegram_notification, to_utc, to_moscow, MOSCOW_TZ
from dotenv import load_dotenv
import os
import asyncio

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация базы данных
DATABASE_URL = os.getenv("DATABASE_URL")

# Конфигурация Celery
celery = Celery(
    'notifier',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0',
    include=['notifier'],
    broker_connection_retry_on_startup=True
)
celery.config_from_object('celeryconfig')

# Создаем подключение к базе данных с логированием запросов
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

@celery.task
def check_and_notify():
    db: Session = SessionLocal()
    try:
        users = db.query(UserDB).filter(UserDB.group_number.isnot(None)).all()
        now_moscow = datetime.now(MOSCOW_TZ)
        now_utc = to_utc(now_moscow)
        logger.info(f"Текущее время (Moscow): {now_moscow}, (UTC): {now_utc}")

        if not users:
            logger.info("Пользователи с group_number не найдены")
            return {"status": "completed"}

        # Используем существующий цикл событий или создаём новый
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def process_user(user):
            logger.info(f"Обработка пользователя: {user.username}, telegram_id: {user.telegram_id}, group_number: {user.group_number}")
            if not user.telegram_id:
                logger.warning(f"Пользователь {user.username} не имеет telegram_id")
                return

            notification_settings = {}
            if user.notification_settings:
                try:
                    notification_settings = json.loads(user.notification_settings)
                except json.JSONDecodeError:
                    logger.error(f"Некорректный JSON в notification_settings для пользователя {user.username}")
                    return

            event_reminder = notification_settings.get("event_reminder", 4500)
            last_notified_event_ids = user.last_notified_event_ids or []
            logger.info(f"event_reminder: {event_reminder}, last_notified_event_ids: {last_notified_event_ids}")

            # Пропускаем уведомления, если event_reminder = -1
            if event_reminder == -1:
                logger.info(f"Уведомления для пользователя {user.username} отключены (event_reminder = -1)")
                return

            events = (
                db.query(Event)
                .filter(
                    Event.is_active == True,
                    Event.group_number == user.group_number,
                    Event.start_datetime >= now_utc,
                    Event.start_datetime <= to_utc(now_moscow + timedelta(minutes=event_reminder))
                )
                .all()
            )

            if not events:
                logger.info(f"События для группы {user.group_number} не найдены")
                return

            # Список новых ID событий, которые нужно добавить в last_notified_event_ids
            new_notified_event_ids = []

            for event in events:
                event_time_utc = event.start_datetime
                event_time_moscow = to_moscow(event_time_utc)
                logger.info(f"Найдено событие: id={event.id}, title={event.title}, start_datetime (UTC)={event_time_utc}, (Moscow)={event_time_moscow}, group_number={event.group_number}")
                if event.id not in last_notified_event_ids:
                    event_time = event_time_moscow.strftime("%Y-%m-%d %H:%M")
                    message = (
                        f"Напоминание о событии!\n"
                        f"Событие: {event.title}\n"
                        f"Тип: {event.event_type}\n"
                        f"Время: {event_time}\n"
                        f"Группа: {event.group_number}\n"
                        f"Описание: {event.description or '-'}"
                    )
                    try:
                        await send_telegram_notification(user.telegram_id, message)
                        new_notified_event_ids.append(event.id)
                        logger.info(f"Уведомление отправлено пользователю {user.username} о событии {event.id}")
                    except Exception as e:
                        logger.error(f"Ошибка при отправке уведомления для события {event.id}: {e}")

            # Если были отправлены уведомления, обновляем last_notified_event_ids
            if new_notified_event_ids:
                logger.info(f"До обновления last_notified_event_ids: {last_notified_event_ids}")
                last_notified_event_ids.extend(new_notified_event_ids)
                user.last_notified_event_ids = last_notified_event_ids
                logger.info(f"После обновления в памяти last_notified_event_ids: {user.last_notified_event_ids}")
                db.add(user)  # Явно помечаем объект как изменённый
                flag_modified(user, "last_notified_event_ids")  # Явно помечаем JSON-поле как изменённое
                db.flush()    # Подготавливаем изменения
                db.commit()   # Фиксируем изменения
                logger.info(f"Обновлённый last_notified_event_ids для {user.username}: {user.last_notified_event_ids}")

        # Собираем все задачи для асинхронной обработки
        tasks = [process_user(user) for user in users]
        loop.run_until_complete(asyncio.gather(*tasks))

        # Закрываем цикл только если мы его создавали
        if loop != asyncio.get_event_loop():
            loop.close()

        return {"status": "completed"}

    except Exception as e:
        logger.error(f"Ошибка в check_and_notify: {e}")
        if db:
            db.rollback()
        raise
    finally:
        if db:
            db.close()
