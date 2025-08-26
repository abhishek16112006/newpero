#!/usr/bin/env python3
import os
import sqlite3
import secrets
import datetime
from flask import Flask, request, redirect, url_for, send_from_directory, render_template, flash, abort
from werkzeug.utils import secure_filename
import qrcode

# ------------------ Config ------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
QRCODE_FOLDER = os.path.join(BASE_DIR, "qrcodes")
DB_PATH = os.path.join(BASE_DIR, "app.db")

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB per file

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QRCODE_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# ------------------ DB helpers ------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE
            );
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ------------------ Routes ------------------
@app.route("/")
def index():
    with get_db() as db:
        users = db.execute("SELECT id, name, email FROM users ORDER BY id DESC").fetchall()
    return render_template("index.html", users=users)

@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip() or None
    if not name:
        flash("Name is required.", "error")
        return redirect(url_for("index"))
    try:
        with get_db() as db:
            cur = db.execute("INSERT INTO users(name, email) VALUES (?, ?)", (name, email))
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        flash("Email already exists. Use a different one.", "error")
        return redirect(url_for("index"))
    flash("User registered. Now upload a document for them.", "success")
    return redirect(url_for("upload_for_user", user_id=user_id))

@app.route("/user/<int:user_id>/upload", methods=["GET", "POST"])
def upload_for_user(user_id):
    with get_db() as db:
        user = db.execute("SELECT id, name, email FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        abort(404)
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part in the form.", "error")
            return redirect(request.url)
        f = request.files["file"]
        if f.filename == "":
            flash("No file selected.", "error")
            return redirect(request.url)
        if not allowed_file(f.filename):
            flash("File type not allowed. Allowed: pdf, jpg, jpeg, png, webp", "error")
            return redirect(request.url)
        safe_name = secure_filename(f.filename)
        # Make filename unique
        unique_name = f"{user_id}_{secrets.token_urlsafe(8)}_{safe_name}"
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        f.save(save_path)

        # Create token and DB record
        token = secrets.token_urlsafe(16)
        created_at = datetime.datetime.utcnow().isoformat()
        with get_db() as db:
            db.execute(
                "INSERT INTO documents(user_id, filename, original_name, token, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, unique_name, safe_name, token, created_at),
            )
        # Generate QR code pointing to the token URL
        token_url = url_for("doc_by_token", token=token, _external=True)
        qr_img = qrcode.make(token_url)
        qr_path = os.path.join(QRCODE_FOLDER, f"{token}.png")
        qr_img.save(qr_path)

        flash("Document uploaded and QR code generated.", "success")
        return redirect(url_for("show_qr", token=token))

    # GET
    with get_db() as db:
        docs = db.execute("SELECT * FROM documents WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
    return render_template("upload.html", user=user, docs=docs)

@app.route("/qr/<token>")
def show_qr(token):
    with get_db() as db:
        doc = db.execute("SELECT d.*, u.name FROM documents d JOIN users u ON d.user_id=u.id WHERE token=?", (token,)).fetchone()
    if not doc:
        abort(404)
    qr_file = f"/qrcodes/{token}.png"
    link = url_for("doc_by_token", token=token, _external=True)
    return render_template("my_qr.html", doc=doc, qr_file=qr_file, link=link)

@app.route("/qrcodes/<path:filename>")
def qrcodes(filename):
    return send_from_directory(QRCODE_FOLDER, filename)

@app.route("/uploads/<path:filename>")
def uploads(filename):
    # For demo only. In production, protect these routes!
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=False)

@app.route("/d/<token>")
def doc_by_token(token):
    with get_db() as db:
        doc = db.execute("SELECT * FROM documents WHERE token=?", (token,)).fetchone()
    if not doc:
        abort(404)
    return render_template("document.html", doc=doc)

@app.errorhandler(413)
def file_too_large(e):
    return render_template("message.html", title="File too large", message="The uploaded file exceeds 10 MB."), 413

@app.errorhandler(404)
def not_found(e):
    return render_template("message.html", title="Not found", message="The requested item was not found."), 404

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
