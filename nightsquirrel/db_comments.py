# nightsquirrel/db_comments.py
from psycopg2.extras import RealDictCursor
from .db import get_db


def db_create_comment(tkt_id: int, usr_id: int, ctx_delta_json: str, ctx_plaintext: str) -> dict:
    """Create complextext + comment row for a ticket.

    Returns a dict with: cmt_id, tkt_id, usr_id, cmt_created_at,
    cmt_ctx_delta_text, cmt_ctx_plaintext.
    """
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)

        # 1) create complextext
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_q_complextext (ctx_delta, ctx_plaintext)
            VALUES (%s::jsonb, %s)
            RETURNING ctx_id
        """, (ctx_delta_json, ctx_plaintext))
        ctx_id = cur.fetchone()["ctx_id"]

        # 2) create comment row
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_q_comment (tkt_id, usr_id, ctx_id)
            VALUES (%s, %s, %s)
            RETURNING cmt_id, cmt_created_at
        """, (tkt_id, usr_id, ctx_id))
        row = cur.fetchone()

        db.commit()
        return {
            "cmt_id": row["cmt_id"],
            "tkt_id": tkt_id,
            "usr_id": usr_id,
            "cmt_created_at": row["cmt_created_at"],
            "cmt_ctx_delta_text": ctx_delta_json,
            "cmt_ctx_plaintext": ctx_plaintext,
        }

    except Exception:
        db.rollback()
        raise


def db_list_comments_for_ticket(tkt_id: int) -> list:
    """Fetch all comments for a ticket, ordered chronologically."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
            c.cmt_id, c.tkt_id, c.usr_id, c.cmt_created_at,
            u.usr_name, u.usr_email,
            cx.ctx_id, cx.ctx_delta::text AS cmt_ctx_delta_text,
            cx.ctx_plaintext AS cmt_ctx_plaintext
        FROM nightsquirrel.tbl_q_comment c
        JOIN nightsquirrel.tbl_q_complextext cx ON cx.ctx_id = c.ctx_id
        JOIN nightsquirrel.tbl_u_user u ON u.usr_id = c.usr_id
        WHERE c.tkt_id = %s
        ORDER BY c.cmt_created_at ASC
    """, (tkt_id,))
    return cur.fetchall()
