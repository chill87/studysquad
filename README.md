# StudySquad

A tiny Flask web app for a group of students to:

- Keep a **shared calendar** of homework — anyone can add, edit, or delete assignments.
- Post **answers/work under each assignment** so you can compare with each other.
- Do a **daily photo check-in** — upload a photo of your finished homework so the
  group can see who's done for the day.

## 1. Setup

You need Python 3.9+ installed. Then, in this folder:

```bash
pip install -r requirements.txt
python app.py
```

The first run creates a local database file (`studysquad.db`) automatically.

## 2. Open it

- On your own computer: http://localhost:5000
- For friends on the same wifi: find your computer's local IP (e.g. `192.168.1.23`)
  and have them go to `http://192.168.1.23:5000`
- To make it reachable from anywhere (e.g. so people can use it from home too),
  deploy it to a free host like Render, PythonAnywhere, or Railway — search
  "deploy Flask app free hosting" for an up to date guide, since these
  services change their instructions often.

## 3. How it works

- **No passwords** — everyone just types a display name. This keeps it simple
  for a small trusted group, but means anyone with the link can post as anyone.
  Only use this with people you actually trust.
- **Calendar**: `/calendar` — fully shared and editable by everyone. Good for
  agreeing on due dates as a class/group.
- **Check-in**: `/checkin` — one photo per person per day. The dashboard shows
  everyone's check-in as a little avatar so you can see who's done.
- **Assignment pages**: click any assignment to see everyone's posted answers
  side by side, and post your own (text and/or photo).
- Photos are stored in `static/uploads/` and the data lives in `studysquad.db`
  (a SQLite file) — back that file up if you care about the history.

## 4. A couple of honest notes

- This is a lightweight accountability/study tool, not a security system —
  it can't verify a check-in photo is genuine or from today.
- Comparing answers is great for checking your work and learning from each
  other; it's still worth doing the thinking yourselves before you look,
  since that's what actually helps on tests.
- If you want real accounts/passwords, a bigger group, or hosting outside
  your home network, you'll want to add proper authentication (e.g.
  Flask-Login) before opening it up beyond people you trust.

## 5. Customizing

Everything is plain Flask + SQLite + Jinja templates + Bootstrap (via CDN),
so it's easy to tweak:

- `app.py` — routes and database logic
- `templates/` — the HTML pages
- `static/uploads/` — where photos get saved
