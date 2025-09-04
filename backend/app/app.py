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
