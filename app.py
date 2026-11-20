from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import sqlite3
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Database connection
def get_db():
    conn = sqlite3.connect("civic.db")
    conn.row_factory = sqlite3.Row
    return conn

# Create table and safely add status to existing records
def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            citizen_name TEXT NOT NULL,
            category TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            image TEXT
        )
    """)

    columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(complaints)").fetchall()
    ]

    if "status" not in columns:
        conn.execute("""
            ALTER TABLE complaints
            ADD COLUMN status TEXT NOT NULL DEFAULT 'Pending'
        """)

    conn.commit()
    conn.close()

init_db()

# Home page
@app.route("/")
def home():
    return render_template("index.html")

# Submit complaint
@app.route("/submit", methods=["POST"])
def submit():
    citizen_name = request.form.get("citizen_name", "").strip()
    category = request.form.get("category", "").strip()
    location = request.form.get("location", "").strip()
    description = request.form.get("description", "").strip()

    if not all([citizen_name, category, location, description]):
        return "Please fill in all required fields.", 400

    image = request.files.get("image")
    image_filename = None

    if image and image.filename:
        if "." not in image.filename:
            return "Invalid image filename.", 400

        extension = image.filename.rsplit(".", 1)[1].lower()

        if extension not in ["jpg", "jpeg", "png", "webp"]:
            return "Only JPG, PNG and WEBP images are allowed.", 400

        filename = secure_filename(image.filename)
        image_filename = uuid.uuid4().hex + "_" + filename

        image.save(
            os.path.join(app.config["UPLOAD_FOLDER"], image_filename)
        )

    conn = get_db()

    cursor = conn.execute("""
        INSERT INTO complaints
        (citizen_name, category, location, description, image)
        VALUES (?, ?, ?, ?, ?)
    """, (
        citizen_name, category, location,
        description, image_filename
    ))

    complaint_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return f"""
    <h2>Complaint Submitted Successfully!</h2>
    <p>Your Complaint ID is: {complaint_id}</p>
    <a href="/">Submit Another Complaint</a>
    <br><br><a href="/admin">View Admin Dashboard</a>
    """

# Admin dashboard
@app.route("/admin")
def admin():
    conn = get_db()

    complaints = conn.execute("""
        SELECT * FROM complaints ORDER BY id DESC
    """).fetchall()

    total = conn.execute(
        "SELECT COUNT(*) FROM complaints"
    ).fetchone()[0]

    pending = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE status='Pending'"
    ).fetchone()[0]

    in_progress = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE status='In Progress'"
    ).fetchone()[0]

    resolved = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE status='Resolved'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "admin.html",
        complaints=complaints,
        total=total,
        pending=pending,
        in_progress=in_progress,
        resolved=resolved
    )

# Update complaint status
@app.route("/update_status/<int:complaint_id>", methods=["POST"])
def update_status(complaint_id):
    status = request.form.get("status")

    allowed_statuses = ["Pending", "In Progress", "Resolved"]

    if status not in allowed_statuses:
        return "Invalid status", 400

    conn = get_db()

    conn.execute("""
        UPDATE complaints
        SET status = ?
        WHERE id = ?
    """, (status, complaint_id))

    conn.commit()
    conn.close()

    return redirect(url_for("admin"))

# Display uploaded images
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"], filename
    )

if __name__ == "__main__":
    app.run(debug=True)