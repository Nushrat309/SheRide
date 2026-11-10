"""SheRide — a women-only ride-sharing demo.

Run:  python app.py   then open http://127.0.0.1:5000
Demo accounts (password: demo123): ayesha@demo.com, nadia@demo.com, sara@demo.com
"""
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

from shebot import shebot_reply

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("SHERIDE_DB", os.path.join(BASE_DIR, "sheride.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SHERIDE_SECRET", "dev-only-change-me")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^(\+?88)?01[3-9]\d{8}$")  # Bangladeshi mobile numbers
ACTIVE_BOOKING = ("pending", "accepted")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,
  email         TEXT NOT NULL UNIQUE,
  phone         TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  gender        TEXT NOT NULL CHECK (gender = 'woman'),   -- women-only, enforced by the DB too
  nid           TEXT,
  verified      INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rides (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  driver_id   INTEGER NOT NULL REFERENCES users(id),
  origin      TEXT NOT NULL,
  destination TEXT NOT NULL,
  depart_at   TEXT NOT NULL,                       -- 'YYYY-MM-DDTHH:MM'
  seats_total INTEGER NOT NULL CHECK (seats_total BETWEEN 1 AND 6),
  fare        INTEGER NOT NULL CHECK (fare >= 0),  -- per seat, in BDT
  vehicle     TEXT NOT NULL,
  notes       TEXT NOT NULL DEFAULT '',
  status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'cancelled')),
  created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bookings (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  ride_id      INTEGER NOT NULL REFERENCES rides(id),
  passenger_id INTEGER NOT NULL REFERENCES users(id),
  seats        INTEGER NOT NULL DEFAULT 1,
  status       TEXT NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled')),
  created_at   TEXT NOT NULL,
  UNIQUE (ride_id, passenger_id)
);
CREATE TABLE IF NOT EXISTS messages (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  booking_id INTEGER NOT NULL REFERENCES bookings(id),
  sender_id  INTEGER REFERENCES users(id),   -- NULL = SheBot system message
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_booking ON messages (booking_id, id);
"""

RIDE_SELECT = """
SELECT r.*, u.name AS driver_name,
  r.seats_total - COALESCE((SELECT SUM(b.seats) FROM bookings b
                            WHERE b.ride_id = r.id AND b.status = 'accepted'), 0) AS seats_left,
  (SELECT COUNT(*) FROM bookings b WHERE b.ride_id = r.id AND b.status = 'pending') AS pending_count
FROM rides r JOIN users u ON u.id = r.driver_id
"""


# ---------------------------------------------------------------- database

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def now_iso(seconds=False):
    return datetime.now().isoformat(timespec="seconds" if seconds else "minutes")


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        seed(db)
    db.commit()


def seed(db):
    """Demo data: three verified women, a few rides, one accepted booking with a chat."""
    created = now_iso(seconds=True)
    pw = generate_password_hash("demo123")
    for name, email, phone, nid in [
        ("Ayesha Rahman", "ayesha@demo.com", "01711000001", "1990123456"),
        ("Nadia Islam", "nadia@demo.com", "01811000002", "1992123456"),
        ("Sara Ahmed", "sara@demo.com", "01911000003", "1995123456"),
    ]:
        db.execute(
            "INSERT INTO users (name, email, phone, password_hash, gender, nid, verified, created_at)"
            " VALUES (?, ?, ?, ?, 'woman', ?, 1, ?)",
            (name, email, phone, pw, nid, created),
        )

    day = datetime.now().replace(second=0, microsecond=0) + timedelta(days=1)

    def at(days, hour, minute=0):
        return (day + timedelta(days=days)).replace(hour=hour, minute=minute).isoformat(timespec="minutes")

    rides = [
        (1, "Dhanmondi 27", "Gulshan 1", at(0, 8, 30), 3, 150, "Toyota Axio (white)",
         "Daily office commute, AC car. Can pick up along Satmasjid Road."),
        (1, "Gulshan 1", "Dhanmondi 27", at(0, 18, 0), 3, 150, "Toyota Axio (white)",
         "Return trip. Leaving right after office."),
        (2, "Mirpur 10", "Motijheel", at(0, 9, 0), 2, 120, "Honda Grace (silver)",
         "Going via Agargaon. Quiet ride, no smoking."),
        (2, "Uttara Sector 7", "Banani", at(1, 8, 0), 3, 180, "Honda Grace (silver)", ""),
        (3, "Rajshahi (RUET Gate)", "Dhaka (Gabtoli)", at(2, 7, 0), 3, 900, "Toyota Noah (grey)",
         "Intercity trip. One break at the Jamuna Bridge food court."),
    ]
    for r in rides:
        db.execute(
            "INSERT INTO rides (driver_id, origin, destination, depart_at, seats_total, fare,"
            " vehicle, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*r, created),
        )

    # Sara has an accepted seat on Ayesha's morning ride, with a short conversation.
    db.execute(
        "INSERT INTO bookings (ride_id, passenger_id, seats, status, created_at)"
        " VALUES (1, 3, 1, 'accepted', ?)", (created,))
    for sender, body in [
        (None, "Sara Ahmed requested 1 seat. Use this chat to agree on the exact pickup spot."),
        (None, "Ayesha Rahman accepted the request. Have a safe trip! 🌸"),
        (3, "Hi Ayesha! Can you pick me up in front of Shimanto Square?"),
        (1, "Sure! I'll be there at 8:30 sharp. White Axio, I'll text when I'm close."),
        (3, "Perfect, thank you 😊"),
    ]:
        db.execute("INSERT INTO messages (booking_id, sender_id, body, created_at) VALUES (1, ?, ?, ?)",
                   (sender, body, created))


def bot_message(booking_id, body):
    get_db().execute(
        "INSERT INTO messages (booking_id, sender_id, body, created_at) VALUES (?, NULL, ?, ?)",
        (booking_id, body, now_iso(seconds=True)))


# ---------------------------------------------------------------- auth, CSRF, helpers

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


@app.before_request
def load_user_and_check_csrf():
    uid = session.get("user_id")
    g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone() if uid else None
    if request.method == "POST":
        token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not token or token != session.get("csrf"):
            abort(400, "Invalid or missing CSRF token. Reload the page and try again.")


@app.context_processor
def inject_globals():
    return {
        "user": g.get("user"),
        "csrf_token": csrf_token,
        "csrf_field": lambda: Markup(f'<input type="hidden" name="csrf_token" value="{csrf_token()}">'),
    }


@app.template_filter("dt")
def format_dt(value):
    try:
        return datetime.fromisoformat(value).strftime("%a, %d %b · %I:%M %p")
    except (TypeError, ValueError):
        return value


def _is_api():
    return request.path.startswith("/api/")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if _is_api():
                return jsonify(error="Please log in."), 401
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


def verified_required(view):
    """Only logged-in, identity-verified women can offer, book or chat."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user["verified"]:
            if _is_api():
                return jsonify(error="Please verify your identity first."), 403
            flash("Please verify your identity before offering or booking rides.", "error")
            return redirect(url_for("verify", next=request.full_path))
        return view(*args, **kwargs)
    return login_required(wrapped)


def safe_next(default):
    target = request.values.get("next", "")
    parsed = urlparse(target)
    if target.startswith("/") and not target.startswith("//") and not parsed.netloc:
        return target
    return default


def get_ride_or_404(ride_id):
    ride = get_db().execute(RIDE_SELECT + " WHERE r.id = ?", (ride_id,)).fetchone()
    if ride is None:
        abort(404)
    return ride


def get_chat_booking(booking_id):
    """Load a booking with its ride; only the ride sharer and that passenger may access it."""
    b = get_db().execute("""
        SELECT b.*, r.driver_id, r.origin, r.destination, r.depart_at, r.status AS ride_status,
               d.name AS driver_name, p.name AS passenger_name
        FROM bookings b
        JOIN rides r ON r.id = b.ride_id
        JOIN users d ON d.id = r.driver_id
        JOIN users p ON p.id = b.passenger_id
        WHERE b.id = ?""", (booking_id,)).fetchone()
    if b is None:
        abort(404)
    if g.user["id"] not in (b["driver_id"], b["passenger_id"]):
        abort(403)
    return b


def chat_is_open(b):
    return b["status"] in ACTIVE_BOOKING and b["ride_status"] == "open"


# ---------------------------------------------------------------- pages

@app.route("/")
def index():
    rides = get_db().execute(
        RIDE_SELECT + " WHERE r.status = 'open' AND r.depart_at >= ? ORDER BY r.depart_at LIMIT 6",
        (now_iso(),)).fetchall()
    return render_template("index.html", rides=rides)


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        f = request.form
        name, email = f.get("name", "").strip(), f.get("email", "").strip().lower()
        phone, password = f.get("phone", "").strip().replace(" ", ""), f.get("password", "")
        errors = []
        if f.get("gender") != "woman":
            errors.append("SheRide is a women-only community, so only women can create an account.")
        if not name:
            errors.append("Please enter your name.")
        if not EMAIL_RE.match(email):
            errors.append("Please enter a valid email address.")
        if not PHONE_RE.match(phone):
            errors.append("Please enter a valid Bangladeshi mobile number (e.g. 01712345678).")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if not f.get("agree"):
            errors.append("Please accept the community guidelines.")
        db = get_db()
        if not errors and db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            errors.append("An account with this email already exists.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", form=f)

        cur = db.execute(
            "INSERT INTO users (name, email, phone, password_hash, gender, created_at)"
            " VALUES (?, ?, ?, ?, 'woman', ?)",
            (name, email, phone, generate_password_hash(password), now_iso(seconds=True)))
        db.commit()
        session.clear()
        session["user_id"] = cur.lastrowid
        flash(f"Welcome to SheRide, {name}! One last step: verify your identity.", "success")
        return redirect(url_for("verify"))
    return render_template("register.html", form={})


@app.route("/verify", methods=["GET", "POST"])
@login_required
def verify():
    if g.user["verified"]:
        return redirect(safe_next(url_for("dashboard")))
    if request.method == "POST":
        nid = re.sub(r"\D", "", request.form.get("nid", ""))
        if len(nid) not in (10, 13, 17):
            flash("A Bangladeshi NID number has 10, 13 or 17 digits.", "error")
        elif not request.form.get("selfie"):
            flash("Please confirm the selfie check.", "error")
        else:
            # DEMO ONLY: a real app would send the NID + a live selfie to a KYC provider
            # and keep the account unverified until the provider approves it.
            db = get_db()
            db.execute("UPDATE users SET nid = ?, verified = 1 WHERE id = ?", (nid, g.user["id"]))
            db.commit()
            flash("You're verified ✓ (demo mode: approved automatically).", "success")
            return redirect(safe_next(url_for("rides")))
    return render_template("verify.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['name'].split()[0]}!", "success")
            return redirect(safe_next(url_for("dashboard")))
        flash("Incorrect email or password.", "error")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/rides")
def rides():
    q_from, q_to = request.args.get("from", "").strip(), request.args.get("to", "").strip()
    q_date = request.args.get("date", "").strip()
    sql, params = RIDE_SELECT + " WHERE r.status = 'open' AND r.depart_at >= ?", [now_iso()]
    if q_from:
        sql += " AND r.origin LIKE ?"
        params.append(f"%{q_from}%")
    if q_to:
        sql += " AND r.destination LIKE ?"
        params.append(f"%{q_to}%")
    if q_date:
        sql += " AND substr(r.depart_at, 1, 10) = ?"
        params.append(q_date)
    results = get_db().execute(sql + " ORDER BY r.depart_at", params).fetchall()
    return render_template("rides.html", rides=results, q={"from": q_from, "to": q_to, "date": q_date})


@app.route("/rides/new", methods=["GET", "POST"])
@verified_required
def new_ride():
    if request.method == "POST":
        f = request.form
        origin, destination = f.get("origin", "").strip(), f.get("destination", "").strip()
        depart_at, vehicle = f.get("depart_at", "").strip(), f.get("vehicle", "").strip()
        notes = f.get("notes", "").strip()[:500]
        errors = []
        try:
            seats, fare = int(f.get("seats", "")), int(f.get("fare", ""))
        except ValueError:
            seats = fare = -1
        if not origin or not destination:
            errors.append("Please enter where you're leaving from and going to.")
        try:
            if datetime.fromisoformat(depart_at) <= datetime.now():
                errors.append("Departure time must be in the future.")
        except ValueError:
            errors.append("Please choose a departure date and time.")
        if not 1 <= seats <= 6:
            errors.append("Seats must be between 1 and 6.")
        if not 0 <= fare <= 10000:
            errors.append("Fare per seat must be between ৳0 and ৳10,000.")
        if not vehicle:
            errors.append("Please describe your vehicle (model and colour).")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("ride_new.html", form=f)

        db = get_db()
        cur = db.execute(
            "INSERT INTO rides (driver_id, origin, destination, depart_at, seats_total, fare, vehicle,"
            " notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (g.user["id"], origin, destination, depart_at, seats, fare, vehicle, notes,
             now_iso(seconds=True)))
        db.commit()
        flash("Your ride is live! You'll see seat requests on the ride page.", "success")
        return redirect(url_for("ride_detail", ride_id=cur.lastrowid))
    return render_template("ride_new.html", form={})


@app.route("/rides/<int:ride_id>")
def ride_detail(ride_id):
    ride = get_ride_or_404(ride_id)
    db = get_db()
    is_driver = bool(g.user) and ride["driver_id"] == g.user["id"]
    bookings = my_booking = None
    if is_driver:
        bookings = db.execute(
            "SELECT b.*, u.name AS passenger_name FROM bookings b JOIN users u ON u.id = b.passenger_id"
            " WHERE b.ride_id = ? ORDER BY b.created_at", (ride_id,)).fetchall()
    elif g.user:
        my_booking = db.execute("SELECT * FROM bookings WHERE ride_id = ? AND passenger_id = ?",
                                (ride_id, g.user["id"])).fetchone()
    return render_template("ride_detail.html", ride=ride, is_driver=is_driver, bookings=bookings,
                           my_booking=my_booking, ride_past=ride["depart_at"] < now_iso())


@app.post("/rides/<int:ride_id>/book")
@verified_required
def book_ride(ride_id):
    ride = get_ride_or_404(ride_id)
    back = redirect(url_for("ride_detail", ride_id=ride_id))
    if ride["driver_id"] == g.user["id"]:
        flash("You can't book a seat on your own ride.", "error")
        return back
    if ride["status"] != "open" or ride["depart_at"] < now_iso():
        flash("This ride is no longer accepting requests.", "error")
        return back
    seats = request.form.get("seats", 1, type=int) or 1
    if not 1 <= seats <= ride["seats_left"]:
        flash("Not enough seats left on this ride.", "error")
        return back

    db = get_db()
    existing = db.execute("SELECT * FROM bookings WHERE ride_id = ? AND passenger_id = ?",
                          (ride_id, g.user["id"])).fetchone()
    if existing and existing["status"] in ACTIVE_BOOKING:
        return redirect(url_for("chat", booking_id=existing["id"]))
    if existing:  # re-requesting after a decline/cancel
        db.execute("UPDATE bookings SET status = 'pending', seats = ?, created_at = ? WHERE id = ?",
                   (seats, now_iso(seconds=True), existing["id"]))
        booking_id = existing["id"]
    else:
        booking_id = db.execute(
            "INSERT INTO bookings (ride_id, passenger_id, seats, created_at) VALUES (?, ?, ?, ?)",
            (ride_id, g.user["id"], seats, now_iso(seconds=True))).lastrowid
    bot_message(booking_id,
                f"{g.user['name']} requested {seats} seat{'s' if seats > 1 else ''}. "
                f"{ride['driver_name']}, please accept or decline from the ride page. "
                "Use this chat to agree on the exact pickup spot.")
    db.commit()
    flash("Request sent! Say hi to your ride sharer while you wait.", "success")
    return redirect(url_for("chat", booking_id=booking_id))


@app.post("/bookings/<int:booking_id>/<action>")
@verified_required
def booking_action(booking_id, action):
    b = get_chat_booking(booking_id)
    db = get_db()
    is_driver = b["driver_id"] == g.user["id"]

    if action in ("accept", "decline"):
        if not is_driver:
            abort(403)
        if b["status"] != "pending":
            flash("This request has already been handled.", "error")
        elif action == "accept" and b["seats"] > get_ride_or_404(b["ride_id"])["seats_left"]:
            flash("Not enough seats left to accept this request.", "error")
        else:
            new_status = "accepted" if action == "accept" else "declined"
            db.execute("UPDATE bookings SET status = ? WHERE id = ?", (new_status, booking_id))
            bot_message(booking_id, f"{b['driver_name']} accepted the request. Have a safe trip! 🌸"
                        if action == "accept" else
                        f"{b['driver_name']} declined the request. You can look for another ride.")
            db.commit()
            flash(f"Request {new_status}.", "success")
    elif action == "cancel":
        if b["passenger_id"] != g.user["id"]:
            abort(403)
        if b["status"] in ACTIVE_BOOKING:
            db.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
            bot_message(booking_id, f"{b['passenger_name']} cancelled this booking.")
            db.commit()
            flash("Your booking was cancelled.", "success")
    else:
        abort(404)
    return redirect(safe_next(url_for("ride_detail", ride_id=b["ride_id"])))


@app.post("/rides/<int:ride_id>/cancel")
@verified_required
def cancel_ride(ride_id):
    ride = get_ride_or_404(ride_id)
    if ride["driver_id"] != g.user["id"]:
        abort(403)
    db = get_db()
    db.execute("UPDATE rides SET status = 'cancelled' WHERE id = ?", (ride_id,))
    active = db.execute("SELECT id FROM bookings WHERE ride_id = ? AND status IN ('pending', 'accepted')",
                        (ride_id,)).fetchall()
    for row in active:
        db.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (row["id"],))
        bot_message(row["id"], f"{ride['driver_name']} cancelled this ride. Sorry! Please search for another ride.")
    db.commit()
    flash("Ride cancelled. Your passengers have been notified.", "success")
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    offered = db.execute(RIDE_SELECT + " WHERE r.driver_id = ? ORDER BY r.depart_at DESC",
                         (g.user["id"],)).fetchall()
    booked = db.execute("""
        SELECT b.*, r.origin, r.destination, r.depart_at, r.fare, r.status AS ride_status,
               u.name AS driver_name
        FROM bookings b JOIN rides r ON r.id = b.ride_id JOIN users u ON u.id = r.driver_id
        WHERE b.passenger_id = ? ORDER BY r.depart_at DESC""", (g.user["id"],)).fetchall()
    return render_template("dashboard.html", offered=offered, booked=booked)


# ---------------------------------------------------------------- chat between ride sharer and passenger

DRIVER_QUICK = ["I'm on my way 🚗", "I've arrived at the pickup point.",
                "Please share your exact pickup spot.", "Running 5 minutes late, sorry!"]
PASSENGER_QUICK = ["I'm at the pickup point.", "Running 5 minutes late, sorry!",
                   "What's your car number?", "Thank you for the ride! 🌸"]


@app.route("/chat/<int:booking_id>")
@verified_required
def chat(booking_id):
    b = get_chat_booking(booking_id)
    is_driver = b["driver_id"] == g.user["id"]
    return render_template(
        "chat.html", b=b, is_driver=is_driver, chat_open=chat_is_open(b),
        other_name=b["passenger_name"] if is_driver else b["driver_name"],
        quick_replies=DRIVER_QUICK if is_driver else PASSENGER_QUICK)


def serialize_message(m):
    return {
        "id": m["id"],
        "sender_id": m["sender_id"],
        "sender_name": m["sender_name"] or "SheBot",
        "body": m["body"],
        "time": datetime.fromisoformat(m["created_at"]).strftime("%d %b, %I:%M %p"),
    }


MESSAGE_SELECT = """SELECT m.*, u.name AS sender_name FROM messages m
                    LEFT JOIN users u ON u.id = m.sender_id"""


@app.get("/api/chat/<int:booking_id>/messages")
@verified_required
def api_messages(booking_id):
    b = get_chat_booking(booking_id)
    after = request.args.get("after", 0, type=int)
    rows = get_db().execute(MESSAGE_SELECT + " WHERE m.booking_id = ? AND m.id > ? ORDER BY m.id LIMIT 200",
                            (booking_id, after)).fetchall()
    return jsonify(messages=[serialize_message(m) for m in rows],
                   status=b["status"], chat_open=chat_is_open(b))


@app.post("/api/chat/<int:booking_id>/messages")
@verified_required
def api_send_message(booking_id):
    b = get_chat_booking(booking_id)
    if not chat_is_open(b):
        return jsonify(error="This chat is closed."), 409
    body = ((request.get_json(silent=True) or {}).get("body") or "").strip()
    if not body:
        return jsonify(error="Message is empty."), 400
    if len(body) > 1000:
        return jsonify(error="Message is too long (max 1000 characters)."), 400
    db = get_db()
    msg_id = db.execute("INSERT INTO messages (booking_id, sender_id, body, created_at) VALUES (?, ?, ?, ?)",
                        (booking_id, g.user["id"], body, now_iso(seconds=True))).lastrowid
    db.commit()
    row = db.execute(MESSAGE_SELECT + " WHERE m.id = ?", (msg_id,)).fetchone()
    return jsonify(message=serialize_message(row)), 201


# ---------------------------------------------------------------- SheBot help assistant

@app.post("/api/shebot")
def api_shebot():
    text = ((request.get_json(silent=True) or {}).get("message") or "").strip()[:500]
    return jsonify(shebot_reply(text, logged_in=g.user is not None))


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
