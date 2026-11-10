# 🌸 SheRide: women-only ride sharing (demo)

SheRide connects verified women who are driving somewhere with women who need a seat going the same way.
Only women can join, and every ride sharer and passenger can talk in a private in-app chat.

## Run it

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The database (`sheride.db`) is created and filled with demo data on first run.
Delete the file to reset it.

**Demo accounts** (password `demo123`):

| Email | Role in demo data |
|---|---|
| ayesha@demo.com | Ride sharer (Dhanmondi ⇄ Gulshan), already chatting with Sara |
| nadia@demo.com | Ride sharer (Mirpur → Motijheel, Uttara → Banani) |
| sara@demo.com | Passenger on Ayesha's ride, ride sharer for Rajshahi → Dhaka |

**Try the chat:** open two browser windows (one normal, one private/incognito), log in as two
different users, request a seat in one window and reply from the other. Messages appear within about 2 seconds.

## Features

- **Women-only accounts:** signup rejects anyone who isn't a woman, and the database itself
  enforces it (`CHECK (gender = 'woman')`).
- **Identity verification gate:** members must verify (National ID + selfie consent) before they can offer,
  book or chat. *Demo: approved automatically.*
- **Offer a ride:** route, departure time, seats, fare per seat (৳), vehicle and notes.
- **Find & book:** search by origin, destination and date, then request seats. The ride sharer accepts or declines.
- **Ride sharer ⇄ passenger chat:** a private chat for each booking, with quick replies
  ("I'm at the pickup point", "Running 5 minutes late"…) and automatic SheBot status updates
  (requested / accepted / declined / cancelled). Phone numbers are never shown.
- **SheBot help assistant:** a floating 💬 button on every page that answers questions about booking, offering,
  chat, fares, verification, safety and emergencies (999 / 109).
- **My trips** dashboard, ride cancellation (passengers are notified), CSRF protection and hashed passwords.

## Project structure

```
app.py            Flask app: routes, database schema, demo seed data, chat API
shebot.py         SheBot rule-based answers (replace with an LLM later; same return shape)
templates/        Jinja pages (home, rides, ride detail, offer, chat, dashboard, auth)
static/style.css  Styles
static/chat.js    Chat between ride sharer and passenger (polls every 2s)
static/shebot.js  SheBot widget
```

## Before a real launch

This is a demo. Things to replace or add:

1. **Real verification:** integrate a KYC provider (NID + live selfie face match) and keep accounts
   *pending* until approved. Self-declared gender alone is not enough to keep a platform women-only.
2. **Real-time chat:** switch polling to WebSockets (e.g. Flask-SocketIO), add push notifications and
   chat moderation/reporting.
3. **Safety:** SOS button with live location sharing to trusted contacts, ratings & reviews, report/block.
4. **Maps:** pickup points and route matching (Google Maps / OpenStreetMap).
5. **Payments:** bKash / Nagad integration.
6. **Production setup:** set `SHERIDE_SECRET` to a long random value, use PostgreSQL, run behind
   gunicorn/waitress with HTTPS, and turn off `debug`.
7. **Smarter SheBot:** swap `shebot_reply()` for an LLM call, keeping the rule-based emergency
   answer as a fallback.
