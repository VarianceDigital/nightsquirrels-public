# nightsquirrel/db_payment.py
from psycopg2.extras import RealDictCursor
from .db import get_db
from typing import Optional


# ==================== PAYER LINK ====================

def db_get_active_payer_link(student_usr_id: int) -> Optional[dict]:
    """Return the active payer_link row for a student, joined with payer user info.
    Returns None if no active link exists.
    """
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT plk.plk_id, plk.student_usr_id, plk.payer_usr_id,
               plk.plk_relationship, plk.plk_is_active,
               plk.plk_created_at, plk.plk_updated_at,
               u.usr_email AS payer_email,
               u.usr_name  AS payer_name
          FROM nightsquirrel.tbl_p_payer_link plk
          JOIN nightsquirrel.tbl_u_user u ON u.usr_id = plk.payer_usr_id
         WHERE plk.student_usr_id = %s
           AND plk.plk_is_active = true
    """, (student_usr_id,))
    row = cur.fetchone()
    cur.close()
    return row


def db_student_has_active_payer(student_usr_id: int) -> bool:
    """Quick check: does this student have an active payer link?"""
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT 1
          FROM nightsquirrel.tbl_p_payer_link
         WHERE student_usr_id = %s AND plk_is_active = true
         LIMIT 1
    """, (student_usr_id,))
    result = cur.fetchone() is not None
    cur.close()
    return result


def db_create_payer_link(student_usr_id: int, payer_usr_id: int, relationship: str) -> int:
    """Create a new active payer link. Deactivates any prior active link first.
    Returns the new plk_id.
    """
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        # Deactivate any existing active link for this student
        cur.execute("""
            UPDATE nightsquirrel.tbl_p_payer_link
               SET plk_is_active = false
             WHERE student_usr_id = %s AND plk_is_active = true
        """, (student_usr_id,))
        # Insert new link
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_p_payer_link
                (student_usr_id, payer_usr_id, plk_relationship, plk_is_active)
            VALUES (%s, %s, %s, true)
            RETURNING plk_id
        """, (student_usr_id, payer_usr_id, relationship))
        plk_id = cur.fetchone()['plk_id']
        db.commit()
        return plk_id
    except Exception:
        db.rollback()
        raise


def db_deactivate_payer_link(student_usr_id: int) -> bool:
    """Deactivate the active payer link for a student.
    Returns True if a row was updated.
    """
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_p_payer_link
               SET plk_is_active = false
             WHERE student_usr_id = %s AND plk_is_active = true
        """, (student_usr_id,))
        ok = cur.rowcount >= 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


def db_deactivate_payment_methods(payer_usr_id: int) -> bool:
    """Deactivate all payment methods for a payer.
    Returns True if any rows were updated.
    """
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_p_payment_method
               SET pmt_is_active = false, pmt_is_default = false
             WHERE payer_usr_id = %s AND pmt_is_active = true
        """, (payer_usr_id,))
        ok = cur.rowcount >= 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


# ==================== PAYMENT METHOD ====================

def db_create_payment_method(payer_usr_id: int, paypal_email: str) -> int:
    """Create a PayPal payment method for a payer.
    Unsets any existing default first. Returns pmt_id.
    """
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        # Unset any existing default for this payer
        cur.execute("""
            UPDATE nightsquirrel.tbl_p_payment_method
               SET pmt_is_default = false
             WHERE payer_usr_id = %s AND pmt_is_default = true
        """, (payer_usr_id,))
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_p_payment_method
                (payer_usr_id, pmt_type, pmt_paypal_email, pmt_is_default, pmt_is_active)
            VALUES (%s, 'paypal', %s, true, true)
            RETURNING pmt_id
        """, (payer_usr_id, paypal_email))
        pmt_id = cur.fetchone()['pmt_id']
        db.commit()
        return pmt_id
    except Exception:
        db.rollback()
        raise


def db_get_default_payment_method(payer_usr_id: int) -> Optional[dict]:
    """Return the default active payment method for a payer, or None."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT *
          FROM nightsquirrel.tbl_p_payment_method
         WHERE payer_usr_id = %s
           AND pmt_is_default = true
           AND pmt_is_active = true
    """, (payer_usr_id,))
    row = cur.fetchone()
    cur.close()
    return row


# ==================== PAYMENT ====================

def db_create_payment_record(tkt_id: int, payer_usr_id: int,
                             amount_cents: int, currency: str = 'EUR') -> int:
    """Create an awaiting_charge payment record when a quote is accepted.
    The charge will be attempted later when the tutor delivers the answer.
    Returns pay_id.
    """
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_p_payment
                (tkt_id, payer_usr_id, pay_amount_cents, pay_currency, pay_status)
            VALUES (%s, %s, %s, %s, 'awaiting_charge')
            RETURNING pay_id
        """, (tkt_id, payer_usr_id, amount_cents, currency))
        pay_id = cur.fetchone()['pay_id']
        db.commit()
        return pay_id
    except Exception:
        db.rollback()
        raise


def db_get_payment_for_ticket(tkt_id: int) -> Optional[dict]:
    """Return the most recent payment record for a ticket, or None."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT *
          FROM nightsquirrel.tbl_p_payment
         WHERE tkt_id = %s
         ORDER BY pay_created_at DESC
         LIMIT 1
    """, (tkt_id,))
    row = cur.fetchone()
    cur.close()
    return row


def db_get_payer_info_for_ticket(tkt_id: int) -> Optional[dict]:
    """Fetch payer user data for a ticket (ticket -> question -> student -> payer_link -> payer).
    Used for notifications.
    """
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT u_payer.usr_id   AS payer_usr_id,
               u_payer.usr_email AS payer_email,
               u_payer.usr_name  AS payer_name,
               u_student.usr_name AS student_name,
               q.qtn_title,
               q.qtn_id,
               t.tkt_id,
               t.tkt_selected_quote_cents,
               t.tkt_currency
          FROM nightsquirrel.tbl_t_ticket t
          JOIN nightsquirrel.tbl_q_question q ON q.qtn_id = t.qtn_id
          JOIN nightsquirrel.tbl_p_payer_link plk
               ON plk.student_usr_id = q.usr_id AND plk.plk_is_active = true
          JOIN nightsquirrel.tbl_u_user u_payer   ON u_payer.usr_id = plk.payer_usr_id
          JOIN nightsquirrel.tbl_u_user u_student ON u_student.usr_id = q.usr_id
         WHERE t.tkt_id = %s
    """, (tkt_id,))
    row = cur.fetchone()
    cur.close()
    return row


# ==================== VAULT / CHARGE UPDATES ====================

def db_update_vault_status(pmt_id: int, vault_status: str):
    """Update the vault agreement lifecycle status on a payment method.

    Valid values: 'none', 'pending_approval', 'vaulted',
                  'suspended', 'cancelled', 'expired'.
    """
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_p_payment_method
               SET pmt_vault_status = %s
             WHERE pmt_id = %s
        """, (vault_status, pmt_id))
        db.commit()
    except Exception:
        db.rollback()
        raise


def db_clear_vault(pmt_id: int):
    """Disconnect the PayPal vault from a payment method.
    Clears the vault_id and resets status to 'none'.
    """
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_p_payment_method
               SET pmt_paypal_vault_id = NULL,
                   pmt_vault_status = 'none'
             WHERE pmt_id = %s
        """, (pmt_id,))
        db.commit()
    except Exception:
        db.rollback()
        raise


def db_update_payment_method_vault_id(pmt_id: int, vault_id: str):
    """Store the PayPal vault token and mark the method as 'vaulted'.

    Called after the payer approves the vault setup and we exchange
    the setup token for a permanent payment token.
    """
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_p_payment_method
               SET pmt_paypal_vault_id = %s,
                   pmt_vault_status = 'vaulted'
             WHERE pmt_id = %s
        """, (vault_id, pmt_id))
        db.commit()
    except Exception:
        db.rollback()
        raise


def db_update_payment_captured(pay_id: int, order_id: str, capture_id: str):
    """Mark a payment as captured after a successful PayPal charge."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_p_payment
               SET pay_status = 'captured',
                   pay_paypal_order_id = %s,
                   pay_paypal_capture_id = %s,
                   pay_charged_at = now()
             WHERE pay_id = %s
               AND pay_status = 'awaiting_charge'
        """, (order_id, capture_id, pay_id))
        db.commit()
    except Exception:
        db.rollback()
        raise


def db_update_payment_failed(pay_id: int, error_msg: str):
    """Mark a payment as failed and record the error message."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_p_payment
               SET pay_status = 'failed',
                   pay_error_msg = %s
             WHERE pay_id = %s
               AND pay_status = 'awaiting_charge'
        """, (error_msg, pay_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
