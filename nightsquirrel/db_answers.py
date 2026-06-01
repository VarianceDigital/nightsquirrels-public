# nightsquirrel/db_answers.py
from psycopg2.extras import RealDictCursor
from .db import get_db


def db_get_answer_for_ticket(tkt_id: int):
    """Fetch answer with complextext for editing."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT
          a.ans_id, a.tkt_id, a.qtn_id, a.ctx_id, a.ans_state,
          a.ans_created_at, a.ans_updated_at,
          ca.ctx_delta::text AS ans_ctx_delta_text,
          ca.ctx_plaintext AS ans_ctx_plaintext,
          ca.ctx_createdwhen AS ans_ctx_createdwhen,
          ca.ctx_modifiedwhen AS ans_ctx_modifiedwhen
        FROM nightsquirrel.tbl_q_answer a
        JOIN nightsquirrel.tbl_q_complextext ca ON ca.ctx_id = a.ctx_id
        WHERE a.tkt_id = %s
        """,
        (tkt_id,),
    )
    return cur.fetchone()


def db_create_answer_for_ticket(tkt_id: int, tutor_usr_id: int, ctx_delta_json: str, ctx_plaintext: str) -> int:
    """Create complextext + answer row, link ticket -> answer."""
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)

        # Must be assigned to this tutor AND no answer yet
        cur.execute("""
            SELECT t.qtn_id
            FROM nightsquirrel.tbl_t_ticket t
            WHERE t.tkt_id = %s
              AND t.tutor_usr_id = %s
              AND t.ans_id IS NULL
        """, (tkt_id, tutor_usr_id))
        r = cur.fetchone()
        if not r:
            db.rollback()
            raise PermissionError("Ticket not assigned to tutor or answer already exists")

        qtn_id = r["qtn_id"]

        # 1) create complextext for answer
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_q_complextext (ctx_delta, ctx_plaintext)
            VALUES (%s::jsonb, %s)
            RETURNING ctx_id
        """, (ctx_delta_json, ctx_plaintext))
        a_ctx_id = cur.fetchone()["ctx_id"]

        # 2) create answer row
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_q_answer (qtn_id, tkt_id, ctx_id, ans_state, ans_is_valid)
            VALUES (%s, %s, %s, 0, true)
            RETURNING ans_id
        """, (qtn_id, tkt_id, a_ctx_id))
        ans_id = cur.fetchone()["ans_id"]

        # 3) link ticket -> answer
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket
            SET ans_id = %s
            WHERE tkt_id = %s
        """, (ans_id, tkt_id))

        db.commit()
        return ans_id

    except Exception:
        db.rollback()
        raise

def db_update_answer_complextext(
    tkt_id: int,
    tutor_usr_id: int,
    ctx_delta_json: str,
    ctx_plaintext: str
) -> bool:
    """Update answer's Quill content. Ownership check (tutor must own ticket)."""
    db = get_db()
    try:
        cur = db.cursor()

        # Ensure tutor owns ticket AND answer exists
        cur.execute(
            """
            SELECT a.ans_id, a.ctx_id
            FROM nightsquirrel.tbl_t_ticket t
            JOIN nightsquirrel.tbl_q_answer a ON a.tkt_id = t.tkt_id
            WHERE t.tkt_id = %s AND t.tutor_usr_id = %s
            """,
            (tkt_id, tutor_usr_id),
        )
        row = cur.fetchone()
        if not row:
            db.rollback()
            return False

        ans_id, ctx_id = row[0], row[1]

        # Update complextext
        cur.execute(
            """
            UPDATE nightsquirrel.tbl_q_complextext
            SET ctx_delta = %s::jsonb,
                ctx_plaintext = %s
            WHERE ctx_id = %s
            """,
            (ctx_delta_json, ctx_plaintext, ctx_id),
        )

        db.commit()
        return True

    except Exception:
        db.rollback()
        raise
