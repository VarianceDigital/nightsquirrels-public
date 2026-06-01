from flask import Blueprint, request, g, jsonify
from flask_login import login_required
from psycopg2.extras import RealDictCursor

from .db import get_db
from .pusher_client import get_pusher

bp = Blueprint('bl_pusher', __name__)


def _user_can_access_ticket(tkt_id: int, usr_id: int) -> bool:
    """Check if usr_id is the question owner or the assigned tutor."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT 1
          FROM nightsquirrel.tbl_t_ticket t
          JOIN nightsquirrel.tbl_q_question q ON q.qtn_id = t.qtn_id
         WHERE t.tkt_id = %s
           AND (q.usr_id = %s OR t.tutor_usr_id = %s)
    """, (tkt_id, usr_id, usr_id))
    return cur.fetchone() is not None


@bp.route('/pusher/auth', methods=('POST',))
@login_required
def pusher_auth():
    p = get_pusher()
    if not p:
        return jsonify(error="Real-time not configured"), 503

    channel_name = request.form.get('channel_name', '')
    socket_id = request.form.get('socket_id', '')

    if not channel_name or not socket_id:
        return jsonify(error="Missing channel_name or socket_id"), 400

    if not channel_name.startswith('private-ticket-'):
        return jsonify(error="Unknown channel"), 403

    try:
        tkt_id = int(channel_name.split('private-ticket-')[1])
    except (ValueError, IndexError):
        return jsonify(error="Invalid channel"), 403

    if not _user_can_access_ticket(tkt_id, g.user_id):
        return jsonify(error="Forbidden"), 403

    auth_response = p.authenticate(channel=channel_name, socket_id=socket_id)
    return jsonify(auth_response)
