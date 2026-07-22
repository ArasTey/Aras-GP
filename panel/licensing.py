"""Offline licence gate (opt-in).

Design constraints, in order of importance:

1. **No network.** Verification is a local Ed25519 signature check. The panel
   never contacts a licence server, because a censorship-circumvention tool that
   phones home hands whoever controls (or seizes) that server a list of its own
   users. There is no activation call, no heartbeat, no remote kill switch.
2. **Off by default.** With no public key baked in, :func:`enforced` is False and
   the panel starts normally. A vendor who wants the gate runs ``keygen``, pastes
   the public key into :data:`LICENSE_PUBLIC_KEY`, keeps the private key, and
   issues signed licence files.
3. **Auditable.** Nothing here is obfuscated. A user can read exactly what the
   check does, which is the point — a security tool the user cannot audit is
   worse than no tool.

CLI::

    python -m panel.licensing keygen  --out vendor-key.pem
    python -m panel.licensing sign    --key vendor-key.pem --licensee "..." --days 365
    python -m panel.licensing verify  --file panel/data/license.key
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
import uuid

from . import paths

# Paste the vendor's Ed25519 public key here (base64, raw 32 bytes) to arm the
# gate. Empty string = gate disabled, panel runs unrestricted.
LICENSE_PUBLIC_KEY = ""

_ENV_KEY = "ARAS_LICENSE_PUBKEY"


def _public_key_b64() -> str:
    return (os.environ.get(_ENV_KEY) or LICENSE_PUBLIC_KEY or "").strip()


def enforced() -> bool:
    """True when a public key is present, i.e. this build is licence-gated."""
    return bool(_public_key_b64())


def _canonical(payload: dict) -> bytes:
    """Deterministic byte form of the payload — what actually gets signed."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _load_ed25519():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey,
        )
    except ImportError:
        raise RuntimeError(
            "بسته‌ی cryptography نصب نیست؛ برای بررسی لایسنس لازم است."
        )
    return Ed25519PrivateKey, Ed25519PublicKey


# ── verification ──────────────────────────────────────────────────────


def verify_blob(blob: dict) -> dict:
    """Validate a licence document. Returns the payload or raises ValueError."""
    _, Ed25519PublicKey = _load_ed25519()

    public_b64 = _public_key_b64()
    if not public_b64:
        raise ValueError("این نسخه لایسنس‌محور نیست.")

    payload = blob.get("payload")
    signature = blob.get("sig")
    if not isinstance(payload, dict) or not signature:
        raise ValueError("ساختار فایل لایسنس نامعتبر است.")

    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_b64))
        public_key.verify(base64.b64decode(signature), _canonical(payload))
    except Exception:
        raise ValueError("امضای لایسنس معتبر نیست.")

    expires_at = payload.get("expires_at")
    if expires_at and time.time() > float(expires_at):
        raise ValueError("اعتبار لایسنس به پایان رسیده است.")

    return payload


def check(path: str | None = None) -> dict:
    """Panel-facing status. Never raises."""
    if not enforced():
        return {"required": False, "valid": True, "payload": None,
                "message": "این نسخه بدون قفل لایسنس اجرا می‌شود."}

    path = path or paths.LICENSE_FILE
    try:
        with open(path, encoding="utf-8") as handle:
            blob = json.load(handle)
    except FileNotFoundError:
        return {"required": True, "valid": False, "payload": None,
                "message": "فایل لایسنس پیدا نشد."}
    except json.JSONDecodeError:
        return {"required": True, "valid": False, "payload": None,
                "message": "فایل لایسنس قابل خواندن نیست."}

    try:
        payload = verify_blob(blob)
    except (ValueError, RuntimeError) as exc:
        return {"required": True, "valid": False, "payload": None,
                "message": str(exc)}

    return {"required": True, "valid": True, "payload": payload,
            "message": f"لایسنس معتبر — {payload.get('licensee', '')}"}


def guard() -> None:
    """Abort start-up when the gate is armed and the licence is missing/bad."""
    status = check()
    if status["required"] and not status["valid"]:
        raise SystemExit(f"Aras-GP Panel: {status['message']}")


# ── vendor-side CLI ───────────────────────────────────────────────────


def _keygen(args) -> None:
    from cryptography.hazmat.primitives import serialization
    Ed25519PrivateKey, _ = _load_ed25519()

    private_key = Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(pem)

    public_b64 = base64.b64encode(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")

    print(f"Private key written to {args.out} (mode 0600) — keep it offline.")
    print("Paste this into panel/licensing.py to arm the gate:\n")
    print(f'LICENSE_PUBLIC_KEY = "{public_b64}"')


def _sign(args) -> None:
    from cryptography.hazmat.primitives import serialization

    with open(args.key, "rb") as handle:
        private_key = serialization.load_pem_private_key(handle.read(), password=None)

    now = time.time()
    payload = {
        "id": str(uuid.uuid4()),
        "licensee": args.licensee,
        "issued_at": int(now),
        "expires_at": int(now + args.days * 86400) if args.days else None,
        "features": sorted(set(args.feature or [])),
    }
    signature = base64.b64encode(private_key.sign(_canonical(payload))).decode("ascii")
    blob = {"payload": payload, "sig": signature}

    output = args.out or paths.LICENSE_FILE
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(blob, handle, indent=2, ensure_ascii=False)
    print(f"Licence written to {output}")


def _verify(args) -> None:
    status = check(args.file)
    print(json.dumps(status, indent=2, ensure_ascii=False))
    raise SystemExit(0 if status["valid"] else 1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="panel.licensing",
                                     description="Aras-GP offline licence tools")
    sub = parser.add_subparsers(dest="command", required=True)

    keygen = sub.add_parser("keygen", help="generate a vendor signing key")
    keygen.add_argument("--out", default="aras-license-key.pem")
    keygen.set_defaults(func=_keygen)

    sign = sub.add_parser("sign", help="issue a signed licence file")
    sign.add_argument("--key", required=True)
    sign.add_argument("--licensee", required=True)
    sign.add_argument("--days", type=int, default=365, help="0 = perpetual")
    sign.add_argument("--feature", action="append")
    sign.add_argument("--out")
    sign.set_defaults(func=_sign)

    verify = sub.add_parser("verify", help="check a licence file")
    verify.add_argument("--file", default=paths.LICENSE_FILE)
    verify.set_defaults(func=_verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
