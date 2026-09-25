"""MirPay (mirpay.uz) card payments. Enabled only when MIRPAY_KASSA_ID and MIRPAY_API_KEY are set."""

import time

import httpx

from config import MIRPAY_API_KEY, MIRPAY_KASSA_ID, log

API = "https://mirpay.uz/api"
_token = {"value": None, "expires": 0.0}


def enabled():
    return bool(MIRPAY_KASSA_ID and MIRPAY_API_KEY)


async def _get_token(client):
    if _token["value"] and _token["expires"] > time.time(): return _token["value"]
    r = await client.post(f"{API}/connect", params={"kassaid": MIRPAY_KASSA_ID, "api_key": MIRPAY_API_KEY})
    r.raise_for_status()
    _token["value"] = r.json().get("token"); _token["expires"] = time.time() + 23 * 3600
    return _token["value"]


async def create_payment(summa, info):
    """Returns (invoice_id, pay_url) or (None, None)."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            token = await _get_token(client)
            r = await client.post(f"{API}/create-pay", params={"summa": summa, "info_pay": info}, headers={"Authorization": f"Bearer {token}"})
            r.raise_for_status(); data = r.json()
        return data.get("id"), (data.get("payinfo") or {}).get("redicet_url")
    except (httpx.HTTPError, ValueError) as e:
        log.warning("mirpay create failed: %s", e); return None, None


async def is_paid(invoice_id, expected_summa):
    """True only when MirPay reports the invoice as paid (and for the expected amount, when it tells)."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            token = await _get_token(client)
            r = await client.post(f"{API}/pay/invoice/", data={"payid": invoice_id}, headers={"Authorization": f"Bearer {token}"})
            r.raise_for_status(); info = (r.json() or {}).get("payinfo") or {}
    except (httpx.HTTPError, ValueError) as e:
        log.warning("mirpay check failed: %s", e); return False
    if info.get("status") != "Muvaffaqiyatli": return False
    summa = info.get("summa") or info.get("amount")
    try: return summa is None or int(float(summa)) >= int(expected_summa)
    except (TypeError, ValueError): return False
