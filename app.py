from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os, sqlite3
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clinic-demo-secret-change-me")
DB_PATH = os.environ.get("SQLITE_DB", os.path.join(os.path.dirname(__file__), "clinic_queue.db"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('patient','doctor','admin')),
        phone TEXT
    );
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        specialization TEXT NOT NULL,
        room TEXT,
        available INTEGER DEFAULT 1,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        appointment_date TEXT NOT NULL,
        appointment_time TEXT NOT NULL,
        reason TEXT,
        status TEXT DEFAULT 'Waiting',
        token INTEGER NOT NULL,
        priority INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(patient_id) REFERENCES users(id),
        FOREIGN KEY(doctor_id) REFERENCES doctors(id)
    );
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        diagnosis TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(patient_id) REFERENCES users(id),
        FOREIGN KEY(doctor_id) REFERENCES doctors(id)
    );
    CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        appointment_id INTEGER,
        amount REAL NOT NULL,
        status TEXT DEFAULT 'Unpaid',
        description TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(patient_id) REFERENCES users(id),
        FOREIGN KEY(appointment_id) REFERENCES appointments(id)
    );
    CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        medicine TEXT NOT NULL,
        dosage TEXT,
        instructions TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(patient_id) REFERENCES users(id),
        FOREIGN KEY(doctor_id) REFERENCES doctors(id)
    );
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(patient_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)

    # Demo accounts and doctor.
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.execute("INSERT INTO users(name,email,password,role,phone) VALUES (?,?,?,?,?)",
                     ("Admin User", "admin@clinic.com", "admin123", "admin", "9000000001"))
        doctor_user = conn.execute(
            "INSERT INTO users(name,email,password,role,phone) VALUES (?,?,?,?,?) RETURNING id",
            ("Dr. Priya Sharma", "doctor@clinic.com", "doctor123", "doctor", "9000000002")
        ).fetchone()[0]
        patient_user = conn.execute(
            "INSERT INTO users(name,email,password,role,phone) VALUES (?,?,?,?,?) RETURNING id",
            ("Demo Patient", "patient@clinic.com", "patient123", "patient", "9000000003")
        ).fetchone()[0]
        doctor_id = conn.execute(
            "INSERT INTO doctors(user_id,specialization,room,available) VALUES (?,?,?,?) RETURNING id",
            (doctor_user, "General Physician", "Room 101", 1)
        ).fetchone()[0]
        today = date.today().isoformat()
        conn.execute("INSERT INTO appointments(patient_id,doctor_id,appointment_date,appointment_time,reason,status,token,priority) VALUES (?,?,?,?,?,?,?,?)",
                     (patient_user, doctor_id, today, "10:00", "General consultation", "In Consultation", 1, 0))
        conn.execute("INSERT INTO appointments(patient_id,doctor_id,appointment_date,appointment_time,reason,status,token,priority) VALUES (?,?,?,?,?,?,?,?)",
                     (patient_user, doctor_id, today, "10:30", "Follow-up consultation", "Waiting", 2, 1))
        conn.execute("INSERT INTO notifications(user_id,message) VALUES (?,?)",
                     (patient_user, "Welcome to ClinicQueue. Your demo queue is ready."))
        conn.execute("INSERT INTO bills(patient_id,amount,status,description) VALUES (?,?,?,?)",
                     (patient_user, 500.00, "Unpaid", "General consultation"))
    conn.commit()
    conn.close()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return user


def require_role(role):
    user = current_user()
    return user if user and user["role"] == role else None


def next_token(conn, doctor_id, appointment_date):
    row = conn.execute(
        "SELECT COALESCE(MAX(token),0)+1 AS n FROM appointments WHERE doctor_id=? AND appointment_date=?",
        (doctor_id, appointment_date)
    ).fetchone()
    return row["n"]


@app.context_processor
def inject_globals():
    return {"current_user": current_user(), "today": date.today().isoformat()}


@app.route("/")
def home():
    return render_template("index.html", user=current_user())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role", "patient")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=? AND role=?",
            (email, password, role)
        ).fetchone()
        conn.close()
        if user:
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome, {user['name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid email, password or selected role.", "error")
    return render_template("login.html", user=current_user())


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    return redirect(url_for({
        "patient": "patient_dashboard",
        "doctor": "doctor_dashboard",
        "admin": "admin_dashboard"
    }[user["role"]]))


@app.route("/patient")
def patient_dashboard():
    user = require_role("patient")
    if not user:
        return redirect(url_for("login"))
    conn = get_db()
    appointments = conn.execute("""
        SELECT a.*, u.name AS doctor_name, d.specialization, d.room
        FROM appointments a
        JOIN doctors d ON a.doctor_id=d.id
        JOIN users u ON d.user_id=u.id
        WHERE a.patient_id=?
        ORDER BY a.appointment_date DESC, a.token ASC
    """, (user["id"],)).fetchall()
    doctors = conn.execute("""
        SELECT d.id,u.name,d.specialization,d.room,d.available
        FROM doctors d JOIN users u ON d.user_id=u.id ORDER BY d.available DESC,u.name
    """).fetchall()
    bills = conn.execute("SELECT * FROM bills WHERE patient_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    medicines = conn.execute("""
        SELECT m.*,u.name AS doctor_name FROM medicines m
        JOIN doctors d ON m.doctor_id=d.id JOIN users u ON d.user_id=u.id
        WHERE m.patient_id=? ORDER BY m.id DESC
    """, (user["id"],)).fetchall()
    records = conn.execute("""
        SELECT r.*,u.name AS doctor_name FROM records r
        JOIN doctors d ON r.doctor_id=d.id JOIN users u ON d.user_id=u.id
        WHERE r.patient_id=? ORDER BY r.id DESC
    """, (user["id"],)).fetchall()
    notifications = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 8", (user["id"],)
    ).fetchall()
    waiting_count = conn.execute(
        "SELECT COUNT(*) c FROM appointments WHERE patient_id=? AND status='Waiting'", (user["id"],)
    ).fetchone()["c"]
    conn.close()
    return render_template("patient.html", user=user, appointments=appointments, doctors=doctors,
                           bills=bills, medicines=medicines, records=records,
                           notifications=notifications, waiting_count=waiting_count)


@app.route("/appointment", methods=["POST"])
def appointment():
    user = require_role("patient")
    if not user:
        return redirect(url_for("login"))
    doctor_id = int(request.form["doctor_id"])
    appt_date = request.form["appointment_date"]
    appt_time = request.form["appointment_time"]
    reason = request.form.get("reason", "").strip() or "General consultation"
    priority = 1 if request.form.get("priority") == "1" else 0
    if appt_date < date.today().isoformat():
        flash("Please select today or a future date.", "error")
        return redirect(url_for("patient_dashboard"))
    conn = get_db()
    doctor = conn.execute("SELECT * FROM doctors WHERE id=?", (doctor_id,)).fetchone()
    if not doctor or not doctor["available"]:
        conn.close()
        flash("That doctor is currently unavailable.", "error")
        return redirect(url_for("patient_dashboard"))
    token = next_token(conn, doctor_id, appt_date)
    cur = conn.execute("""
        INSERT INTO appointments(patient_id,doctor_id,appointment_date,appointment_time,reason,status,token,priority)
        VALUES (?,?,?,?,?,?,?,?)
    """, (user["id"], doctor_id, appt_date, appt_time, reason, "Waiting", token, priority))
    conn.execute("INSERT INTO notifications(user_id,message) VALUES (?,?)",
                 (user["id"], f"Appointment booked successfully. Your digital token is #{token}."))
    conn.execute("INSERT INTO bills(patient_id,appointment_id,amount,status,description) VALUES (?,?,?,?,?)",
                 (user["id"], cur.lastrowid, 500.00, "Unpaid", "Consultation fee"))
    conn.commit(); conn.close()
    flash(f"Appointment booked! Your digital token is #{token}.", "success")
    return redirect(url_for("patient_dashboard"))


@app.route("/feedback", methods=["POST"])
def feedback():
    user = require_role("patient")
    if not user:
        return redirect(url_for("login"))
    rating = max(1, min(5, int(request.form["rating"])))
    message = request.form.get("message", "").strip()
    conn = get_db()
    conn.execute("INSERT INTO feedback(patient_id,rating,message) VALUES (?,?,?)",
                 (user["id"], rating, message))
    conn.commit(); conn.close()
    flash("Thank you for your feedback!", "success")
    return redirect(url_for("patient_dashboard"))


@app.route("/doctor")
def doctor_dashboard():
    user = require_role("doctor")
    if not user:
        return redirect(url_for("login"))
    conn = get_db()
    doctor = conn.execute("SELECT * FROM doctors WHERE user_id=?", (user["id"],)).fetchone()
    today = date.today().isoformat()
    queue = conn.execute("""
        SELECT a.*,p.name AS patient_name,p.phone
        FROM appointments a JOIN users p ON a.patient_id=p.id
        WHERE a.doctor_id=? AND a.appointment_date=?
        ORDER BY CASE WHEN a.status='In Consultation' THEN 0 WHEN a.status='Waiting' THEN 1 ELSE 2 END,
                 a.priority DESC,a.token ASC
    """, (doctor["id"], today)).fetchall()
    patients = conn.execute("""
        SELECT DISTINCT p.id,p.name,p.email,p.phone
        FROM appointments a JOIN users p ON a.patient_id=p.id
        WHERE a.doctor_id=? ORDER BY p.name
    """, (doctor["id"],)).fetchall()
    counts = {
        "waiting": conn.execute("SELECT COUNT(*) c FROM appointments WHERE doctor_id=? AND appointment_date=? AND status='Waiting'", (doctor["id"],today)).fetchone()["c"],
        "serving": conn.execute("SELECT COUNT(*) c FROM appointments WHERE doctor_id=? AND appointment_date=? AND status='In Consultation'", (doctor["id"],today)).fetchone()["c"],
        "completed": conn.execute("SELECT COUNT(*) c FROM appointments WHERE doctor_id=? AND appointment_date=? AND status='Completed'", (doctor["id"],today)).fetchone()["c"]
    }
    conn.close()
    return render_template("doctor.html", user=user, doctor=doctor, queue=queue, patients=patients, counts=counts)


@app.route("/doctor/call-next", methods=["POST"])
def call_next():
    user = require_role("doctor")
    if not user:
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    doctor = conn.execute("SELECT * FROM doctors WHERE user_id=?", (user["id"],)).fetchone()
    today = date.today().isoformat()
    current = conn.execute("""
        SELECT * FROM appointments WHERE doctor_id=? AND appointment_date=? AND status='In Consultation' LIMIT 1
    """, (doctor["id"], today)).fetchone()
    if current:
        conn.execute("UPDATE appointments SET status='Completed' WHERE id=?", (current["id"],))
    nxt = conn.execute("""
        SELECT a.*,p.name AS patient_name FROM appointments a JOIN users p ON a.patient_id=p.id
        WHERE a.doctor_id=? AND a.appointment_date=? AND a.status='Waiting'
        ORDER BY a.priority DESC,a.token ASC LIMIT 1
    """, (doctor["id"], today)).fetchone()
    if not nxt:
        conn.commit(); conn.close()
        return jsonify({"message": "No waiting patients in today's queue.", "token": None})
    conn.execute("UPDATE appointments SET status='In Consultation' WHERE id=?", (nxt["id"],))
    conn.execute("INSERT INTO notifications(user_id,message) VALUES (?,?)",
                 (nxt["patient_id"], f"Token #{nxt['token']} is now being called. Please proceed to {doctor['room']} ."))
    conn.commit(); conn.close()
    return jsonify({"message": f"Now calling token #{nxt['token']} — {nxt['patient_name']}.", "token": nxt["token"]})


@app.route("/doctor/prescription", methods=["POST"])
def prescription():
    user = require_role("doctor")
    if not user:
        return redirect(url_for("login"))
    patient_id = int(request.form["patient_id"])
    medicine = request.form["medicine"].strip()
    dosage = request.form.get("dosage", "").strip()
    instructions = request.form.get("instructions", "").strip()
    diagnosis = request.form.get("diagnosis", "").strip()
    notes = request.form.get("notes", "").strip()
    conn = get_db()
    doctor = conn.execute("SELECT id FROM doctors WHERE user_id=?", (user["id"],)).fetchone()
    conn.execute("INSERT INTO medicines(patient_id,doctor_id,medicine,dosage,instructions) VALUES (?,?,?,?,?)",
                 (patient_id, doctor["id"], medicine, dosage, instructions))
    conn.execute("INSERT INTO records(patient_id,doctor_id,diagnosis,notes) VALUES (?,?,?,?)",
                 (patient_id, doctor["id"], diagnosis, notes))
    conn.execute("INSERT INTO notifications(user_id,message) VALUES (?,?)",
                 (patient_id, "A new prescription and medical record has been added to your account."))
    conn.commit(); conn.close()
    flash("Prescription and medical record saved.", "success")
    return redirect(url_for("doctor_dashboard"))


@app.route("/admin")
def admin_dashboard():
    user = require_role("admin")
    if not user:
        return redirect(url_for("login"))
    conn = get_db()
    patients = conn.execute("SELECT * FROM users WHERE role='patient' ORDER BY name").fetchall()
    doctors = conn.execute("""SELECT d.*,u.name,u.email,u.phone FROM doctors d JOIN users u ON d.user_id=u.id ORDER BY u.name""").fetchall()
    appointments = conn.execute("""
        SELECT a.*,p.name patient_name,u.name doctor_name,d.room
        FROM appointments a JOIN users p ON a.patient_id=p.id
        JOIN doctors d ON a.doctor_id=d.id JOIN users u ON d.user_id=u.id
        ORDER BY a.appointment_date DESC,a.token ASC LIMIT 100
    """).fetchall()
    feedback = conn.execute("""
        SELECT f.*,u.name patient_name FROM feedback f JOIN users u ON f.patient_id=u.id ORDER BY f.id DESC
    """).fetchall()
    stats = {
        "patients": conn.execute("SELECT COUNT(*) c FROM users WHERE role='patient'").fetchone()["c"],
        "doctors": conn.execute("SELECT COUNT(*) c FROM users WHERE role='doctor'").fetchone()["c"],
        "appointments": conn.execute("SELECT COUNT(*) c FROM appointments").fetchone()["c"],
        "waiting": conn.execute("SELECT COUNT(*) c FROM appointments WHERE status='Waiting'").fetchone()["c"]
    }
    conn.close()
    return render_template("admin.html", user=user, patients=patients, doctors=doctors,
                           appointments=appointments, feedback=feedback, stats=stats)


@app.route("/admin/add-doctor", methods=["POST"])
def add_doctor():
    user = require_role("admin")
    if not user:
        return redirect(url_for("login"))
    name = request.form["name"].strip(); email = request.form["email"].strip().lower()
    password = request.form["password"]; phone = request.form.get("phone", "").strip()
    specialization = request.form["specialization"].strip(); room = request.form.get("room", "").strip()
    conn = get_db()
    try:
        cur = conn.execute("INSERT INTO users(name,email,password,role,phone) VALUES (?,?,?,?,?)",
                           (name,email,password,"doctor",phone))
        conn.execute("INSERT INTO doctors(user_id,specialization,room,available) VALUES (?,?,?,?)",
                     (cur.lastrowid,specialization,room,1))
        conn.commit(); flash("Doctor added successfully.", "success")
    except sqlite3.IntegrityError:
        conn.rollback(); flash("That email address already exists.", "error")
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/toggle-doctor/<int:doctor_id>", methods=["POST"])
def toggle_doctor(doctor_id):
    user = require_role("admin")
    if not user:
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    doctor = conn.execute("SELECT available FROM doctors WHERE id=?", (doctor_id,)).fetchone()
    if not doctor:
        conn.close(); return jsonify({"error": "Doctor not found"}), 404
    new_value = 0 if doctor["available"] else 1
    conn.execute("UPDATE doctors SET available=? WHERE id=?", (new_value, doctor_id))
    conn.commit(); conn.close()
    return jsonify({"available": new_value})


@app.route("/queue")
def live_queue():
    conn = get_db()
    today = date.today().isoformat()
    rows = conn.execute("""
        SELECT a.id,a.token,a.status,a.priority,p.name AS patient_name,u.name AS doctor_name,d.room,d.specialization
        FROM appointments a JOIN users p ON a.patient_id=p.id
        JOIN doctors d ON a.doctor_id=d.id JOIN users u ON d.user_id=u.id
        WHERE a.appointment_date=? AND a.status!='Completed'
        ORDER BY CASE WHEN a.status='In Consultation' THEN 0 ELSE 1 END,a.priority DESC,a.token ASC
    """, (today,)).fetchall()
    conn.close()
    return render_template("queue.html", rows=rows, today=today)


@app.route("/api/queue")
def api_queue():
    conn = get_db()
    today = date.today().isoformat()
    rows = conn.execute("""
        SELECT a.token,a.status,a.priority,p.name AS patient_name,u.name AS doctor_name,d.room,d.specialization
        FROM appointments a JOIN users p ON a.patient_id=p.id
        JOIN doctors d ON a.doctor_id=d.id JOIN users u ON d.user_id=u.id
        WHERE a.appointment_date=? AND a.status!='Completed'
        ORDER BY CASE WHEN a.status='In Consultation' THEN 0 ELSE 1 END,a.priority DESC,a.token ASC
    """, (today,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
