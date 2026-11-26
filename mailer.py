"""Send an email with attachments, for free, from wherever the app runs.

Render's free plan blocks the mail ports (SMTP), so mail goes over HTTPS:
- Resend (the default): a free account and one API key, pasted in Settings (RESEND_API_KEY). Free plan:
  100 emails a day. Without a domain of your own it sends to the address the account was made with.
- A Google Apps Script relay (MAIL_SCRIPT_URL + MAIL_SCRIPT_TOKEN), or Brevo (BREVO_API_KEY + EMAIL_FROM),
  when those are set instead.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import urllib.error
import urllib.request

SCRIPT = """// Job Finder mailer: sends the app's emails from your own Gmail.
const TOKEN = "{token}";

function doPost(e) {
  const d = JSON.parse(e.postData.contents);
  if (d.token !== TOKEN) return reply({ ok: false, error: "wrong token" });
  const files = (d.attachments || []).map(function (a) {
    return Utilities.newBlob(Utilities.base64Decode(a.data), a.mime, a.name);
  });
  MailApp.sendEmail({ to: d.to, subject: d.subject, htmlBody: d.html, name: d.from_name || "Job Finder",
                      attachments: files });
  return reply({ ok: true, left: MailApp.getRemainingDailyQuota() });
}

function reply(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
"""


class MailError(RuntimeError):
    """Mail isn't set up, or the sender refused: the message says what to do."""


def method() -> str:
    if os.environ.get("RESEND_API_KEY", "").strip():
        return "resend"
    if os.environ.get("MAIL_SCRIPT_URL", "").strip() and os.environ.get("MAIL_SCRIPT_TOKEN", "").strip():
        return "script"
    if os.environ.get("BREVO_API_KEY", "").strip() and os.environ.get("EMAIL_FROM", "").strip():
        return "brevo"
    return ""


def new_token() -> str:
    return secrets.token_urlsafe(24)


def script_code(token: str) -> str:
    return SCRIPT.replace("{token}", token)


def send(to: str, subject: str, html: str, attachments: list[tuple[str, bytes, str]] | None = None,
         from_name: str = "Job Finder", resend_key: str | None = None) -> None:
    """attachments: (file name, bytes, MIME type). resend_key: one person's own Resend key (their
    profile's), used instead of the app's."""
    files = [{"name": n, "mime": m, "data": base64.b64encode(b).decode("ascii")} for n, b, m in attachments or []]
    how = "resend" if resend_key else method()
    if how == "resend":
        _send_resend(to, subject, html, files, from_name, resend_key or os.environ["RESEND_API_KEY"].strip())
    elif how == "script":
        _send_script(to, subject, html, files, from_name)
    elif how == "brevo":
        _send_brevo(to, subject, html, files, from_name)
    else:
        raise MailError("Email isn't set up yet. Open Settings, then Email, and paste your Resend key.")


RESEND_URL = "https://api.resend.com/emails"


def _send_resend(to, subject, html, files, from_name, key) -> None:
    body = {"from": f"{from_name} <{os.environ.get('RESEND_FROM', '').strip() or 'onboarding@resend.dev'}>",
            "to": [a.strip() for a in to.split(",") if a.strip()], "subject": subject, "html": html}
    if files:
        body["attachments"] = [{"filename": f["name"], "content": f["data"]} for f in files]
    req = urllib.request.Request(RESEND_URL, data=json.dumps(body).encode("utf-8"), method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "User-Agent": "job-finder/1.0"})          # their firewall turns away Python's default agent
    try:
        with urllib.request.urlopen(req, timeout=90):
            pass
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8", "replace")).get("message", "")
        except (json.JSONDecodeError, AttributeError):
            detail = ""
        if exc.code in (401, 403) and "own email" not in detail:
            raise MailError("Resend didn't accept the key. Copy it again from resend.com (API Keys) and paste it "
                            "in Settings.") from exc
        if "own email" in detail or "verify a domain" in detail:
            raise MailError("Resend sends only to the email you signed up with. Use that address in "
                            f"\"Send matches to\". ({detail})") from exc
        raise MailError(f"Resend refused the email: {detail or exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise MailError(f"Couldn't reach Resend ({getattr(exc, 'reason', exc)}).") from exc


def _send_script(to, subject, html, files, from_name) -> None:
    payload = json.dumps({"token": os.environ["MAIL_SCRIPT_TOKEN"].strip(), "to": to, "subject": subject,
                          "html": html, "attachments": files, "from_name": from_name}).encode("utf-8")
    req = urllib.request.Request(os.environ["MAIL_SCRIPT_URL"].strip(), data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        # Google answers with a redirect to the result, which urllib follows as a GET - as it should.
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise MailError(f"Google refused the email (HTTP {exc.code}). Check the script's web-app link in Settings.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise MailError(f"Couldn't reach the Google script ({getattr(exc, 'reason', exc)}).") from exc
    try:
        answer = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MailError("The Google script didn't answer. Deploy it as a web app with \"Who has access: Anyone\", "
                        "then paste its new link in Settings.") from exc
    if not answer.get("ok"):
        hint = " Paste the script again from Settings: its token changed." if answer.get("error") == "wrong token" else ""
        raise MailError(f"The Google script refused: {answer.get('error', 'unknown error')}.{hint}")


def _send_brevo(to, subject, html, files, from_name) -> None:
    body = {"sender": {"email": os.environ["EMAIL_FROM"].strip(), "name": from_name},
            "to": [{"email": a.strip()} for a in to.split(",") if a.strip()],
            "subject": subject, "htmlContent": html}
    if files:
        body["attachment"] = [{"name": f["name"], "content": f["data"]} for f in files]
    req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=json.dumps(body).encode("utf-8"),
                                 headers={"api-key": os.environ["BREVO_API_KEY"].strip(),
                                          "Content-Type": "application/json", "Accept": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90):
            pass
    except urllib.error.HTTPError as exc:
        raise MailError(f"Brevo refused the email: {exc.read().decode('utf-8', 'replace')[:200]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise MailError(f"Couldn't reach Brevo ({getattr(exc, 'reason', exc)}).") from exc
