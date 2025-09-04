from flask import Blueprint, jsonify

agenda_bp = Blueprint('agenda', __name__)

@agenda_bp.route('/', strict_slashes=False)
def agenda_health():
    return jsonify({"status": "ok", "agenda": []})
