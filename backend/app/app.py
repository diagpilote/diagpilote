from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from rq import Queue
from redis import Redis
from apscheduler.schedulers.background import BackgroundScheduler
import os, datetime

# imports locaux
from utils.mailer import send_email
from .tasks import generate_pdf, ocr_process
from .agenda_module.agenda import agenda_bp
# --- CONFIG FLASK ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'postgresql+psycopg2://postgres:postgres@db:5432/diagpilote'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Blueprint Agenda ---
app.register_blueprint(agenda_bp, url_prefix="/kanban")

# --- REDIS & QUEUE ---
redis_conn = Redis(host=os.getenv('REDIS_HOST', 'redis'), port=int(os.getenv('REDIS_PORT', 6379)))
queue = Queue(connection=redis_conn)

# --- SCHEDULER ---
scheduler = BackgroundScheduler()
scheduler.start()
# --- MODELS ---
class Dossier(db.Model):
    __tablename__ = "dossier"
    id = db.Column(db.Integer, primary_key=True)
    client = db.Column(db.String(255))
    status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
# --- ROUTES ---
@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200

@app.get("/dossiers")
def get_dossiers():
    dossiers = Dossier.query.all()
    result = [{"id": d.id, "client": d.client, "status": d.status} for d in dossiers]
    return jsonify(result)

@app.post("/dossiers")
def create_dossier():
    data = request.get_json(force=True, silent=True) or {}
    d = Dossier(client=data.get("client"), status=data.get("status", "nouveau"))
    db.session.add(d)
    db.session.commit()
    return jsonify({"id": d.id}), 201

@app.post("/enqueue/pdf")
def enqueue_pdf():
    data = request.get_json(force=True, silent=True) or {}
    job = queue.enqueue(generate_pdf, data.get("dossier_id"))
    return jsonify({"job_id": job.id}), 200

@app.post("/enqueue/ocr")
def enqueue_ocr():
    data = request.get_json(force=True, silent=True) or {}
    job = queue.enqueue(ocr_process, data.get("file_path"))
    return jsonify({"job_id": job.id}), 200

@app.post("/send_email")
def api_send_email():
    data = request.get_json(force=True, silent=True) or {}
    send_email(data.get("to"), data.get("subject"), data.get("body"))
    return jsonify({"status": "sent"}), 200
if __name__ == "__main__":
    app.run()
from flask import redirect

@app.route("/")
def root_redirect():
    return redirect("/kanban", code=302)

# ===== RQ enqueue & status (ajout) =====
import os
from flask import request, jsonify
from redis import Redis
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError
from app.tasks import generate_pdf

_redis = Redis(host=os.getenv("REDIS_HOST", "redis"),
               port=int(os.getenv("REDIS_PORT", 6379)))
_queue = Queue(connection=_redis)

IDEMPOTENCY_TTL = int(os.getenv("IDEMPOTENCY_TTL", "600"))  # 10 min

@app.route("/jobs/test", methods=["POST"])
def jobs_test():
    """Déclenche un job de démo."""
    n = int(request.args.get("n", 1))
    key = request.headers.get("Idempotency-Key")
    if key:
        existing = _redis.get(f"idemp:{key}")
        if existing:
            job_id = existing.decode() if isinstance(existing, (bytes, bytearray)) else str(existing)
            return jsonify({"status": "queued", "job_id": job_id}), 202

    job = _queue.enqueue(generate_pdf, source="http", n=n, result_ttl=86400, failure_ttl=604800)
    if key:
        _redis.setex(f"idemp:{key}", IDEMPOTENCY_TTL, job.get_id())
    return jsonify({"status": "queued", "job_id": job.get_id()}), 202

@app.route("/jobs/<job_id>", methods=["GET"])
def jobs_status(job_id: str):
    """Retourne l'état + résultat d'un job RQ."""
    try:
        job = Job.fetch(job_id, connection=_redis)
    except NoSuchJobError:
        return jsonify({"error": "job_not_found", "job_id": job_id}), 404

    return jsonify({
        "job_id": job.get_id(),
        "status": job.get_status(),   # queued | started | finished | failed | deferred
        "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
        "ended_at": job.ended_at.isoformat() if job.ended_at else None,
        "result": job.result,
        "exc_info": job.exc_info,
    })
# ===== fin ajout =====

# ===== download du résultat d'un job =====
import os
from flask import send_file, jsonify
from werkzeug.utils import safe_join

_TASKS_DIR = os.getenv("TASKS_OUTPUT_DIR", "/app/tmp/tasks")

@app.route("/jobs/<job_id>/download", methods=["GET"])
def jobs_download(job_id: str):
    try:
        job = Job.fetch(job_id, connection=_redis)
    except NoSuchJobError:
        return jsonify({"error": "job_not_found", "job_id": job_id}), 404

    res = job.result
    if not isinstance(res, dict) or "output" not in res:
        return jsonify({"error": "no_output_for_job", "job_id": job_id}), 409

    output_path = res["output"]
    # Normaliser et s'assurer que le fichier reste sous _TASKS_DIR
    try:
        rel = os.path.relpath(output_path, _TASKS_DIR)
    except ValueError:
        return jsonify({"error": "bad_output_path"}), 400
    if rel.startswith(".."):
        return jsonify({"error": "bad_output_path"}), 400

    full = safe_join(_TASKS_DIR, rel)
    if not full or not os.path.isfile(full):
        return jsonify({"error": "file_not_found", "path": rel}), 404

    return send_file(full, as_attachment=True,
                     download_name=os.path.basename(full),
                     mimetype="text/plain")
# ===== fin ajout =====

# --- garde d'accès pour /jobs/test via X-Job-Token ---
# Le token est lu dans l'env à l'initialisation du module
JOB_TOKEN = os.getenv("JOB_ENQUEUE_TOKEN")

@app.before_request
def _protect_jobs_test():
    # Protéger uniquement l'endpoint de démo
    if request.path == "/jobs/test" and request.method == "POST":
        if JOB_TOKEN and request.headers.get("X-Job-Token") != JOB_TOKEN:
            return jsonify({"error": "forbidden"}), 403


# --- Phase 2 placeholders ---
@app.route("/devis", methods=["GET","POST"])
def devis_endpoint():
    if request.method == "GET":
        return jsonify({"status": "ok", "devis": []})
    data = (request.get_json(silent=True) or {})
    return jsonify({"status": "accepted", "input": data}), 202

@app.route("/rdv", methods=["GET","POST"])
def rdv_endpoint():
    if request.method == "GET":
        return jsonify({"status": "ok", "rdv": []})
    data = (request.get_json(silent=True) or {})
    return jsonify({"status": "accepted", "input": data}), 202
