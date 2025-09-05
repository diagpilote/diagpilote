import os, time
from redis import Redis
from rq import Worker, Queue, Connection

# Préimporte les fonctions du module de tâches, sans casser au démarrage
try:
    import app.tasks  # noqa: F401
except Exception as e:
    print("WARN: could not import app.tasks:", e)

redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = int(os.getenv("REDIS_PORT", 6379))
listen = ["default"]

def wait_for_redis(host, port, timeout=60):
    start = time.time()
    while True:
        try:
            Redis(host=host, port=port).ping()
            return
        except Exception as e:
            if time.time() - start > timeout:
                print(f"ERROR: Redis still unavailable after {timeout}s: {e}")
                raise
            print("Waiting for Redis...", e)
            time.sleep(2)

wait_for_redis(redis_host, redis_port)
conn = Redis(host=redis_host, port=redis_port)
with Connection(conn):
    Worker(list(map(Queue, listen))).work(with_scheduler=True)
