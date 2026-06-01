from psycopg2.extras import RealDictCursor
from .db import get_db
from .states import *


def db_update_question_ai_predictions(qtn_id: int, sbj_id, sct_id, grade, difficulty) -> bool:
    """Overwrite question metadata with AI-predicted values."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_q_question
               SET sbj_id = %s,
                   sct_id = %s,
                   qtn_grade = %s,
                   qtn_difficulty = %s
             WHERE qtn_id = %s
        """, (sbj_id, sct_id, grade, difficulty, qtn_id))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


def db_create_question_with_ticket(
    usr_id: int,
    title: str,
    sbj_id,
    qtp_id,
    sct_id,
    difficulty,
    grade,
    notes,
    ctx_delta_json: str,
    ctx_plaintext: str
):
    """Creates complextext + question + ticket in one transaction.

    Returns dict with: ctx_id, qtn_id, tkt_id
    """

    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)

        # 1) ComplexText
        cur.execute(
            """INSERT INTO nightsquirrel.tbl_q_complextext
                (ctx_delta, ctx_plaintext)
                VALUES (%s::jsonb, %s)
                RETURNING ctx_id
            """,
            (ctx_delta_json, ctx_plaintext,)
        )
        ctx_id = cur.fetchone()['ctx_id']

        # 2) Question
        cur.execute(
            """INSERT INTO nightsquirrel.tbl_q_question
                (usr_id, qtn_title, sbj_id, qtp_id, sct_id, ctx_id,
                 qtn_notes, qtn_difficulty, qtn_grade,
                 qtn_is_valid, qtn_state)
                VALUES (%s, %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        true, 0)
                RETURNING qtn_id
            """,
            (usr_id, title, sbj_id, qtp_id, sct_id, ctx_id,
             notes, difficulty, grade)
        )
        qtn_id = cur.fetchone()['qtn_id']

        # 3) Ticket (quote/due are placeholders for now)
        cur.execute(
            """INSERT INTO nightsquirrel.tbl_t_ticket (qtn_id, tkt_state)
                VALUES (%s, %s)
                RETURNING tkt_id
            """,
            (qtn_id, TKT_NEW)
        )
        tkt_id = cur.fetchone()['tkt_id']

        db.commit()
        return {'ctx_id': ctx_id, 'qtn_id': qtn_id, 'tkt_id': tkt_id}

    except Exception:
        db.rollback()
        raise


def db_list_questions_for_user(usr_id: int):
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
            q.qtn_id,
            q.qtn_title,
            q.qtn_state,
            q.sbj_id,
            q.qtp_id,
            q.sct_id,
            t.tkt_id,
            t.tkt_state,
            t.tkt_selected_quote_cents,
            t.tkt_currency,
            t.tkt_due_at,
            t.tutor_usr_id,
            t.ans_id
        FROM nightsquirrel.tbl_q_question q
        LEFT JOIN nightsquirrel.tbl_t_ticket t
          ON t.qtn_id = q.qtn_id
        WHERE q.usr_id = %s
          AND q.qtn_is_valid = true
        ORDER BY q.qtn_created_at DESC
    """, (usr_id,))
    return cur.fetchall()


def db_get_question_detail(qtn_id: int, usr_id: int):
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
            q.qtn_id,
            q.qtn_title,
            q.qtn_state,
            q.qtn_notes,
            q.qtn_difficulty,
            q.qtn_grade,
            q.sbj_id,
            q.qtp_id,
            q.sct_id,
            q.qtn_is_valid,

            t.tkt_id,
            t.tkt_state,
            t.tkt_selected_quote_cents,
            t.tkt_quote_points,
            t.tkt_quote_version,
            t.tkt_quote_note,
            t.tkt_quoted_at,
            t.tkt_currency,
            t.tkt_quote_signature,
            t.tkt_quote_payload,
            t.tkt_due_at,
            t.tutor_usr_id,
            t.tkt_ai_analysis,
            t.tkt_ai_hint,

            c.ctx_id,
            c.ctx_delta::text AS ctx_delta_text,
            c.ctx_plaintext,
            c.ctx_createdwhen,
            c.ctx_modifiedwhen,
            a.ans_id,
            a.ans_state,
            ca.ctx_delta::text AS ans_ctx_delta_text,
            ca.ctx_createdwhen AS ans_ctx_createdwhen,
            ca.ctx_modifiedwhen AS ans_ctx_modifiedwhen

        FROM nightsquirrel.tbl_q_question q
        LEFT JOIN nightsquirrel.tbl_t_ticket t
            ON t.qtn_id = q.qtn_id
        LEFT JOIN nightsquirrel.tbl_q_complextext c
            ON c.ctx_id = q.ctx_id
        LEFT JOIN nightsquirrel.tbl_q_answer a
            ON a.tkt_id = t.tkt_id
        LEFT JOIN nightsquirrel.tbl_q_complextext ca
            ON ca.ctx_id = a.ctx_id
        WHERE q.qtn_id = %s
          AND q.usr_id = %s
    """, (qtn_id, usr_id))
    return cur.fetchone()

def db_delete_question(qtn_id: int, usr_id: int) -> bool:
    """
    Deletes a question owned by usr_id.
    Cascades will delete ticket/answer/comments (per FKs).
    Then we delete all orphaned complextext rows (question body, answer, comments).
    Returns True if something was deleted, else False.
    """
    db = get_db()
    try:
        cur = db.cursor()

        # 1) Ownership check + collect all related complextext IDs
        cur.execute("""
            SELECT q.ctx_id,
                   a.ctx_id,
                   array_agg(cmt.ctx_id) FILTER (WHERE cmt.ctx_id IS NOT NULL)
            FROM nightsquirrel.tbl_q_question q
            LEFT JOIN nightsquirrel.tbl_t_ticket t ON t.qtn_id = q.qtn_id
            LEFT JOIN nightsquirrel.tbl_q_answer a ON a.tkt_id = t.tkt_id
            LEFT JOIN nightsquirrel.tbl_q_comment cmt ON cmt.tkt_id = t.tkt_id
            WHERE q.qtn_id = %s AND q.usr_id = %s
            GROUP BY q.ctx_id, a.ctx_id
        """, (qtn_id, usr_id))
        row = cur.fetchone()
        if not row:
            db.rollback()
            return False

        ctx_ids = set()
        if row[0]: ctx_ids.add(row[0])       # question body
        if row[1]: ctx_ids.add(row[1])       # answer body
        if row[2]: ctx_ids.update(row[2])    # comment bodies

        # 2) Delete question (ticket/answer/comments cascade)
        cur.execute("""
            DELETE FROM nightsquirrel.tbl_q_question
            WHERE qtn_id = %s AND usr_id = %s
        """, (qtn_id, usr_id))

        if cur.rowcount != 1:
            db.rollback()
            return False

        # 3) Delete all orphaned complextext rows
        if ctx_ids:
            cur.execute("""
                DELETE FROM nightsquirrel.tbl_q_complextext
                WHERE ctx_id = ANY(%s)
            """, (list(ctx_ids),))

        db.commit()
        return True

    except Exception:
        db.rollback()
        raise

def db_update_question_with_complextext(
    qtn_id: int,
    usr_id: int,
    title: str,
    sbj_id,
    qtp_id,
    sct_id,
    difficulty,
    grade,
    notes,
    ctx_delta_json: str,
    ctx_plaintext: str
) -> bool:
    """
    Updates question metadata + its Quill complextext (same ctx_id).
    Returns True if updated, False if not found / not owned.
    """
    db = get_db()
    try:
        cur = db.cursor()

        # find ctx_id + ownership check
        cur.execute("""
            SELECT ctx_id
            FROM nightsquirrel.tbl_q_question
            WHERE qtn_id = %s AND usr_id = %s
        """, (qtn_id, usr_id))
        row = cur.fetchone()
        if not row or row[0] is None:
            db.rollback()
            return False

        ctx_id = row[0]

        # update complextext
        cur.execute("""
            UPDATE nightsquirrel.tbl_q_complextext
            SET ctx_delta = %s::jsonb,
                ctx_plaintext = %s
            WHERE ctx_id = %s
        """, (ctx_delta_json, ctx_plaintext, ctx_id))

        # update question
        cur.execute("""
            UPDATE nightsquirrel.tbl_q_question
            SET qtn_title = %s,
                sbj_id = %s,
                qtp_id = %s,
                sct_id = %s,
                qtn_notes = %s,
                qtn_difficulty = %s,
                qtn_grade = %s
            WHERE qtn_id = %s AND usr_id = %s
        """, (title, sbj_id, qtp_id, sct_id, notes, difficulty, grade, qtn_id, usr_id))

        if cur.rowcount != 1:
            db.rollback()
            return False

        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def db_soft_delete_question(qtn_id: int, usr_id: int) -> bool:
    """Soft-delete: set qtn_is_valid=false and tkt_state=TKT_CANCELLED.
    Used for delivered/paid questions where data must be preserved."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_q_question
            SET qtn_is_valid = false
            WHERE qtn_id = %s AND usr_id = %s AND qtn_is_valid = true
        """, (qtn_id, usr_id))
        if cur.rowcount != 1:
            db.rollback()
            return False
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket
            SET tkt_state = %s
            WHERE qtn_id = %s
        """, (TKT_CANCELLED, qtn_id))
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
