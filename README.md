# Campus Cleanliness Monitoring System

A Flask-based mini project for reporting campus cleanliness issues, tracking complaint progress, managing cleaning schedules, and generating reports.

## Features

- Complaint reporting with optional image upload
- Complaint tracking by Complaint ID
- Admin dashboard with charts and reminder cards
- Complaint management with search, filters, pagination, update, and delete
- Cleaning schedule management for daily, weekly, and monthly tasks
- Reports system with daily, weekly, and monthly summaries
- CSV export and printable report view
- Responsive Bootstrap 5 UI with sidebar, navbar, toast notifications, and loading spinner

## Tech Stack

- Python
- Flask
- SQLite
- HTML, CSS, JavaScript
- Bootstrap 5
- Jinja2

## Setup Steps

1. Create a virtual environment:

```powershell
python -m venv .venv
```

2. Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Run the application:

```powershell
python app.py
```

5. Open the browser:

```text
http://127.0.0.1:5000
```

## Notes

- No authentication system is included, as required.
- SQLite tables are created automatically on first run.
- Uploaded complaint images are stored in `static/uploads/`.
