import sqlite3
import string
import random
import csv
from datetime import datetime, timedelta
from io import StringIO
from math import ceil
from pathlib import Path
from uuid import uuid4

from flask import Flask, Response, flash, g, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "database.db"
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

ROLE_OPTIONS = ["Student", "Faculty", "Staff", "Visitor"]
AREA_TYPE_OPTIONS = [
    "Washroom",
    "Classroom",
    "Corridor",
    "Lab",
    "Library",
    "Hostel",
    "Canteen",
    "Sports Area",
    "Parking",
    "Other",
]
ISSUE_CATEGORY_OPTIONS = [
    "Dirty Floor",
    "Bad Smell",
    "Overflowing Dustbin",
    "Water Leakage",
    "Blocked Toilet",
    "Broken Dustbin",
    "No Soap",
    "No Tissue",
    "Pest Problem",
    "Other",
]
PRIORITY_OPTIONS = ["Low", "Medium", "High"]
STATUS_OPTIONS = ["Pending", "Assigned", "In Progress", "Resolved", "Closed"]
CLEANING_TYPE_OPTIONS = ["Daily", "Weekly", "Monthly"]
REPORT_TYPE_OPTIONS = ["daily", "weekly", "monthly"]
ACTIVE_COMPLAINT_STATUSES = ["Pending", "Assigned", "In Progress"]
RESOLVED_STATUSES = ["Resolved", "Closed"]
OVERDUE_DAYS = 2
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


app = Flask(__name__)
app.config["SECRET_KEY"] = "campus-cleanliness-system-secret-key"
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT UNIQUE NOT NULL,
            reporter_name TEXT,
            department TEXT NOT NULL,
            role TEXT NOT NULL,
            building TEXT NOT NULL,
            floor TEXT NOT NULL,
            location TEXT NOT NULL,
            area_type TEXT NOT NULL,
            issue_category TEXT NOT NULL,
            priority TEXT NOT NULL,
            description TEXT NOT NULL,
            image TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            assigned_staff TEXT,
            remarks TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS cleaning_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT NOT NULL,
            building TEXT NOT NULL,
            cleaning_type TEXT NOT NULL,
            assigned_staff TEXT NOT NULL,
            scheduled_date TEXT NOT NULL,
            remarks TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.commit()
    db.close()


def get_filter_options():
    db = get_db()
    buildings = db.execute(
        "SELECT DISTINCT building FROM complaints WHERE building IS NOT NULL AND building != '' ORDER BY building"
    ).fetchall()
    area_types = db.execute(
        "SELECT DISTINCT area_type FROM complaints WHERE area_type IS NOT NULL AND area_type != '' ORDER BY area_type"
    ).fetchall()
    return {
        "buildings": [row["building"] for row in buildings],
        "area_types": [row["area_type"] for row in area_types],
    }


def get_schedule_filter_options():
    db = get_db()
    buildings = db.execute(
        "SELECT DISTINCT building FROM cleaning_schedules WHERE building IS NOT NULL AND building != '' ORDER BY building"
    ).fetchall()
    return {
        "buildings": [row["building"] for row in buildings],
    }


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_complaint_id():
    db = get_db()
    while True:
        timestamp = datetime.now().strftime("%Y%m%d")
        token = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        complaint_id = f"CCMS-{timestamp}-{token}"
        existing = db.execute(
            "SELECT 1 FROM complaints WHERE complaint_id = ?",
            (complaint_id,),
        ).fetchone()
        if existing is None:
            return complaint_id


def normalize_form_data(form):
    return {
        "reporter_name": form.get("reporter_name", "").strip(),
        "department": form.get("department", "").strip(),
        "role": form.get("role", "").strip(),
        "building": form.get("building", "").strip(),
        "floor": form.get("floor", "").strip(),
        "location": form.get("location", "").strip(),
        "area_type": form.get("area_type", "").strip(),
        "issue_category": form.get("issue_category", "").strip(),
        "priority": form.get("priority", "").strip(),
        "description": form.get("description", "").strip(),
    }


def validate_complaint_form(data, image_file):
    errors = []

    required_fields = {
        "department": "Department is required.",
        "role": "Role is required.",
        "building": "Building is required.",
        "floor": "Floor is required.",
        "location": "Exact location is required.",
        "area_type": "Area type is required.",
        "issue_category": "Issue category is required.",
        "priority": "Priority is required.",
        "description": "Description is required.",
    }

    for field, message in required_fields.items():
        if not data[field]:
            errors.append(message)

    if data["role"] and data["role"] not in ROLE_OPTIONS:
        errors.append("Please select a valid role.")
    if data["area_type"] and data["area_type"] not in AREA_TYPE_OPTIONS:
        errors.append("Please select a valid area type.")
    if data["issue_category"] and data["issue_category"] not in ISSUE_CATEGORY_OPTIONS:
        errors.append("Please select a valid issue category.")
    if data["priority"] and data["priority"] not in PRIORITY_OPTIONS:
        errors.append("Please select a valid priority.")
    if data["description"] and len(data["description"]) < 10:
        errors.append("Description must be at least 10 characters long.")

    if image_file and image_file.filename:
        if not allowed_file(image_file.filename):
            errors.append("Image must be a PNG, JPG, JPEG, GIF, or WEBP file.")

    return errors


def validate_management_update(form):
    errors = []
    status = form.get("status", "").strip()
    assigned_staff = form.get("assigned_staff", "").strip()
    remarks = form.get("remarks", "").strip()

    if not status:
        errors.append("Status is required.")
    elif status not in STATUS_OPTIONS:
        errors.append("Please select a valid status.")

    if len(assigned_staff) > 100:
        errors.append("Assigned staff name must be 100 characters or fewer.")
    if len(remarks) > 1000:
        errors.append("Remarks must be 1000 characters or fewer.")

    return {
        "status": status,
        "assigned_staff": assigned_staff,
        "remarks": remarks,
    }, errors


def validate_schedule_form(form):
    data = {
        "area": form.get("area", "").strip(),
        "building": form.get("building", "").strip(),
        "cleaning_type": form.get("cleaning_type", "").strip(),
        "assigned_staff": form.get("assigned_staff", "").strip(),
        "scheduled_date": form.get("scheduled_date", "").strip(),
        "remarks": form.get("remarks", "").strip(),
    }
    errors = []

    for field, label in (
        ("area", "Area"),
        ("building", "Building"),
        ("cleaning_type", "Cleaning type"),
        ("assigned_staff", "Assigned staff"),
        ("scheduled_date", "Scheduled date"),
    ):
        if not data[field]:
            errors.append(f"{label} is required.")

    if data["cleaning_type"] and data["cleaning_type"] not in CLEANING_TYPE_OPTIONS:
        errors.append("Please select a valid cleaning type.")

    if data["scheduled_date"]:
        try:
            datetime.strptime(data["scheduled_date"], "%Y-%m-%d")
        except ValueError:
            errors.append("Scheduled date must be a valid date.")

    if len(data["remarks"]) > 1000:
        errors.append("Remarks must be 1000 characters or fewer.")

    return data, errors


def serialize_complaint(complaint):
    if complaint is None:
        return None

    image_url = None
    if complaint["image"]:
        image_url = url_for("static", filename=f"uploads/{complaint['image']}")

    return {
        "complaint_id": complaint["complaint_id"],
        "reporter_name": complaint["reporter_name"],
        "department": complaint["department"],
        "role": complaint["role"],
        "building": complaint["building"],
        "floor": complaint["floor"],
        "location": complaint["location"],
        "area_type": complaint["area_type"],
        "issue_category": complaint["issue_category"],
        "priority": complaint["priority"],
        "description": complaint["description"],
        "status": complaint["status"],
        "assigned_staff": complaint["assigned_staff"],
        "remarks": complaint["remarks"],
        "created_at": complaint["created_at"],
        "updated_at": complaint["updated_at"],
        "image_url": image_url,
    }


def fetch_complaint_by_id(complaint_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM complaints WHERE UPPER(complaint_id) = ?",
        (complaint_id.upper(),),
    ).fetchone()


def fetch_schedule_by_id(schedule_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM cleaning_schedules WHERE id = ?",
        (schedule_id,),
    ).fetchone()


def build_management_filters(args):
    return {
        "search": args.get("search", "").strip(),
        "status": args.get("status", "").strip(),
        "priority": args.get("priority", "").strip(),
        "building": args.get("building", "").strip(),
        "area_type": args.get("area_type", "").strip(),
    }


def fetch_management_complaints(filters, page, per_page):
    where_clauses = []
    params = []

    if filters["search"]:
        where_clauses.append(
            """
            (
                complaint_id LIKE ? OR
                department LIKE ? OR
                building LIKE ? OR
                location LIKE ? OR
                IFNULL(assigned_staff, '') LIKE ?
            )
            """
        )
        search_value = f"%{filters['search']}%"
        params.extend([search_value] * 5)

    if filters["status"]:
        where_clauses.append("status = ?")
        params.append(filters["status"])
    if filters["priority"]:
        where_clauses.append("priority = ?")
        params.append(filters["priority"])
    if filters["building"]:
        where_clauses.append("building = ?")
        params.append(filters["building"])
    if filters["area_type"]:
        where_clauses.append("area_type = ?")
        params.append(filters["area_type"])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    db = get_db()

    total = db.execute(
        f"SELECT COUNT(*) FROM complaints {where_sql}",
        params,
    ).fetchone()[0]

    total_pages = max(1, ceil(total / per_page)) if total else 1
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    complaints = db.execute(
        f"""
        SELECT *
        FROM complaints
        {where_sql}
        ORDER BY datetime(updated_at) DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, per_page, offset],
    ).fetchall()

    return complaints, total, total_pages, page


def fetch_schedule_filters(args):
    return {
        "building": args.get("building", "").strip(),
        "cleaning_type": args.get("cleaning_type", "").strip(),
        "search": args.get("search", "").strip(),
    }


def fetch_schedules(filters):
    where_clauses = []
    params = []

    if filters["building"]:
        where_clauses.append("building = ?")
        params.append(filters["building"])
    if filters["cleaning_type"]:
        where_clauses.append("cleaning_type = ?")
        params.append(filters["cleaning_type"])
    if filters["search"]:
        where_clauses.append("(area LIKE ? OR assigned_staff LIKE ?)")
        search_value = f"%{filters['search']}%"
        params.extend([search_value, search_value])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    db = get_db()
    return db.execute(
        f"""
        SELECT *
        FROM cleaning_schedules
        {where_sql}
        ORDER BY date(scheduled_date) ASC, datetime(updated_at) DESC
        """,
        params,
    ).fetchall()


def fetch_complaint_stats():
    db = get_db()
    status_counts = {
        row["status"]: row["count"]
        for row in db.execute(
            "SELECT status, COUNT(*) AS count FROM complaints GROUP BY status"
        ).fetchall()
    }
    priority_counts = {
        row["priority"]: row["count"]
        for row in db.execute(
            "SELECT priority, COUNT(*) AS count FROM complaints GROUP BY priority"
        ).fetchall()
    }

    return {
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "stats": {
            "total": db.execute("SELECT COUNT(*) FROM complaints").fetchone()[0],
            "pending": status_counts.get("Pending", 0),
            "assigned": status_counts.get("Assigned", 0),
            "in_progress": status_counts.get("In Progress", 0),
            "resolved": status_counts.get("Resolved", 0),
            "closed": status_counts.get("Closed", 0),
            "high_priority": priority_counts.get("High", 0),
        },
    }


def fetch_dashboard_reminders():
    # Centralize dashboard reminder queries so the summary cards and lists stay consistent.
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    overdue_cutoff = (datetime.now() - timedelta(days=OVERDUE_DAYS)).strftime(DATE_FORMAT)
    status_placeholders = ",".join("?" for _ in ACTIVE_COMPLAINT_STATUSES)

    todays_tasks = db.execute(
        """
        SELECT area, building, cleaning_type, assigned_staff, scheduled_date
        FROM cleaning_schedules
        WHERE scheduled_date = ?
        ORDER BY cleaning_type, area
        """,
        (today,),
    ).fetchall()
    pending_complaints = db.execute(
        """
        SELECT complaint_id, location, building, priority, created_at
        FROM complaints
        WHERE status = 'Pending'
        ORDER BY datetime(created_at) ASC
        LIMIT 5
        """
    ).fetchall()
    high_priority = db.execute(
        f"""
        SELECT complaint_id, status, building, location, created_at
        FROM complaints
        WHERE priority = 'High' AND status IN ({status_placeholders})
        ORDER BY datetime(created_at) ASC
        LIMIT 5
        """,
        ACTIVE_COMPLAINT_STATUSES,
    ).fetchall()
    overdue = db.execute(
        f"""
        SELECT complaint_id, status, building, location, created_at
        FROM complaints
        WHERE status IN ({status_placeholders}) AND datetime(created_at) < datetime(?)
        ORDER BY datetime(created_at) ASC
        LIMIT 5
        """,
        [*ACTIVE_COMPLAINT_STATUSES, overdue_cutoff],
    ).fetchall()

    return {
        "today_label": datetime.now().strftime("%d %b %Y"),
        "todays_tasks": todays_tasks,
        "pending_complaints": pending_complaints,
        "high_priority": high_priority,
        "overdue": overdue,
    }


def get_period_range(report_type):
    now = datetime.now()

    if report_type == "daily":
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)
    elif report_type == "weekly":
        start = datetime(now.year, now.month, now.day) - timedelta(days=now.weekday())
        end = start + timedelta(days=7)
    else:
        start = datetime(now.year, now.month, 1)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1)
        else:
            end = datetime(now.year, now.month + 1, 1)

    return start, end


def calculate_average_resolution_time(rows):
    durations = []
    for row in rows:
        try:
            created_at = datetime.strptime(row["created_at"], DATE_FORMAT)
            updated_at = datetime.strptime(row["updated_at"], DATE_FORMAT)
        except ValueError:
            continue
        duration = updated_at - created_at
        if duration.total_seconds() >= 0:
            durations.append(duration.total_seconds())

    if not durations:
        return "N/A"

    average_hours = sum(durations) / len(durations) / 3600
    return f"{average_hours:.1f} hours"


def build_report_summary(report_type):
    # Report summaries are based on complaint creation dates for the selected period.
    start, end = get_period_range(report_type)
    db = get_db()
    complaints = db.execute(
        """
        SELECT *
        FROM complaints
        WHERE datetime(created_at) >= datetime(?) AND datetime(created_at) < datetime(?)
        ORDER BY datetime(created_at) DESC
        """,
        (start.strftime(DATE_FORMAT), end.strftime(DATE_FORMAT)),
    ).fetchall()

    total = len(complaints)
    resolved_rows = [row for row in complaints if row["status"] in RESOLVED_STATUSES]
    pending_rows = [row for row in complaints if row["status"] in ACTIVE_COMPLAINT_STATUSES]

    most_reported_area_row = db.execute(
        """
        SELECT area_type, COUNT(*) AS total
        FROM complaints
        WHERE datetime(created_at) >= datetime(?) AND datetime(created_at) < datetime(?)
        GROUP BY area_type
        ORDER BY total DESC, area_type ASC
        LIMIT 1
        """,
        (start.strftime(DATE_FORMAT), end.strftime(DATE_FORMAT)),
    ).fetchone()
    most_common_issue_row = db.execute(
        """
        SELECT issue_category, COUNT(*) AS total
        FROM complaints
        WHERE datetime(created_at) >= datetime(?) AND datetime(created_at) < datetime(?)
        GROUP BY issue_category
        ORDER BY total DESC, issue_category ASC
        LIMIT 1
        """,
        (start.strftime(DATE_FORMAT), end.strftime(DATE_FORMAT)),
    ).fetchone()

    return {
        "report_type": report_type,
        "label": report_type.capitalize(),
        "start": start,
        "end": end,
        "start_display": start.strftime("%d %b %Y"),
        "end_display": (end - timedelta(days=1)).strftime("%d %b %Y"),
        "generated_at": datetime.now().strftime("%d %b %Y %I:%M %p"),
        "total_complaints": total,
        "resolved": len(resolved_rows),
        "pending": len(pending_rows),
        "average_resolution_time": calculate_average_resolution_time(resolved_rows),
        "most_reported_area": most_reported_area_row["area_type"] if most_reported_area_row else "N/A",
        "most_common_issue": most_common_issue_row["issue_category"] if most_common_issue_row else "N/A",
        "complaints": complaints,
    }


def serialize_report_rows(complaints):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Complaint ID",
            "Department",
            "Building",
            "Area Type",
            "Issue Category",
            "Priority",
            "Status",
            "Assigned Staff",
            "Created At",
            "Updated At",
        ]
    )
    for complaint in complaints:
        writer.writerow(
            [
                complaint["complaint_id"],
                complaint["department"],
                complaint["building"],
                complaint["area_type"],
                complaint["issue_category"],
                complaint["priority"],
                complaint["status"],
                complaint["assigned_staff"] or "",
                complaint["created_at"],
                complaint["updated_at"],
            ]
        )
    return output.getvalue()


@app.context_processor
def inject_now():
    return {
        "current_year": datetime.now().year,
        "status_options": STATUS_OPTIONS,
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/report", methods=["GET", "POST"])
def report_complaint():
    form_data = {
        "reporter_name": "",
        "department": "",
        "role": "",
        "building": "",
        "floor": "",
        "location": "",
        "area_type": "",
        "issue_category": "",
        "priority": "",
        "description": "",
    }

    if request.method == "POST":
        form_data = normalize_form_data(request.form)
        image_file = request.files.get("image")
        errors = validate_complaint_form(form_data, image_file)

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "report_complaint.html",
                form_data=form_data,
                role_options=ROLE_OPTIONS,
                area_type_options=AREA_TYPE_OPTIONS,
                issue_category_options=ISSUE_CATEGORY_OPTIONS,
                priority_options=PRIORITY_OPTIONS,
            )

        image_name = None
        if image_file and image_file.filename:
            extension = image_file.filename.rsplit(".", 1)[1].lower()
            filename = secure_filename(image_file.filename.rsplit(".", 1)[0])
            image_name = f"{filename}-{uuid4().hex[:12]}.{extension}"
            image_file.save(UPLOAD_FOLDER / image_name)

        complaint_id = generate_complaint_id()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db = get_db()
        db.execute(
            """
            INSERT INTO complaints (
                complaint_id, reporter_name, department, role, building, floor,
                location, area_type, issue_category, priority, description,
                image, status, assigned_staff, remarks, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                complaint_id,
                form_data["reporter_name"] or None,
                form_data["department"],
                form_data["role"],
                form_data["building"],
                form_data["floor"],
                form_data["location"],
                form_data["area_type"],
                form_data["issue_category"],
                form_data["priority"],
                form_data["description"],
                image_name,
                "Pending",
                None,
                None,
                timestamp,
                timestamp,
            ),
        )
        db.commit()

        flash(f"Complaint submitted successfully. Your Complaint ID is {complaint_id}.", "success")
        return redirect(url_for("track_complaint", complaint_id=complaint_id))

    return render_template(
        "report_complaint.html",
        form_data=form_data,
        role_options=ROLE_OPTIONS,
        area_type_options=AREA_TYPE_OPTIONS,
        issue_category_options=ISSUE_CATEGORY_OPTIONS,
        priority_options=PRIORITY_OPTIONS,
    )


@app.route("/track", methods=["GET", "POST"])
def track_complaint():
    complaint = None
    complaint_id = request.args.get("complaint_id", "").strip()

    if request.method == "POST":
        complaint_id = request.form.get("complaint_id", "").strip().upper()
        if not complaint_id:
            flash("Please enter a complaint ID to continue.", "danger")
        else:
            return redirect(url_for("track_complaint", complaint_id=complaint_id))

    if complaint_id:
        complaint = fetch_complaint_by_id(complaint_id)
        if complaint is None:
            flash("No complaint found for the provided Complaint ID.", "warning")

    return render_template("track_complaint.html", complaint=complaint, complaint_id=complaint_id)


@app.get("/api/complaints/<complaint_id>")
def complaint_lookup_api(complaint_id):
    normalized_id = complaint_id.strip().upper()
    if not normalized_id:
        return jsonify({"message": "Complaint ID is required."}), 400

    complaint = fetch_complaint_by_id(normalized_id)
    if complaint is None:
        return jsonify({"message": "No complaint found for the provided Complaint ID."}), 404

    return jsonify({"complaint": serialize_complaint(complaint)})


@app.route("/admin")
def admin_dashboard():
    db = get_db()
    recent_complaints = db.execute(
        """
        SELECT complaint_id, department, role, building, location, issue_category,
               priority, status, created_at
        FROM complaints
        ORDER BY datetime(created_at) DESC
        LIMIT 10
        """
    ).fetchall()

    complaint_stats = fetch_complaint_stats()
    reminders = fetch_dashboard_reminders()

    chart_data = {
        "status_labels": STATUS_OPTIONS,
        "status_values": [complaint_stats["status_counts"].get(status, 0) for status in STATUS_OPTIONS],
        "priority_labels": PRIORITY_OPTIONS,
        "priority_values": [complaint_stats["priority_counts"].get(priority, 0) for priority in PRIORITY_OPTIONS],
    }

    return render_template(
        "admin_dashboard.html",
        complaints=recent_complaints,
        stats=complaint_stats["stats"],
        chart_data=chart_data,
        reminders=reminders,
    )


@app.route("/admin/complaints")
def manage_complaints():
    filters = build_management_filters(request.args)
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1

    complaints, total, total_pages, current_page = fetch_management_complaints(filters, page, per_page=10)
    filter_options = get_filter_options()

    return render_template(
        "manage_complaints.html",
        complaints=complaints,
        filters=filters,
        filter_options=filter_options,
        status_options=STATUS_OPTIONS,
        priority_options=PRIORITY_OPTIONS,
        total=total,
        total_pages=total_pages,
        current_page=current_page,
    )


@app.post("/admin/complaints/<complaint_id>/update")
def update_complaint(complaint_id):
    complaint = fetch_complaint_by_id(complaint_id)
    if complaint is None:
        flash("Complaint not found. It may have already been removed.", "warning")
        return redirect(url_for("manage_complaints", **request.args))

    update_data, errors = validate_management_update(request.form)
    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("manage_complaints", **request.args))

    db = get_db()
    db.execute(
        """
        UPDATE complaints
        SET status = ?, assigned_staff = ?, remarks = ?, updated_at = ?
        WHERE complaint_id = ?
        """,
        (
            update_data["status"],
            update_data["assigned_staff"] or None,
            update_data["remarks"] or None,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            complaint["complaint_id"],
        ),
    )
    db.commit()

    flash(f"Complaint {complaint['complaint_id']} updated successfully.", "success")
    return redirect(url_for("manage_complaints", **request.args))


@app.post("/admin/complaints/<complaint_id>/delete")
def delete_complaint(complaint_id):
    complaint = fetch_complaint_by_id(complaint_id)
    if complaint is None:
        flash("Complaint not found. It may have already been removed.", "warning")
        return redirect(url_for("manage_complaints", **request.args))

    db = get_db()
    db.execute("DELETE FROM complaints WHERE complaint_id = ?", (complaint["complaint_id"],))
    db.commit()

    flash(f"Complaint {complaint['complaint_id']} deleted successfully.", "success")
    return redirect(url_for("manage_complaints", **request.args))


@app.route("/admin/schedules", methods=["GET", "POST"])
def manage_schedules():
    filters = fetch_schedule_filters(request.args)

    if request.method == "POST":
        schedule_data, errors = validate_schedule_form(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
        else:
            db = get_db()
            timestamp = datetime.now().strftime(DATE_FORMAT)
            db.execute(
                """
                INSERT INTO cleaning_schedules (
                    area, building, cleaning_type, assigned_staff, scheduled_date,
                    remarks, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule_data["area"],
                    schedule_data["building"],
                    schedule_data["cleaning_type"],
                    schedule_data["assigned_staff"],
                    schedule_data["scheduled_date"],
                    schedule_data["remarks"] or None,
                    timestamp,
                    timestamp,
                ),
            )
            db.commit()
            flash("Cleaning schedule added successfully.", "success")
        return redirect(url_for("manage_schedules", **request.args))

    schedules = fetch_schedules(filters)
    return render_template(
        "manage_schedules.html",
        schedules=schedules,
        filters=filters,
        cleaning_type_options=CLEANING_TYPE_OPTIONS,
        filter_options=get_schedule_filter_options(),
        schedule_form_data={
            "area": "",
            "building": "",
            "cleaning_type": "",
            "assigned_staff": "",
            "scheduled_date": "",
            "remarks": "",
        },
    )


@app.post("/admin/schedules/<int:schedule_id>/update")
def update_schedule(schedule_id):
    schedule = fetch_schedule_by_id(schedule_id)
    if schedule is None:
        flash("Schedule not found.", "warning")
        return redirect(url_for("manage_schedules", **request.args))

    schedule_data, errors = validate_schedule_form(request.form)
    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("manage_schedules", **request.args))

    db = get_db()
    db.execute(
        """
        UPDATE cleaning_schedules
        SET area = ?, building = ?, cleaning_type = ?, assigned_staff = ?,
            scheduled_date = ?, remarks = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            schedule_data["area"],
            schedule_data["building"],
            schedule_data["cleaning_type"],
            schedule_data["assigned_staff"],
            schedule_data["scheduled_date"],
            schedule_data["remarks"] or None,
            datetime.now().strftime(DATE_FORMAT),
            schedule_id,
        ),
    )
    db.commit()
    flash("Cleaning schedule updated successfully.", "success")
    return redirect(url_for("manage_schedules", **request.args))


@app.post("/admin/schedules/<int:schedule_id>/delete")
def delete_schedule(schedule_id):
    schedule = fetch_schedule_by_id(schedule_id)
    if schedule is None:
        flash("Schedule not found.", "warning")
        return redirect(url_for("manage_schedules", **request.args))

    db = get_db()
    db.execute("DELETE FROM cleaning_schedules WHERE id = ?", (schedule_id,))
    db.commit()
    flash("Cleaning schedule deleted successfully.", "success")
    return redirect(url_for("manage_schedules", **request.args))


@app.get("/reports")
def reports():
    report_type = request.args.get("type", "daily").strip().lower()
    if report_type not in REPORT_TYPE_OPTIONS:
        report_type = "daily"

    report = build_report_summary(report_type)
    return render_template(
        "reports.html",
        report=report,
        report_type_options=REPORT_TYPE_OPTIONS,
    )


@app.get("/reports/export")
def export_report_csv():
    report_type = request.args.get("type", "daily").strip().lower()
    if report_type not in REPORT_TYPE_OPTIONS:
        report_type = "daily"

    report = build_report_summary(report_type)
    csv_content = serialize_report_rows(report["complaints"])
    filename = f"{report_type}-report-{datetime.now().strftime('%Y%m%d')}.csv"

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/reports/print")
def print_report():
    report_type = request.args.get("type", "daily").strip().lower()
    if report_type not in REPORT_TYPE_OPTIONS:
        report_type = "daily"

    report = build_report_summary(report_type)
    return render_template("print_report.html", report=report)


@app.teardown_appcontext
def teardown_db(error):
    close_db(error)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
