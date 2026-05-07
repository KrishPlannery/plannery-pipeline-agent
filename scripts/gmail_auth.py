"""
One-time Gmail OAuth2 flow.
Run locally to generate token.json, then upload to Secret Manager:

    python scripts/gmail_auth.py
    gcloud secrets create plannery/gmail-oauth-token \
        --data-file=token.json \
        --project=plannery-agents

Do NOT commit token.json to git (it is in .gitignore).
"""

import json
import os

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://mail.google.com/"]
CREDS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def main():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_FILE):
                print(f"❌ {CREDS_FILE} not found. Download OAuth2 credentials from GCP Console.")
                return
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            token_data = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes) if creds.scopes else SCOPES,
            }
            json.dump(token_data, f, indent=2)

    print(f"✅ token.json written. Upload to Secret Manager:")
    print(f"   gcloud secrets create plannery/gmail-oauth-token --data-file=token.json --project=plannery-agents")


if __name__ == "__main__":
    main()
