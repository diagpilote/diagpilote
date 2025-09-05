import os, time
from redis import Redis
from rq import Worker, Queue, Connection
# Préimporte les fonctions
try:
    import app.tasks  # noqa: F401
except Exception as e:
    print("WARN: could not import app.tasks:", e)

redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = int(os.getenv("REDIS_PORT", 6379))
listen = ["default"]

conn = Redis(host=redis_host, port=redis_port)
with Connection(conn):
    Worker(list(map(Queue, listen))).work(with_scheduler=True)
