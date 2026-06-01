# nightsquirrel/payment.py
"""Business-logic orchestrator that ties PayPal API + DB together.

Called from ``bl_tutor.py`` when a tutor delivers an answer.
"""
import logging
from .paypal import create_order, capture_order, PayPalError
from .db_payment import (
    db_get_payment_for_ticket,
    db_get_default_payment_method,
    db_update_payment_captured,
    db_update_payment_failed,
)
from .db_ticket import db_set_ticket_delivered
from .db_auth import db_get_user_by_id
from .notifications import notify_answer_delivered

log = logging.getLogger(__name__)


def attempt_payment_for_ticket(tkt_id: int) -> bool:
    """Try to charge the payer for the given ticket.

    Returns True if the payment was captured (or was already captured / not
    required).  Returns False on failure (payment marked ``failed`` in DB).
    """
    pay = db_get_payment_for_ticket(tkt_id)

    # No payment record or already captured → nothing to do
    if not pay:
        return True
    if pay["pay_status"] == "captured":
        return True

    # Only attempt charge on payments awaiting charge
    # (other statuses like 'failed' or 'refunded' are terminal)
    if pay["pay_status"] != "awaiting_charge":
        return False

    payer_user = db_get_user_by_id(pay["payer_usr_id"])
    if not payer_user or not payer_user.get("usr_isvalid"):
        db_update_payment_failed(pay["pay_id"], "Payer account is suspended")
        return False

    pmt = db_get_default_payment_method(pay["payer_usr_id"])
    if not pmt or not pmt.get("pmt_paypal_vault_id"):
        db_update_payment_failed(pay["pay_id"], "No vaulted payment method")
        return False

    # Check vault is in a chargeable state
    if pmt.get("pmt_vault_status") != "vaulted":
        db_update_payment_failed(pay["pay_id"],
            f"Vault not chargeable (status: {pmt.get('pmt_vault_status')})")
        return False

    vault_id = pmt["pmt_paypal_vault_id"]

    try:
        order = create_order(
            vault_id=vault_id,
            amount_cents=pay["pay_amount_cents"],
            currency=pay["pay_currency"],
            reference_id=f"TKT-{tkt_id}",
        )
        order_id = order["id"]

        # With a vault_id, PayPal auto-captures on order creation.
        # Only call capture_order() if the order isn't already completed.
        if order.get("status") == "COMPLETED":
            capture_id = (
                order["purchase_units"][0]["payments"]["captures"][0]["id"]
            )
        else:
            capture_resp = capture_order(order_id)
            capture_id = (
                capture_resp["purchase_units"][0]["payments"]["captures"][0]["id"]
            )

        db_update_payment_captured(pay["pay_id"], order_id, capture_id)
        db_set_ticket_delivered(tkt_id)
        notify_answer_delivered(tkt_id)
        return True

    except PayPalError as exc:
        log.exception("PayPal charge failed for ticket %s", tkt_id)
        db_update_payment_failed(pay["pay_id"], str(exc))
        return False

    except Exception as exc:
        log.exception("Unexpected error charging ticket %s", tkt_id)
        db_update_payment_failed(pay["pay_id"], str(exc))
        return False
