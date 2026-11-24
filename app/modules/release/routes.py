from flask import Blueprint, jsonify
from app.modules.archive.routes import store

bp = Blueprint('release', __name__)


@bp.get('/api/release/<run>')
def orders(run):
    store().get(run)
    return jsonify(run=run, rows=store().handovers(run))


@bp.post('/api/release/<run>/recall')
def recall(run):
    store().get(run)
    recalled = store().recall(run)
    return jsonify(run=run, recalled=recalled, rows=store().handovers(run))
