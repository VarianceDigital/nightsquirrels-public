# nightsquirrel/paypal.py
"""Low-level PayPal REST API wrapper.

No Flask/DB imports -- just ``requests`` + ``os``.
All public functions raise ``PayPalError`` on non-2xx responses.
"""
import os
import requests

PAYPAL_SANDBOX_URL = "https://api-m.sandbox.paypal.com"
PAYPAL_LIVE_URL = "https://api-m.paypal.com"


class PayPalError(Exception):
    """Raised when a PayPal API call returns a non-2xx status."""

    def __init__(self, message: str, status_code: int = 0, response_body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


# ── internal helpers ──────────────────────────────────────────────

def _get_base_url() -> str:
    mode = os.environ.get("PAYPAL_MODE", "sandbox").lower()
    if mode == "live":
        return PAYPAL_LIVE_URL
    return PAYPAL_SANDBOX_URL


def _get_access_token() -> str:
    """Obtain a short-lived access token via client-credentials grant."""
    client_id = os.environ["PAYPAL_CLIENT_ID"]
    client_secret = os.environ["PAYPAL_CLIENT_SECRET"]

    url = f"{_get_base_url()}/v1/oauth2/token"
    resp = requests.post(
        url,
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        headers={"Accept": "application/json"},
        timeout=15,
    )

    if not resp.ok:
        raise PayPalError(
            f"OAuth token request failed ({resp.status_code})",
            status_code=resp.status_code,
            response_body=resp.text,
        )

    return resp.json()["access_token"]


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_access_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _check(resp: requests.Response) -> dict:
    """Return JSON body or raise ``PayPalError``."""
    if not resp.ok:
        raise PayPalError(
            f"PayPal API error ({resp.status_code}): {resp.text}",
            status_code=resp.status_code,
            response_body=resp.text,
        )
    return resp.json()


# ── Vault API (v3) ───────────────────────────────────────────────

def create_vault_setup_token(return_url: str, cancel_url: str) -> dict:
    """POST /v3/vault/setup-tokens -- start the vault flow."""
    url = f"{_get_base_url()}/v3/vault/setup-tokens"
    body = {
        "payment_source": {
            "paypal": {
                "usage_type": "MERCHANT",
                "experience_context": {
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                },
            }
        }
    }
    resp = requests.post(url, json=body, headers=_headers(), timeout=15)
    return _check(resp)


def create_payment_token(setup_token_id: str) -> dict:
    """POST /v3/vault/payment-tokens -- exchange setup-token for vault token."""
    url = f"{_get_base_url()}/v3/vault/payment-tokens"
    body = {
        "payment_source": {
            "token": {
                "id": setup_token_id,
                "type": "SETUP_TOKEN",
            }
        }
    }
    resp = requests.post(url, json=body, headers=_headers(), timeout=15)
    return _check(resp)


# ── Orders API (v2) ──────────────────────────────────────────────

def create_order(vault_id: str, amount_cents: int,
                 currency: str, reference_id: str) -> dict:
    """POST /v2/checkout/orders -- create a CAPTURE-intent order."""
    url = f"{_get_base_url()}/v2/checkout/orders"
    amount_str = f"{amount_cents / 100:.2f}"
    body = {
        "intent": "CAPTURE",
        "payment_source": {
            "paypal": {
                "vault_id": vault_id,
            }
        },
        "purchase_units": [
            {
                "reference_id": reference_id,
                "amount": {
                    "currency_code": currency,
                    "value": amount_str,
                },
            }
        ],
    }
    headers = _headers()
    headers["PayPal-Request-Id"] = reference_id
    resp = requests.post(url, json=body, headers=headers, timeout=15)
    return _check(resp)


def capture_order(order_id: str) -> dict:
    """POST /v2/checkout/orders/{id}/capture -- capture an approved order."""
    url = f"{_get_base_url()}/v2/checkout/orders/{order_id}/capture"
    resp = requests.post(url, json={}, headers=_headers(), timeout=15)
    return _check(resp)
