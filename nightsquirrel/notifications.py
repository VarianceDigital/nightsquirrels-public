# nightsquirrel/notifications.py
import os
import logging
import jwt
import requests
from .db_ticket import db_get_student_info_for_ticket
from .db_payment import db_get_payer_info_for_ticket

log = logging.getLogger(__name__)


def notify_answer_delivered(tkt_id: int):
    """Send a notification to the student that their answer has been delivered.

    Uses the external mailer service (same infrastructure as auth emails).
    Fails silently with a log warning so delivery is never blocked by email errors.
    """
    try:
        row = db_get_student_info_for_ticket(tkt_id)
        if not row:
            log.warning("notify_answer_delivered: ticket %s not found", tkt_id)
            return

        mailer_url = os.environ.get("MAILER_URL")
        mailer_secret = os.environ.get("JWT_MAILER_SECRET")

        if not mailer_url or not mailer_secret:
            log.warning("notify_answer_delivered: MAILER_URL or JWT_MAILER_SECRET not set, skipping")
            return

        payload = {
            "user_email": row["usr_email"],
            "user_name": row["usr_name"] or row["usr_email"],
            "qtn_title": row["qtn_title"],
            "qtn_id": row["qtn_id"],
            "tkt_id": row["tkt_id"],
            "tkt_quote_cents": row["tkt_selected_quote_cents"],
            "tkt_currency": row["tkt_currency"],
        }

        encoded = jwt.encode(payload, mailer_secret, algorithm="HS256")
        url = f"{mailer_url}emailservice-ntsqr/answer_delivered/{encoded}"
        requests.get(url, timeout=10)

    except Exception:
        log.exception("notify_answer_delivered failed for ticket %s", tkt_id)


def notify_payer_quote_accepted(tkt_id: int):
    """Notify the payer that the student accepted a quote.

    Tells the payer: "Student X accepted a quote for question Y.
    Payment of Z EUR will be charged when the answer is delivered."

    Fails silently with a log warning so acceptance is never blocked by email errors.
    """
    try:
        row = db_get_payer_info_for_ticket(tkt_id)
        if not row:
            log.warning("notify_payer_quote_accepted: no payer info for ticket %s", tkt_id)
            return

        mailer_url = os.environ.get("MAILER_URL")
        mailer_secret = os.environ.get("JWT_MAILER_SECRET")

        if not mailer_url or not mailer_secret:
            log.warning("notify_payer_quote_accepted: MAILER_URL or JWT_MAILER_SECRET not set, skipping")
            return

        payload = {
            "user_email": row["payer_email"],
            "user_name": row["payer_name"] or row["payer_email"],
            "student_name": row["student_name"],
            "qtn_title": row["qtn_title"],
            "qtn_id": row["qtn_id"],
            "tkt_id": row["tkt_id"],
            "tkt_quote_cents": row["tkt_selected_quote_cents"],
            "tkt_currency": row["tkt_currency"],
        }

        encoded = jwt.encode(payload, mailer_secret, algorithm="HS256")
        url = f"{mailer_url}emailservice-ntsqr/payer_quote_accepted/{encoded}"
        requests.get(url, timeout=10)

    except Exception:
        log.exception("notify_payer_quote_accepted failed for ticket %s", tkt_id)


def notify_admin_payment_failed(tkt_id: int):
    """Notify the admin that a payment charge failed after delivery.

    Includes ticket ID, student name, payer email, amount, and error message.
    Fails silently with a log warning so delivery is never blocked.
    """
    try:
        payer_info = db_get_payer_info_for_ticket(tkt_id)
        from .db_payment import db_get_payment_for_ticket
        pay = db_get_payment_for_ticket(tkt_id)

        admin_email = os.environ.get("ADMIN_EMAIL")
        mailer_url = os.environ.get("MAILER_URL")
        mailer_secret = os.environ.get("JWT_MAILER_SECRET")

        if not admin_email or not mailer_url or not mailer_secret:
            log.warning("notify_admin_payment_failed: missing ADMIN_EMAIL, MAILER_URL, or JWT_MAILER_SECRET")
            return

        payload = {
            "user_email": admin_email,
            "user_name": "Admin",
            "tkt_id": tkt_id,
            "student_name": payer_info["student_name"] if payer_info else "unknown",
            "payer_email": payer_info["payer_email"] if payer_info else "unknown",
            "amount_cents": pay["pay_amount_cents"] if pay else 0,
            "currency": pay["pay_currency"] if pay else "EUR",
            "error_msg": pay["pay_error_msg"] if pay else "unknown",
        }

        encoded = jwt.encode(payload, mailer_secret, algorithm="HS256")
        url = f"{mailer_url}emailservice-ntsqr/payment_failed/{encoded}"
        requests.get(url, timeout=10)

    except Exception:
        log.exception("notify_admin_payment_failed failed for ticket %s", tkt_id)


def notify_payer_payment_failed(tkt_id: int):
    """Notify the payer that a payment charge failed.

    Tells the payer: "Payment failed for [student]'s question [title].
    Please reconnect your PayPal account."

    Fails silently with a log warning so delivery is never blocked.
    """
    try:
        row = db_get_payer_info_for_ticket(tkt_id)
        if not row:
            log.warning("notify_payer_payment_failed: no payer info for ticket %s", tkt_id)
            return

        mailer_url = os.environ.get("MAILER_URL")
        mailer_secret = os.environ.get("JWT_MAILER_SECRET")

        if not mailer_url or not mailer_secret:
            log.warning("notify_payer_payment_failed: MAILER_URL or JWT_MAILER_SECRET not set, skipping")
            return

        from .db_payment import db_get_payment_for_ticket
        pay = db_get_payment_for_ticket(tkt_id)

        payload = {
            "user_email": row["payer_email"],
            "user_name": row["payer_name"] or row["payer_email"],
            "student_name": row["student_name"],
            "qtn_title": row["qtn_title"],
            "qtn_id": row["qtn_id"],
            "tkt_id": row["tkt_id"],
            "tkt_quote_cents": row["tkt_selected_quote_cents"],
            "tkt_currency": row["tkt_currency"],
            "error_msg": pay["pay_error_msg"] if pay else "unknown",
        }

        encoded = jwt.encode(payload, mailer_secret, algorithm="HS256")
        url = f"{mailer_url}emailservice-ntsqr/payer_payment_failed/{encoded}"
        requests.get(url, timeout=10)

    except Exception:
        log.exception("notify_payer_payment_failed failed for ticket %s", tkt_id)


def notify_student_quote_ready(tkt_id: int):
    """Notify the student that a quote is ready for their question."""
    try:
        row = db_get_student_info_for_ticket(tkt_id)
        if not row:
            log.warning("notify_student_quote_ready: ticket %s not found", tkt_id)
            return

        mailer_url = os.environ.get("MAILER_URL")
        mailer_secret = os.environ.get("JWT_MAILER_SECRET")
        if not mailer_url or not mailer_secret:
            log.warning("notify_student_quote_ready: MAILER_URL or JWT_MAILER_SECRET not set, skipping")
            return

        payload = {
            "user_email": row["usr_email"],
            "user_name": row["usr_name"] or row["usr_email"],
            "qtn_title": row["qtn_title"],
            "qtn_id": row["qtn_id"],
            "tkt_id": row["tkt_id"],
        }

        encoded = jwt.encode(payload, mailer_secret, algorithm="HS256")
        url = f"{mailer_url}emailservice-ntsqr/quote_ready/{encoded}"
        requests.get(url, timeout=10)

    except Exception:
        log.exception("notify_student_quote_ready failed for ticket %s", tkt_id)


def notify_student_quote_accepted(tkt_id: int):
    """Send the student a confirmation that they accepted the quote."""
    try:
        row = db_get_student_info_for_ticket(tkt_id)
        if not row:
            log.warning("notify_student_quote_accepted: ticket %s not found", tkt_id)
            return

        mailer_url = os.environ.get("MAILER_URL")
        mailer_secret = os.environ.get("JWT_MAILER_SECRET")
        if not mailer_url or not mailer_secret:
            log.warning("notify_student_quote_accepted: MAILER_URL or JWT_MAILER_SECRET not set, skipping")
            return

        payload = {
            "user_email": row["usr_email"],
            "user_name": row["usr_name"] or row["usr_email"],
            "qtn_title": row["qtn_title"],
            "qtn_id": row["qtn_id"],
            "tkt_id": row["tkt_id"],
            "tkt_quote_cents": row["tkt_selected_quote_cents"],
            "tkt_currency": row["tkt_currency"],
        }

        encoded = jwt.encode(payload, mailer_secret, algorithm="HS256")
        url = f"{mailer_url}emailservice-ntsqr/quote_accepted/{encoded}"
        requests.get(url, timeout=10)

    except Exception:
        log.exception("notify_student_quote_accepted failed for ticket %s", tkt_id)


def notify_tutor_assigned(tkt_id: int):
    """Notify the tutor that they have been assigned to a ticket."""
    try:
        from .db_ticket import db_get_tutor_info_for_ticket
        row = db_get_tutor_info_for_ticket(tkt_id)
        if not row:
            log.warning("notify_tutor_assigned: ticket %s has no tutor", tkt_id)
            return

        mailer_url = os.environ.get("MAILER_URL")
        mailer_secret = os.environ.get("JWT_MAILER_SECRET")
        if not mailer_url or not mailer_secret:
            log.warning("notify_tutor_assigned: MAILER_URL or JWT_MAILER_SECRET not set, skipping")
            return

        payload = {
            "user_email": row["usr_email"],
            "user_name": row["usr_name"] or row["usr_email"],
            "qtn_title": row["qtn_title"],
            "qtn_id": row["qtn_id"],
            "tkt_id": row["tkt_id"],
        }

        encoded = jwt.encode(payload, mailer_secret, algorithm="HS256")
        url = f"{mailer_url}emailservice-ntsqr/tutor_assigned/{encoded}"
        requests.get(url, timeout=10)

    except Exception:
        log.exception("notify_tutor_assigned failed for ticket %s", tkt_id)


def notify_tutor_ticket_closed(tkt_id: int):
    """Notify the tutor that the student accepted delivery and closed the ticket."""
    try:
        from .db_ticket import db_get_tutor_info_for_ticket
        row = db_get_tutor_info_for_ticket(tkt_id)
        if not row:
            log.warning("notify_tutor_ticket_closed: ticket %s has no tutor", tkt_id)
            return

        mailer_url = os.environ.get("MAILER_URL")
        mailer_secret = os.environ.get("JWT_MAILER_SECRET")
        if not mailer_url or not mailer_secret:
            log.warning("notify_tutor_ticket_closed: MAILER_URL or JWT_MAILER_SECRET not set, skipping")
            return

        payload = {
            "user_email": row["usr_email"],
            "user_name": row["usr_name"] or row["usr_email"],
            "qtn_title": row["qtn_title"],
            "qtn_id": row["qtn_id"],
            "tkt_id": row["tkt_id"],
        }

        encoded = jwt.encode(payload, mailer_secret, algorithm="HS256")
        url = f"{mailer_url}emailservice-ntsqr/ticket_closed/{encoded}"
        requests.get(url, timeout=10)

    except Exception:
        log.exception("notify_tutor_ticket_closed failed for ticket %s", tkt_id)


def notify_tutor_question_deleted(tkt_id: int):
    """Notify the tutor that the student deleted a question they were assigned to."""
    try:
        from .db_ticket import db_get_tutor_info_for_ticket
        row = db_get_tutor_info_for_ticket(tkt_id)
        if not row:
            log.warning("notify_tutor_question_deleted: ticket %s has no tutor", tkt_id)
            return

        mailer_url = os.environ.get("MAILER_URL")
        mailer_secret = os.environ.get("JWT_MAILER_SECRET")
        if not mailer_url or not mailer_secret:
            log.warning("notify_tutor_question_deleted: MAILER_URL or JWT_MAILER_SECRET not set, skipping")
            return

        payload = {
            "user_email": row["usr_email"],
            "user_name": row["usr_name"] or row["usr_email"],
            "qtn_title": row["qtn_title"],
            "qtn_id": row["qtn_id"],
            "tkt_id": row["tkt_id"],
        }

        encoded = jwt.encode(payload, mailer_secret, algorithm="HS256")
        url = f"{mailer_url}emailservice-ntsqr/question_deleted/{encoded}"
        requests.get(url, timeout=10)

    except Exception:
        log.exception("notify_tutor_question_deleted failed for ticket %s", tkt_id)


def notify_student_answer_ready(tkt_id: int):
    """Notify the student that their answer has been delivered (or is pending payment)."""
    try:
        row = db_get_student_info_for_ticket(tkt_id)
        if not row:
            log.warning("notify_student_answer_ready: ticket %s not found", tkt_id)
            return

        mailer_url = os.environ.get("MAILER_URL")
        mailer_secret = os.environ.get("JWT_MAILER_SECRET")
        if not mailer_url or not mailer_secret:
            log.warning("notify_student_answer_ready: MAILER_URL or JWT_MAILER_SECRET not set, skipping")
            return

        payload = {
            "user_email": row["usr_email"],
            "user_name": row["usr_name"] or row["usr_email"],
            "qtn_title": row["qtn_title"],
            "qtn_id": row["qtn_id"],
            "tkt_id": row["tkt_id"],
        }

        encoded = jwt.encode(payload, mailer_secret, algorithm="HS256")
        url = f"{mailer_url}emailservice-ntsqr/answer_ready/{encoded}"
        requests.get(url, timeout=10)

    except Exception:
        log.exception("notify_student_answer_ready failed for ticket %s", tkt_id)


def notify_student_needs_clarification(tkt_id: int, student_hint: str):
    """Notify the student that their question needs clarification before it can be quoted."""
    try:
        row = db_get_student_info_for_ticket(tkt_id)
        if not row:
            log.warning("notify_student_needs_clarification: ticket %s not found", tkt_id)
            return

        mailer_url = os.environ.get("MAILER_URL")
        mailer_secret = os.environ.get("JWT_MAILER_SECRET")
        if not mailer_url or not mailer_secret:
            log.warning("notify_student_needs_clarification: MAILER_URL or JWT_MAILER_SECRET not set, skipping")
            return

        payload = {
            "user_email": row["usr_email"],
            "user_name": row["usr_name"] or row["usr_email"],
            "qtn_title": row["qtn_title"],
            "qtn_id": row["qtn_id"],
            "tkt_id": row["tkt_id"],
            "student_hint": student_hint or "",
        }

        encoded = jwt.encode(payload, mailer_secret, algorithm="HS256")
        url = f"{mailer_url}emailservice-ntsqr/needs_clarification/{encoded}"
        requests.get(url, timeout=10)

    except Exception:
        log.exception("notify_student_needs_clarification failed for ticket %s", tkt_id)


def notify_student_quote_rejected(tkt_id: int):
    """Send the student a confirmation that they declined the quote."""
    try:
        row = db_get_student_info_for_ticket(tkt_id)
        if not row:
            log.warning("notify_student_quote_rejected: ticket %s not found", tkt_id)
            return

        mailer_url = os.environ.get("MAILER_URL")
        mailer_secret = os.environ.get("JWT_MAILER_SECRET")
        if not mailer_url or not mailer_secret:
            log.warning("notify_student_quote_rejected: MAILER_URL or JWT_MAILER_SECRET not set, skipping")
            return

        payload = {
            "user_email": row["usr_email"],
            "user_name": row["usr_name"] or row["usr_email"],
            "qtn_title": row["qtn_title"],
            "qtn_id": row["qtn_id"],
            "tkt_id": row["tkt_id"],
        }

        encoded = jwt.encode(payload, mailer_secret, algorithm="HS256")
        url = f"{mailer_url}emailservice-ntsqr/quote_rejected/{encoded}"
        requests.get(url, timeout=10)

    except Exception:
        log.exception("notify_student_quote_rejected failed for ticket %s", tkt_id)


def notify_student_ticket_closed(tkt_id: int):
    """Send the student a confirmation that they accepted delivery and closed the ticket."""
    try:
        row = db_get_student_info_for_ticket(tkt_id)
        if not row:
            log.warning("notify_student_ticket_closed: ticket %s not found", tkt_id)
            return

        mailer_url = os.environ.get("MAILER_URL")
        mailer_secret = os.environ.get("JWT_MAILER_SECRET")
        if not mailer_url or not mailer_secret:
            log.warning("notify_student_ticket_closed: MAILER_URL or JWT_MAILER_SECRET not set, skipping")
            return

        payload = {
            "user_email": row["usr_email"],
            "user_name": row["usr_name"] or row["usr_email"],
            "qtn_title": row["qtn_title"],
            "qtn_id": row["qtn_id"],
            "tkt_id": row["tkt_id"],
        }

        encoded = jwt.encode(payload, mailer_secret, algorithm="HS256")
        url = f"{mailer_url}emailservice-ntsqr/student_ticket_closed/{encoded}"
        requests.get(url, timeout=10)

    except Exception:
        log.exception("notify_student_ticket_closed failed for ticket %s", tkt_id)
