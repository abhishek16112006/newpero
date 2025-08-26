# QR Document Access (Demo)

A simple Flask app where each user gets a unique QR code to access their uploaded document (e.g., ID proof).

> ⚠️ **Security note:** This is a learning/demo project. For real Aadhaar or any sensitive IDs, add proper auth, HTTPS, short-expiry tokens, audit logs, encryption-at-rest, and access controls. Do not expose `/uploads` publicly in production.

## Features
- Register users (name + optional email)
- Upload a document per user (PDF/JPG/PNG/WEBP; 10 MB limit)
- Auto-generate a unique token + QR code
- Access the document by scanning the QR (or using the link)
- SQLite DB for persistence

## Quickstart
```bash
# 1) Create venv (Windows PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2) Install deps
pip install -r requirements.txt

# 3) Run
python app.py

# Open http://localhost:5000
```

## How it works
- When you upload a document, the app stores it in `uploads/` and creates a random token.
- The QR encodes `http://<your-host>:5000/d/<token>`.
- Visiting that link shows a page with a button to view the file served from `/uploads/<file>`.

## Folder structure
```
qr_doc_site/
  app.py
  app.db           # auto-created
  requirements.txt
  templates/
  uploads/         # user files (created at runtime)
  qrcodes/         # generated QR images
```

## Hardening checklist (for production)
- Put the app behind Nginx with HTTPS (Let's Encrypt).
- Replace bearer-style token with signed, expiring tokens (e.g., itsdangerous/JWT) and bind to user/device.
- Require login + OTP to reveal the file (QR only as a pointer, not the authorizer).
- Encrypt files at rest; restrict MIME types; scan for malware.
- Set `SEND_FILE_MAX_AGE_DEFAULT` and headers to avoid caching sensitive files.
- Move file serving to a private store (S3/GCS) with short-lived signed URLs.
- Enable CSRF protection and add rate limiting (Flask-Limiter).
- Log access; rotate tokens; allow revocation.
```