# nightsquirrel/db_ticket.py
from psycopg2.extras import RealDictCursor
from .db import get_db
from .states import *
from typing import Optional
import json


# ---------- AI analysis ----------

def db_save_ai_analysis(tkt_id: int, analysis_json: dict) -> bool:
    """Store the AI analysis result on the ticket."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket
               SET tkt_ai_analysis = %s::jsonb
             WHERE tkt_id = %s
        """, (json.dumps(analysis_json), tkt_id))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


def db_set_needs_clarification(tkt_id: int, student_hint: Optional[str]) -> bool:
    """Set ticket to TKT_NEEDS_CLARIFICATION, store the hint, and clear any existing quote."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket
               SET tkt_state = %s,
                   tkt_ai_hint = %s,
                   tkt_quote_points = NULL,
                   tkt_quote_version = NULL,
                   tkt_quote_note = NULL,
                   tkt_quote_payload = NULL,
                   tkt_quote_signature = NULL,
                   tkt_quote_input = NULL,
                   tkt_quoted_at = NULL,
                   tkt_selected_option_id = NULL,
                   tkt_selected_quote_cents = NULL
             WHERE tkt_id = %s
               AND tkt_state IN (%s, %s, %s, %s, %s)
        """, (TKT_NEEDS_CLARIFICATION, student_hint, tkt_id,
              TKT_NEW, TKT_NEEDS_CLARIFICATION, TKT_QUOTED, TKT_NEEDS_REVIEW, TKT_REJECTED))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


# ---------- ticket queries ----------

def db_get_student_info_for_ticket(tkt_id: int):
    """Fetch the question owner's email, name, question title, and quote info."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT u.usr_email, u.usr_name, q.qtn_title, q.qtn_id,
               t.tkt_id, t.tkt_selected_quote_cents, t.tkt_currency
          FROM nightsquirrel.tbl_t_ticket t
          JOIN nightsquirrel.tbl_q_question q ON q.qtn_id = t.qtn_id
          JOIN nightsquirrel.tbl_u_user u ON u.usr_id = q.usr_id
         WHERE t.tkt_id = %s
    """, (tkt_id,))
    return cur.fetchone()


def db_get_tutor_info_for_ticket(tkt_id: int):
    """Fetch the assigned tutor's email, name, and question info."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT u.usr_email, u.usr_name, q.qtn_title, q.qtn_id,
               t.tkt_id, t.tkt_selected_quote_cents, t.tkt_currency
          FROM nightsquirrel.tbl_t_ticket t
          JOIN nightsquirrel.tbl_q_question q ON q.qtn_id = t.qtn_id
          JOIN nightsquirrel.tbl_u_user u ON u.usr_id = t.tutor_usr_id
         WHERE t.tkt_id = %s
    """, (tkt_id,))
    return cur.fetchone()


def db_get_ticket_with_question_for_tutor(tkt_id: int):
    """Full ticket + question + answer data with Quill content (tutor view)."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
          t.tkt_id, t.qtn_id, t.tkt_state, t.tutor_usr_id, t.ans_id,
          t.tkt_selected_quote_cents, t.tkt_currency, t.tkt_due_at,

          q.qtn_title, q.qtn_notes, q.qtn_state,

          cq.ctx_id AS q_ctx_id,
          cq.ctx_delta::text AS q_ctx_delta_text,
          cq.ctx_plaintext AS q_ctx_plaintext,
          cq.ctx_createdwhen AS q_ctx_createdwhen,
          cq.ctx_modifiedwhen AS q_ctx_modifiedwhen,

          a.ans_id AS a_ans_id,
          a.ans_state AS a_ans_state,
          a.ctx_id AS a_ctx_id,
          ac.ctx_delta::text AS a_ctx_delta_text,
          ac.ctx_plaintext AS a_ctx_plaintext,
          a.ans_created_at AS a_ans_created_at,
          a.ans_updated_at AS a_ans_updated_at

        FROM nightsquirrel.tbl_t_ticket t
        JOIN nightsquirrel.tbl_q_question q ON q.qtn_id = t.qtn_id
        JOIN nightsquirrel.tbl_q_complextext cq ON cq.ctx_id = q.ctx_id

        LEFT JOIN nightsquirrel.tbl_q_answer a ON a.ans_id = t.ans_id
        LEFT JOIN nightsquirrel.tbl_q_complextext ac ON ac.ctx_id = a.ctx_id

        WHERE t.tkt_id = %s
    """, (tkt_id,))
    return cur.fetchone()


def db_list_open_tickets():
    """Tickets not yet claimed by a tutor (TKT_ACCEPTED, unassigned)."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
            t.tkt_id, t.qtn_id, t.tkt_state, t.tkt_selected_quote_cents, t.tkt_currency, t.tkt_due_at,
            t.tutor_usr_id,
            q.qtn_title, q.qtn_created_at,
            u.usr_email
        FROM nightsquirrel.tbl_t_ticket t
        JOIN nightsquirrel.tbl_q_question q ON q.qtn_id = t.qtn_id
        JOIN nightsquirrel.tbl_u_user u ON u.usr_id = q.usr_id
        WHERE (t.tutor_usr_id IS NULL)
          AND (t.tkt_state = %s)
        ORDER BY q.qtn_created_at DESC
    """, (TKT_ACCEPTED,))
    return cur.fetchall()


def db_list_my_tickets(tutor_usr_id: int):
    """Tickets assigned to a specific tutor."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
            t.tkt_id, t.qtn_id, t.tkt_state, t.tkt_selected_quote_cents, t.tkt_currency, t.tkt_due_at,
            t.tutor_usr_id,
            q.qtn_title, q.qtn_created_at,
            u.usr_email
        FROM nightsquirrel.tbl_t_ticket t
        JOIN nightsquirrel.tbl_q_question q ON q.qtn_id = t.qtn_id
        JOIN nightsquirrel.tbl_u_user u ON u.usr_id = q.usr_id
        WHERE t.tutor_usr_id = %s
        ORDER BY t.tkt_state ASC, q.qtn_created_at DESC
    """, (tutor_usr_id,))
    return cur.fetchall()


# ---------- ticket state transitions ----------

def db_claim_ticket(tkt_id: int, tutor_usr_id: int) -> bool:
    """Claim a ticket only if it's unassigned.
    Uses an atomic UPDATE with a WHERE tutor_usr_id IS NULL to avoid races.
    """
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket
            SET tutor_usr_id = %s,
                tkt_state = %s
            WHERE tkt_id = %s
              AND tutor_usr_id IS NULL
              AND tkt_state = %s
        """, (tutor_usr_id, TKT_ASSIGNED, tkt_id, TKT_ACCEPTED))
        ok = (cur.rowcount == 1)
        if ok:
            db.commit()
        else:
            db.rollback()
        return ok
    except Exception:
        db.rollback()
        raise


def db_unclaim_ticket(tkt_id: int, tutor_usr_id: int) -> bool:
    """Allow tutor to release a ticket from ASSIGNED or IN_PROGRESS state."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket
            SET tutor_usr_id = NULL,
                tkt_state = %s
            WHERE tkt_id = %s
              AND tutor_usr_id = %s
              AND tkt_state IN (%s, %s)
        """, (TKT_ACCEPTED, tkt_id, tutor_usr_id, TKT_ASSIGNED, TKT_IN_PROGRESS))
        ok = (cur.rowcount == 1)
        if ok:
            db.commit()
        else:
            db.rollback()
        return ok
    except Exception:
        db.rollback()
        raise


def db_set_ticket_state(tkt_id: int, tutor_usr_id: int, new_state: int) -> bool:
    """Tutor can move their own ticket through allowed transitions.
    V1: allow any forward move from assigned/in_progress to delivered.
    """
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket
            SET tkt_state = %s
            WHERE tkt_id = %s
              AND tutor_usr_id = %s
              AND tkt_state IN (%s, %s)
        """, (new_state, tkt_id, tutor_usr_id, TKT_ASSIGNED, TKT_IN_PROGRESS))
        ok = (cur.rowcount == 1)
        if ok:
            db.commit()
        else:
            db.rollback()
        return ok
    except Exception:
        db.rollback()
        raise


def db_mark_ticket_and_answer_delivered(tkt_id: int, tutor_usr_id: int) -> bool:
    """Marks ticket as DELIVERED_PENDING_PAYMENT.
    Tutor must own the ticket and it must be in a workable state.
    One transaction, consistent state.
    """
    db = get_db()
    try:
        cur = db.cursor()

        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket
            SET tkt_state = %s
            WHERE tkt_id = %s AND tutor_usr_id = %s
              AND tkt_state IN (%s, %s)
        """, (TKT_DELIVERED_PENDING_PAYMENT, tkt_id, tutor_usr_id,
              TKT_ASSIGNED, TKT_IN_PROGRESS))

        ok = (cur.rowcount == 1)
        if ok:
            db.commit()
        else:
            db.rollback()
        return ok
    except Exception:
        db.rollback()
        raise


def db_set_ticket_delivered(tkt_id: int) -> bool:
    """Move ticket from DELIVERED_PENDING_PAYMENT to DELIVERED (after payment success)."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket
            SET tkt_state = %s
            WHERE tkt_id = %s
              AND tkt_state = %s
        """, (TKT_DELIVERED, tkt_id, TKT_DELIVERED_PENDING_PAYMENT))
        ok = (cur.rowcount == 1)
        if ok:
            db.commit()
        else:
            db.rollback()
        return ok
    except Exception:
        db.rollback()
        raise


# ---------- quoting ----------

def db_apply_quote_to_ticket(
    tkt_id: int,
    quote_points: Optional[int],
    quote_version: str,
    quote_note: Optional[str],
    new_state: int,
    quote_payload: Optional[dict] = None,
    quote_signature: Optional[str] = None,
    quote_input: Optional[dict] = None,
) -> bool:
    """Persist a computed quote on the ticket and advance its state.

    new_state is typically TKT_QUOTED or TKT_NEEDS_REVIEW.
    Only allowed when ticket is in an editable/quotable state.
    Returns True if the update touched exactly one row.
    """
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket
               SET tkt_quote_points    = %s,
                   tkt_quote_version   = %s,
                   tkt_quote_note      = %s,
                   tkt_quote_payload   = %s,
                   tkt_quote_signature = %s,
                   tkt_quote_input     = %s,
                   tkt_quoted_at       = now(),
                   tkt_state           = %s
             WHERE tkt_id = %s
               AND tkt_state IN (%s, %s, %s, %s, %s)
        """, (quote_points, quote_version, quote_note,
              json.dumps(quote_payload) if quote_payload else None,
              quote_signature,
              json.dumps(quote_input) if quote_input else None,
              new_state, tkt_id, TKT_NEW, TKT_NEEDS_CLARIFICATION, TKT_QUOTED, TKT_NEEDS_REVIEW, TKT_REJECTED))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


def db_accept_quote(tkt_id: int, usr_id: int,
                    option_id: str = None, selected_cents: int = None,
                    delivery_hours: int = None) -> bool:
    """Student accepts the quoted price. TKT_QUOTED -> TKT_ACCEPTED.

    Ownership is verified by joining through the question.
    Sets tkt_accepted_at and clears tkt_rejected_at.
    Stores the selected option and its price.
    If delivery_hours is provided, sets tkt_due_at = now() + interval.
    """
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket t
               SET tkt_state                = %s,
                   tkt_accepted_at          = now(),
                   tkt_rejected_at          = NULL,
                   tkt_selected_option_id   = %s,
                   tkt_selected_quote_cents = %s,
                   tkt_due_at = CASE WHEN %s IS NOT NULL
                       THEN now() + make_interval(hours => %s)
                       ELSE tkt_due_at END
             WHERE t.tkt_id = %s
               AND t.tkt_state = %s
               AND EXISTS (
                   SELECT 1 FROM nightsquirrel.tbl_q_question q
                    WHERE q.qtn_id = t.qtn_id AND q.usr_id = %s
               )
        """, (TKT_ACCEPTED, option_id, selected_cents,
              delivery_hours, delivery_hours,
              tkt_id, TKT_QUOTED, usr_id))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


def db_reject_quote(tkt_id: int, usr_id: int) -> bool:
    """Student rejects the quoted price. TKT_QUOTED -> TKT_REJECTED.

    Ownership is verified by joining through the question.
    Sets tkt_rejected_at and clears tkt_accepted_at.
    """
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket t
               SET tkt_state       = %s,
                   tkt_rejected_at = now(),
                   tkt_accepted_at = NULL
             WHERE t.tkt_id = %s
               AND t.tkt_state = %s
               AND EXISTS (
                   SELECT 1 FROM nightsquirrel.tbl_q_question q
                    WHERE q.qtn_id = t.qtn_id AND q.usr_id = %s
               )
        """, (TKT_REJECTED, tkt_id, TKT_QUOTED, usr_id))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


def db_close_ticket(tkt_id: int, usr_id: int) -> bool:
    """Student accepts delivery and closes ticket. TKT_DELIVERED -> TKT_CLOSED.

    Ownership is verified by joining through the question.
    """
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket t
               SET tkt_state     = %s,
                   tkt_closed_at = now()
             WHERE t.tkt_id = %s
               AND t.tkt_state = %s
               AND EXISTS (
                   SELECT 1 FROM nightsquirrel.tbl_q_question q
                    WHERE q.qtn_id = t.qtn_id AND q.usr_id = %s
               )
        """, (TKT_CLOSED, tkt_id, TKT_DELIVERED, usr_id))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


# ---------- admin ticket operations ----------

def db_admin_set_manual_quote(tkt_id: int, quote_cents: int, quote_note: str) -> bool:
    """Admin manually sets a price on a TKT_NEEDS_REVIEW ticket -> TKT_QUOTED."""
    manual_payload = json.dumps({
        "quote_version": "manual",
        "currency": "EUR",
        "base_price_cents": None,
        "overflow": False,
        "axes": [],
        "pricing": None,
        "options": [{
            "id": "manual",
            "label": "Custom",
            "price_cents": quote_cents,
            "currency": "EUR",
        }],
        "ui": {"layout": "single_card"},
    })
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket
               SET tkt_quote_version   = 'manual',
                   tkt_quote_note      = %s,
                   tkt_quote_payload   = %s::jsonb,
                   tkt_quote_signature = NULL,
                   tkt_quote_input     = NULL,
                   tkt_quoted_at       = now(),
                   tkt_state           = %s
             WHERE tkt_id = %s
               AND tkt_state = %s
        """, (quote_note or None, manual_payload, TKT_QUOTED, tkt_id, TKT_NEEDS_REVIEW))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


def db_admin_assign_tutor_to_ticket(tkt_id: int, tutor_usr_id):
    """Assign or unassign a tutor. tutor_usr_id can be None to unassign."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_ticket
            SET tutor_usr_id = %s
            WHERE tkt_id = %s
        """, (tutor_usr_id, tkt_id))
        if cur.rowcount != 1:
            db.rollback()
            return False
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
