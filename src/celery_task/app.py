from celery import Celery
from celery.schedules import crontab

app = Celery(
    'cinema_tasks',
    broker='redis://redis_cinema:6379/0',
    backend='redis://redis_cinema:6379/1',
    include=['src.celery_task.tasks']
)

app.conf.timezone = 'UTC'
app.conf.beat_schedule = {
    'delete-expired-tokens': {
        'task': 'src.celery.tasks.delete_expired_tokens',
        'schedule': crontab(minute=0),
    },
}
