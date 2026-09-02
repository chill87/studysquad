"""
StudySquad - a small Flask app for a group of students to:
  1. Keep a shared calendar of homework assignments (anyone can add/edit)
  2. Post their answers under each assignment to compare with each other
  3. Do a daily "check-in" by uploading a photo of their finished homework,
     so everyone can see who has (and hasn't) done it that day.

This is intentionally simple and dependency-light (Flask + SQLite) so it's
easy to run on a laptop, a Raspberry Pi, or a free hosting service.

Run it with:
    pip install -r requirements.txt
    python app.py

Then open http://localhost:5000 in your browser. Everyone on the same
wifi/network can use http://<your-computer-ip>:5000 to reach it too.

NOTE ON HONESTY: nothing stops someone from uploading an old/fake photo.
This app is a lightweight social-accountability tool, not a proctoring
system -- treat the check-in board as a "nudge", not a guarantee.
"""

import os
import sqlite3
from datetime import date, datetime

from flask import (
    Flask, g, render_template, request, redirect,
    url_for, session, send_from_directory, flash
)
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "studysquad.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp", "heic"}

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = "change-this-to-something-random"  # needed for sessions
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB upload cap


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            due_date TEXT NOT NULL,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            created_by TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            body TEXT,
            photo TEXT,
            created_at TEXT,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author TEXT NOT NULL,
            checkin_date TEXT NOT NULL,
            photo TEXT NOT NULL,
            note TEXT,
            created_at TEXT,
            UNIQUE(author, checkin_date)
        );
        """
    )
    db.commit()
    db.close()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def save_photo(file_storage, prefix):
    """Save an uploaded photo with a unique, safe filename. Returns the
    stored filename, or None if no valid file was given."""
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        flash("That file type isn't supported. Use a photo (jpg/png/etc).")
        return None
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    fname = secure_filename(f"{prefix}_{stamp}.{ext}")
    file_storage.save(os.path.join(UPLOAD_DIR, fname))
    return fname


# --------------------------------------------------------------------------
# Auth-lite: everyone just picks a display name, no password.
# Good enough for a small friend group; don't use this for anything
# sensitive.
# --------------------------------------------------------------------------

@app.before_request
def require_name():
    open_endpoints = {"login", "static", "uploaded_file"}
    if request.endpoint in open_endpoints:
        return
    if "username" not in session:
        return redirect(url_for("login", next=request.path))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("username", "").strip()
        if not name:
            flash("Type a name so people know who's who.")
            return redirect(url_for("login"))
        session["username"] = name[:30]
        return redirect(request.args.get("next") or url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# Dashboard: today's assignments + who has checked in today
# --------------------------------------------------------------------------

@app.route("/")
def dashboard():
    db = get_db()
    today = date.today().isoformat()

    due_today = db.execute(
        "SELECT * FROM assignments WHERE due_date = ? ORDER BY subject",
        (today,),
    ).fetchall()

    upcoming = db.execute(
        "SELECT * FROM assignments WHERE due_date > ? "
        "ORDER BY due_date LIMIT 5",
        (today,),
    ).fetchall()

    checkins_today = db.execute(
        "SELECT * FROM checkins WHERE checkin_date = ? ORDER BY created_at",
        (today,),
    ).fetchall()
    checked_in_names = {c["author"] for c in checkins_today}

    my_checkin = db.execute(
        "SELECT * FROM checkins WHERE author = ? AND checkin_date = ?",
        (session["username"], today),
    ).fetchone()

    return render_template(
        "dashboard.html",
        today=today,
        due_today=due_today,
        upcoming=upcoming,
        checkins_today=checkins_today,
        checked_in_names=checked_in_names,
        my_checkin=my_checkin,
    )


# --------------------------------------------------------------------------
# Daily check-in: upload a photo of finished homework
# --------------------------------------------------------------------------

@app.route("/checkin", methods=["GET", "POST"])
def checkin():
    db = get_db()
    today = date.today().isoformat()

    if request.method == "POST":
        photo = save_photo(request.files.get("photo"), session["username"])
        if not photo:
            flash("Please attach a photo of your finished homework.")
            return redirect(url_for("checkin"))
        note = request.form.get("note", "").strip()
        db.execute(
            "INSERT INTO checkins (author, checkin_date, photo, note, created_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(author, checkin_date) "
            "DO UPDATE SET photo=excluded.photo, note=excluded.note, "
            "created_at=excluded.created_at",
            (session["username"], today, photo, note, datetime.now().isoformat()),
        )
        db.commit()
        flash("Checked in! Nice work today.")
        return redirect(url_for("dashboard"))

    return render_template("checkin.html", today=today)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# --------------------------------------------------------------------------
# Shared calendar: anyone can add / edit / delete assignments
# --------------------------------------------------------------------------

@app.route("/calendar")
def calendar_view():
    db = get_db()
    assignments = db.execute(
        "SELECT * FROM assignments ORDER BY due_date, subject"
    ).fetchall()
    # group by due_date for a simple calendar-style listing
    grouped = {}
    for a in assignments:
        grouped.setdefault(a["due_date"], []).append(a)
    return render_template("calendar.html", grouped=grouped)


@app.route("/calendar/new", methods=["GET", "POST"])
def new_assignment():
    if request.method == "POST":
        db = get_db()
        db.execute(
            "INSERT INTO assignments "
            "(due_date, subject, title, description, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                request.form["due_date"],
                request.form["subject"].strip(),
                request.form["title"].strip(),
                request.form.get("description", "").strip(),
                session["username"],
                datetime.now().isoformat(),
            ),
        )
        db.commit()
        flash("Assignment added to the calendar.")
        return redirect(url_for("calendar_view"))
    return render_template("assignment_form.html", assignment=None)


@app.route("/calendar/<int:assignment_id>/edit", methods=["GET", "POST"])
def edit_assignment(assignment_id):
    db = get_db()
    assignment = db.execute(
        "SELECT * FROM assignments WHERE id = ?", (assignment_id,)
    ).fetchone()
    if assignment is None:
        flash("That assignment doesn't exist (maybe it was deleted).")
        return redirect(url_for("calendar_view"))

    if request.method == "POST":
        db.execute(
            "UPDATE assignments SET due_date=?, subject=?, title=?, "
            "description=? WHERE id=?",
            (
                request.form["due_date"],
                request.form["subject"].strip(),
                request.form["title"].strip(),
                request.form.get("description", "").strip(),
                assignment_id,
            ),
        )
        db.commit()
        flash("Assignment updated.")
        return redirect(url_for("calendar_view"))

    return render_template("assignment_form.html", assignment=assignment)


@app.route("/calendar/<int:assignment_id>/delete", methods=["POST"])
def delete_assignment(assignment_id):
    db = get_db()
    db.execute("DELETE FROM answers WHERE assignment_id = ?", (assignment_id,))
    db.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
    db.commit()
    flash("Assignment deleted.")
    return redirect(url_for("calendar_view"))


# --------------------------------------------------------------------------
# Assignment detail: post & compare answers
# --------------------------------------------------------------------------

@app.route("/assignment/<int:assignment_id>", methods=["GET", "POST"])
def assignment_detail(assignment_id):
    db = get_db()
    assignment = db.execute(
        "SELECT * FROM assignments WHERE id = ?", (assignment_id,)
    ).fetchone()
    if assignment is None:
        flash("That assignment doesn't exist (maybe it was deleted).")
        return redirect(url_for("calendar_view"))

    if request.method == "POST":
        body = request.form.get("body", "").strip()
        photo = save_photo(request.files.get("photo"), f"ans{assignment_id}_{session['username']}")
        if not body and not photo:
            flash("Add some text or a photo of your answer before posting.")
        else:
            db.execute(
                "INSERT INTO answers (assignment_id, author, body, photo, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (assignment_id, session["username"], body, photo, datetime.now().isoformat()),
            )
            db.commit()
        return redirect(url_for("assignment_detail", assignment_id=assignment_id))

    answers = db.execute(
        "SELECT * FROM answers WHERE assignment_id = ? ORDER BY created_at",
        (assignment_id,),
    ).fetchall()

    return render_template("assignment_detail.html", assignment=assignment, answers=answers)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
