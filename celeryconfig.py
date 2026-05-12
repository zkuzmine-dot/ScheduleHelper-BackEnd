from celery.schedules import crontab

beat_schedule = {
    'check-notifications-every-5-minutes': {
        'task': 'notifier.check_and_notify',
        'schedule': crontab(minute='*/5'),  # Каждые 5 минут
    },
}
timezone = 'Europe/Moscow'
enable_utc = False