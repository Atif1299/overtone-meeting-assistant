"""Verify Recall.ai webhook signatures (Svix-compatible). See:
https://docs.recall.ai/docs/authenticating-requests-from-recallai
"""

from __future__ import annotations

import base64
import binascii
import hmac
import hashlib
from typing import Mapping


def verify_recall_signature(
    secret: str,
    headers: Mapping[str, str],
    raw_body: bytes,
) -> bool:
    """
    Returns True if signature matches. Secret must be whsec_... from Recall dashboard.
    """
    if not secret or not secret.startswith("whsec_"):
        return False

    msg_id = _hdr(headers, "webhook-id") or _hdr(headers, "svix-id")
    msg_ts = _hdr(headers, "webhook-timestamp") or _hdr(headers, "svix-timestamp")
    msg_sig = _hdr(headers, "webhook-signature") or _hdr(headers, "svix-signature")

    if not msg_id or not msg_ts or not msg_sig:
        return False

    try:
        key = base64.b64decode(secret[6:])
    except binascii.Error:
        return False

    payload_str = raw_body.decode("utf-8") if raw_body else ""
    to_sign = f"{msg_id}.{msg_ts}.{payload_str}".encode("utf-8")
    expected = base64.b64encode(hmac.new(key, to_sign, hashlib.sha256).digest()).decode("ascii")

    for part in msg_sig.split():
        if "," not in part:
            continue
        version, signature_b64 = part.split(",", 1)
        if version != "v1":
            continue
        try:
            sig_bytes = base64.b64decode(signature_b64)
            exp_bytes = base64.b64decode(expected)
        except binascii.Error:
            continue
        if len(sig_bytes) == len(exp_bytes) and hmac.compare_digest(sig_bytes, exp_bytes):
            return True
    return False


def _hdr(headers: Mapping[str, str], name: str) -> str | None:
    for k, v in headers.items():
        if k.lower() == name.lower():
            return v
    return None
