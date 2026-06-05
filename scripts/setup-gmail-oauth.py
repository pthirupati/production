#!/usr/bin/env python3
"""
One-time setup: obtain Gmail API refresh token for production email sending.

Prerequisites:
  1. Google Cloud Console → create project → enable Gmail API
  2. OAuth consent screen (External) → add scope: .../auth/gmail.send
  3. Credentials → OAuth client ID → Desktop app
  4. Add your Gmail as a test user on the consent screen (while in Testing mode)

Usage:
  pip install google-auth-oauthlib google-api-python-client
  export GMAIL_OAUTH_CLIENT_ID=xxx.apps.googleusercontent.com
  export GMAIL_OAUTH_CLIENT_SECRET=xxx
  python scripts/setup-gmail-oauth.py

Add the printed refresh token to .env.production:
  GMAIL_OAUTH_REFRESH_TOKEN=...
  GMAIL_OAUTH_CLIENT_ID=...
  GMAIL_OAUTH_CLIENT_SECRET=...
  EMAIL_HOST_USER=your@gmail.com
"""
import os
import sys

CLIENT_ID = os.environ.get("GMAIL_OAUTH_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GMAIL_OAUTH_CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET", "")

if not CLIENT_ID or not CLIENT_SECRET:
    print("Set GMAIL_OAUTH_CLIENT_ID and GMAIL_OAUTH_CLIENT_SECRET (or reuse GOOGLE_CLIENT_* from .env)")
    sys.exit(1)

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Install: pip install google-auth-oauthlib google-api-python-client")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    },
    SCOPES,
)

print("Opening browser — sign in with the Gmail account that should SEND emails (e.g. fixitlab@gmail.com)")


def run_oauth_flow():
    """Bind localhost; try several ports if 8099 is still held by a stale run."""
    last_err = None
    for port in (8099, 8100, 8101, 8102, 0):
        try:
            label = "auto" if port == 0 else str(port)
            print(f"Starting local OAuth callback on port {label}...")
            return flow.run_local_server(port=port, prompt="consent", open_browser=True)
        except OSError as exc:
            if getattr(exc, "errno", None) == 48:
                print(f"Port {port} already in use, trying another...")
                last_err = exc
                continue
            raise
    print(
        "\nAll ports busy. Free port 8099 and retry:\n"
        "  lsof -ti :8099 | xargs kill -9\n"
        "Then run this script again."
    )
    if last_err:
        raise last_err
    sys.exit(1)


creds = run_oauth_flow()

print("\n--- Add these to .env.production ---")
print(f"GMAIL_OAUTH_CLIENT_ID={CLIENT_ID}")
print(f"GMAIL_OAUTH_CLIENT_SECRET={CLIENT_SECRET}")
print(f"GMAIL_OAUTH_REFRESH_TOKEN={creds.refresh_token}")
print(f"EMAIL_HOST_USER=<the Gmail address you signed in with>")
print("\nThen rebuild/restart backend + celery_worker on the server.")
