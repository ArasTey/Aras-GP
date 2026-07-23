"""Google Apps Script generation.

**Chosen option: the simple, honest one.** The panel renders ``Code.gs`` with the
operator's ``AUTH_KEY`` and Worker URL already substituted, offers a copy button
and a step-by-step guide, and asks for the Deployment ID back.

Full API-driven GAS deployment is *not* implemented, and the reason is worth
stating rather than hiding behind a disabled button: it requires an OAuth2 client
registered in a Google Cloud project, the Apps Script API switched on for the
end user's own account, and a consent screen the operator has to publish. That
is a heavier prerequisite than deploying the script by hand, so automating it
would trade five minutes of copy-paste for an hour of Google Cloud setup. If the
prerequisite is ever acceptable for a given deployment, the seam for it is this
module: add an ``deploy_via_api()`` alongside :func:`render` and have the panel
call it when credentials exist.
"""

from __future__ import annotations

import json
import re

from . import paths

_AUTH_KEY_RE = re.compile(r'const\s+AUTH_KEY\s*=\s*"[^"]*"\s*;')
_WORKER_URL_RE = re.compile(r'const\s+WORKER_URL\s*=\s*"[^"]*"\s*;')

# Apps Script deployment IDs are long opaque tokens; anything shorter is a
# paste of the wrong field (project ID, script ID, or the /exec URL).
DEPLOYMENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,120}$")


class GasError(ValueError):
    """Raised with a Persian, user-facing message."""


def load_template() -> str:
    with open(paths.GAS_TEMPLATE, encoding="utf-8") as handle:
        return handle.read()


def render(auth_key: str, worker_url: str, source: str | None = None) -> str:
    """Return ``Code.gs`` with the two constants filled in."""
    if not auth_key:
        # The panel mints this automatically, so reaching here means something
        # deeper is wrong rather than a step the operator skipped.
        raise GasError("کلید احراز هویت هنوز ساخته نشده — صفحه‌ی دیپلوی را باز کنید.")
    worker_url = (worker_url or "").strip().rstrip("/")
    if not worker_url:
        raise GasError(
            "هنوز Worker ندارید. اول مرحله‌ی ۱ (دیپلوی Cloudflare Worker) را "
            "انجام دهید؛ بعد کد Apps Script خودش ساخته می‌شود."
        )
    if not worker_url.startswith("https://"):
        raise GasError("آدرس Worker باید با https:// شروع شود.")

    source = source if source is not None else load_template()
    # json.dumps gives us correct JS string escaping for any secret the
    # operator generated, including quotes and backslashes.
    source = _AUTH_KEY_RE.sub(
        lambda _m: f"const AUTH_KEY = {json.dumps(auth_key)};", source, count=1,
    )
    source = _WORKER_URL_RE.sub(
        lambda _m: f"const WORKER_URL = {json.dumps(worker_url)};", source, count=1,
    )
    return source


def normalize_deployment_id(value: str) -> str:
    """Accept a bare ID or a full ``/macros/s/<id>/exec`` URL."""
    text = str(value or "").strip()
    if not text:
        raise GasError("شناسه استقرار خالی است.")
    match = re.search(r"/macros/s/([A-Za-z0-9_-]+)/(?:exec|dev)", text)
    if match:
        text = match.group(1)
    text = text.strip().strip("/")
    if not DEPLOYMENT_ID_RE.match(text):
        raise GasError(
            "شناسه استقرار معتبر نیست. مقدار درست، رشته‌ی بلندی است که در "
            "آدرس .../macros/s/<این-قسمت>/exec دیده می‌شود."
        )
    return text


def exec_url(deployment_id: str) -> str:
    return f"https://script.google.com/macros/s/{deployment_id}/exec"


#: The manual deploy walkthrough shown next to the generated code.
STEPS: tuple[dict, ...] = (
    {
        "title": "ساخت پروژه جدید",
        "body": "به script.google.com بروید و روی «New project» کلیک کنید.",
    },
    {
        "title": "جای‌گذاری کد",
        "body": "همه‌ی محتوای فایل Code.gs را پاک کنید و کد تولیدشده‌ی روبه‌رو "
                "را جای‌گذاری کنید. همه‌چیز از قبل داخلش پر شده — چیزی برای "
                "ویرایش نیست.",
    },
    {
        "title": "ذخیره پروژه",
        "body": "با Ctrl+S (یا ⌘+S) ذخیره کنید و یک نام دلخواه بگذارید.",
    },
    {
        "title": "استقرار به‌عنوان Web App",
        "body": "از منوی Deploy گزینه‌ی «New deployment» را بزنید، نوع را روی "
                "«Web app» بگذارید.",
    },
    {
        "title": "تنظیم دسترسی",
        "body": "مقدار «Execute as» را روی Me و «Who has access» را روی "
                "Anyone بگذارید؛ در غیر این صورت رله نمی‌تواند به آن وصل شود.",
    },
    {
        "title": "تأیید مجوزها",
        "body": "در اولین استقرار، Google اجازه‌ی دسترسی می‌خواهد. Advanced را "
                "بزنید و اجازه بدهید.",
    },
    {
        "title": "برگرداندن Deployment ID",
        "body": "آدرس نهایی به شکل .../macros/s/XXXX/exec است. کل آدرس یا "
                "فقط بخش XXXX را در کادر پایین وارد کنید.",
    },
)
