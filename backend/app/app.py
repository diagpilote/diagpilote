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
API_KEY = os.getenv("API_KEY")

@app.before_request
def _protect_jobs_test():
    # Protéger uniquement l'endpoint de démo
    if request.path == "/jobs/test" and request.method == "POST":
        if JOB_TOKEN and request.headers.get("X-Job-Token") != JOB_TOKEN:
            return jsonify({"error": "forbidden"}), 403




@app.before_request
def _protect_api_key_endpoints():
    if (request.path.startswith("/devis") or request.path.startswith("/rdv")) and request.method in ("GET","POST","PUT","DELETE"):
        if API_KEY and request.headers.get("X-API-Key") != API_KEY:
            return jsonify({"error":"forbidden"}), 403

# --- Models Phase 2 ---

class DossiersRef(db.Model):
    __tablename__ = "dossiers"
    id = db.Column(db.Integer, primary_key=True)

class Devis(db.Model):
    __tablename__ = "devis"
    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(32), unique=True, nullable=False)
    client = db.Column(db.String(255), nullable=False)
    montant = db.Column(db.Numeric(10,2), nullable=False)
    devise = db.Column(db.String(8), nullable=False, default="EUR")
    status = db.Column(db.String(32), nullable=False, default="draft")
    dossier_id = db.Column(db.Integer, db.ForeignKey('dossiers.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "ref": self.ref,
            "client": self.client,
            "montant": float(self.montant) if self.montant is not None else None,
            "devise": self.devise,
            "status": self.status,
            "dossier_id": self.dossier_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Rdv(db.Model):
    __tablename__ = "rdv"
    id = db.Column(db.Integer, primary_key=True)
    dossier_id = db.Column(db.Integer, db.ForeignKey('dossiers.id'), nullable=True)
    date_start = db.Column(db.DateTime, nullable=False)
    date_end   = db.Column(db.DateTime, nullable=True)
    client_nom = db.Column(db.String(255), nullable=True)
    adresse    = db.Column(db.String(255), nullable=True)
    ville      = db.Column(db.String(120), nullable=True)
    lat        = db.Column(db.Float, nullable=True)
    lon        = db.Column(db.Float, nullable=True)
    technicien_id = db.Column(db.Integer, nullable=True)
    status     = db.Column(db.String(32), nullable=False, default="planned")
    notes      = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "dossier_id": self.dossier_id,
            "date_start": self.date_start.isoformat() if self.date_start else None,
            "date_end": self.date_end.isoformat() if self.date_end else None,
            "client_nom": self.client_nom,
            "adresse": self.adresse,
            "ville": self.ville,
            "lat": float(self.lat) if self.lat is not None else None,
            "lon": float(self.lon) if self.lon is not None else None,
            "technicien_id": self.technicien_id,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

# --- Phase 2 placeholders ---
@app.route("/devis", methods=["GET","POST"])
def devis_endpoint():
    if request.method == "GET":
        q = (request.args.get("q") or "").strip()
        status = request.args.get("status")
        try:
            limit = min(max(int(request.args.get("limit", 50)), 1), 200)
        except Exception:
            limit = 50
        try:
            offset = max(int(request.args.get("offset", 0)), 0)
        except Exception:
            offset = 0
        query = Devis.query
        if status:
            query = query.filter(Devis.status == status)
        if q:
            like = f"%{q}%"
            query = query.filter(db.or_(Devis.client.ilike(like), Devis.ref.ilike(like)))
        items = [d.to_dict() for d in query.order_by(Devis.created_at.desc()).offset(offset).limit(limit).all()]
        return jsonify({"status":"ok","devis": items, "limit": limit, "offset": offset, "count": len(items)})

    data = (request.get_json(silent=True) or {})

    # validation légère
    allowed = {"PLANIFIE","A_PLANIFIER","TERMINE","CANCELED","planned","done","pending"}
    if "status" in data and data["status"] is not None and data["status"] not in allowed:
        return jsonify({"error":"validation","details":"status invalide"}), 400

    # longueurs raisonnables
    for key in ("client_nom","adresse","ville","notes"):
        if key in data and data[key] is not None and len(str(data[key])) > 255:
            return jsonify({"error":"validation","details":f"{key} trop long"}), 400

    # lat/lon
    for key in ("lat","lon"):
        if key in data and data[key] is not None:
            try:
                v = float(data[key])
            except Exception:
                return jsonify({"error":"validation","details":f"{key} invalide"}), 400
            if key == "lat" and not (-90 <= v <= 90):
                return jsonify({"error":"validation","details":"lat hors plage"}), 400
            if key == "lon" and not (-180 <= v <= 180):
                return jsonify({"error":"validation","details":"lon hors plage"}), 400

    client = (data.get("client") or "").strip()
    montant = data.get("montant")
    devise  = (data.get("devise") or "EUR")[:8]
    dossier_id = data.get("dossier_id")
    if not client or montant is None:
        return jsonify({"error":"validation","details":"client and montant required"}), 400
    import time, secrets
    ref = f"DV-{int(time.time())}-{secrets.token_hex(3).upper()}"
    obj = Devis(ref=ref, client=client, montant=montant, devise=devise, dossier_id=dossier_id, status="draft")
    db.session.add(obj); db.session.commit()
    return jsonify({"status":"created","devis": obj.to_dict()}), 201



@app.route("/rdv", methods=["GET","POST"])
def rdv_endpoint():
    if request.method == "GET":
        # -- filtres, pagination, tri --
        from sqlalchemy import or_

        def _parse_iso(ts):
            if not ts:
                return None
            import datetime
            try:
                return datetime.datetime.fromisoformat(str(ts).replace("Z","+00:00")).replace(tzinfo=None)
            except Exception:
                return None

        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "").strip()
        date_from = _parse_iso(request.args.get("date_from"))
        date_to   = _parse_iso(request.args.get("date_to"))
        try:
            limit = int(request.args.get("limit", 50))
            offset = int(request.args.get("offset", 0))
        except Exception:
            return jsonify({"error":"validation","details":"limit/offset invalides"}), 400
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        query = Rdv.query
        if status:
            query = query.filter(Rdv.status == status)

        if q:
            like = f"%{q}%"
            query = query.filter(or_(Rdv.client_nom.ilike(like),
                                     Rdv.adresse.ilike(like),
                                     Rdv.ville.ilike(like)))
        if date_from:
            query = query.filter(Rdv.date_start >= date_from)
        if date_to:
            query = query.filter(Rdv.date_start <= date_to)

        sort = (request.args.get("sort") or "date_start").lower()
        order = (request.args.get("order") or "desc").lower()
        colmap = {"date_start": Rdv.date_start, "created_at": Rdv.created_at}
        col = colmap.get(sort, Rdv.date_start)
        order_expr = col.desc() if order == "desc" else col.asc()
        q2 = query.order_by(order_expr, Rdv.created_at.desc())
        items = [r.to_dict() for r in q2.offset(offset).limit(limit).all()]
        return jsonify({"status":"ok","rdv": items, "limit": limit, "offset": offset, "count": len(items)})

    # -- POST: créer un RDV --
    data = (request.get_json(silent=True) or {})

    def _parse_iso(ts):
        if not ts: return None
        import datetime
        try:
            return datetime.datetime.fromisoformat(str(ts).replace("Z","+00:00")).replace(tzinfo=None)
        except Exception:
            return None

    date_start = _parse_iso(data.get("date") or data.get("date_start"))
    date_end   = _parse_iso(data.get("date_end"))

    obj = Rdv(
        client_nom = (data.get("client_nom") or "").strip() or None,
        adresse    = (data.get("adresse") or "").strip() or None,
        ville      = (data.get("ville") or "").strip() or None,
        status     = (data.get("status") or "planned"),
        date_start = date_start,
        date_end   = date_end,
        technicien_id = (int(data["technicien_id"]) if data.get("technicien_id") is not None else None),
        dossier_id    = (int(data["dossier_id"]) if data.get("dossier_id") is not None else None),
        lat = (float(data["lat"]) if data.get("lat") is not None else None),
        lon = (float(data["lon"]) if data.get("lon") is not None else None),
    )
    db.session.add(obj); db.session.commit()
    return jsonify({"status":"created","rdv": obj.to_dict()}), 201
@app.get("/devis/<int:devis_id>")
def devis_get_one(devis_id):
    obj = Devis.query.get(devis_id)
    if not obj:
        return jsonify({"error":"not_found"}), 404
    return jsonify({"status":"ok","devis": obj.to_dict()})

@app.get("/rdv/<int:rdv_id>")
def rdv_get_one(rdv_id):
    obj = Rdv.query.get(rdv_id)
    if not obj:
        return jsonify({"error":"not_found"}), 404
    return jsonify({"status":"ok","rdv": obj.to_dict()})
@app.put("/devis/<int:devis_id>")
def devis_update(devis_id):
    obj = Devis.query.get(devis_id)
    if not obj:
        return jsonify({"error":"not_found"}), 404
    data = (request.get_json(silent=True) or {})
    # champs étendus
    if "client" in data and data["client"] is not None:
        obj.client = str(data["client"]).strip()
    if "devise" in data and data["devise"] is not None:
        obj.devise = str(data["devise"])[:8]
    if "montant" in data and data["montant"] is not None:
        try:
            obj.montant = float(data["montant"])
        except Exception:
            return jsonify({"error":"validation","details":"montant invalide"}), 400
    if "dossier_id" in data:
        try:
            obj.dossier_id = int(data["dossier_id"]) if data["dossier_id"] is not None else None
        except Exception:
            return jsonify({"error":"validation","details":"dossier_id invalide"}), 400
    if "status" in data and data["status"] is not None:
        obj.status = data["status"]
    db.session.commit()
    return jsonify({"status":"ok","devis": obj.to_dict()})


@app.put("/rdv/<int:rdv_id>")
def rdv_update(rdv_id):
    obj = Rdv.query.get(rdv_id)
    if not obj:
        return jsonify({"error":"not_found"}), 404
    data = (request.get_json(silent=True) or {})

    # validation légère (spécifique RDV)
    allowed = {"PLANIFIE","A_PLANIFIER","TERMINE","CANCELED","planned","done","pending"}
    if "status" in data and data["status"] is not None and data["status"] not in allowed:
        return jsonify({"error":"validation","details":"status invalide"}), 400

    # longueurs raisonnables
    for key in ("client_nom","adresse","ville","notes"):
        if key in data and data[key] is not None and len(str(data[key])) > 255:
            return jsonify({"error":"validation","details":f"{key} trop long"}), 400

    # lat/lon bornés
    for key in ("lat","lon"):
        if key in data and data[key] is not None:
            try:
                v = float(data[key])
            except Exception:
                return jsonify({"error":"validation","details":f"{key} invalide"}), 400
            if key == "lat" and not (-90 <= v <= 90):
                return jsonify({"error":"validation","details":"lat hors plage"}), 400
            if key == "lon" and not (-180 <= v <= 180):
                return jsonify({"error":"validation","details":"lon hors plage"}), 400

    # textes simples
    for key in ("client_nom","adresse","ville","notes","status"):
        if key in data and data[key] is not None:
            setattr(obj, key, str(data[key]))

    # date (champ unique "date" -> date_start)
    def _parse_iso(ts):
        if not ts: return None
        try:
            return datetime.datetime.fromisoformat(str(ts).replace("Z","+00:00")).replace(tzinfo=None)
        except Exception:
            return None
    if "date" in data:
        v = _parse_iso(data["date"])
        if v: obj.date_start = v
    # dates explicites
    if "date_start" in data:
        v = _parse_iso(data["date_start"])
        if v: obj.date_start = v
    if "date_end" in data:
        v = _parse_iso(data["date_end"])
        if v: obj.date_end = v

    # entiers
    for key in ("technicien_id","dossier_id"):
        if key in data:
            setattr(obj, key, int(data[key]) if data[key] is not None else None)

    # flottants
    for key in ("lat","lon"):
        if key in data:
            setattr(obj, key, float(data[key]) if data[key] is not None else None)

    db.session.commit()
    return jsonify({"status":"ok","rdv": obj.to_dict()})


@app.delete("/devis/<int:devis_id>")
def devis_delete(devis_id):
    obj = Devis.query.get(devis_id)
    if not obj:
        return jsonify({"error":"not_found"}), 404
    db.session.delete(obj)
    db.session.commit()
    return '', 204


@app.delete("/rdv/<int:rdv_id>")
def rdv_delete(rdv_id):
    obj = Rdv.query.get(rdv_id)
    if not obj:
        return jsonify({"error":"not_found"}), 404
    db.session.delete(obj)
    db.session.commit()
    return '', 204
