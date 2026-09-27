# ClinicQueue — Digital Queue Management System

A college-project-ready Flask website for a clinic digital queue management system.

## Technology
- Python 3
- Flask
- SQLite for an easy local demo
- HTML, CSS and JavaScript
- PostgreSQL-compatible schema is included in `schema.sql`

## Run on Windows / Dell laptop

1. Install Python from https://www.python.org/downloads/ and tick **Add python.exe to PATH**.
2. Install VS Code from https://code.visualstudio.com/.
3. Extract this project folder and open it in VS Code.
4. Open **Terminal → New Terminal**.
5. Run:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

6. Open `http://127.0.0.1:5000` in Chrome.

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Patient | patient@clinic.com | patient123 |
| Doctor | doctor@clinic.com | doctor123 |
| Admin | admin@clinic.com | admin123 |

## Main features

### Patient
- Role-based login
- Book appointment
- Automatic digital token
- Priority/urgent option
- Live queue tracking
- Notifications
- Prescriptions
- Medical records
- Billing
- Feedback

### Doctor
- Today's queue
- Priority queue handling
- Call next patient
- Consultation status
- Prescription and medical record entry

### Admin
- Clinic statistics
- Add doctors
- Doctor availability toggle
- Appointment monitoring
- Feedback review

### Public live queue
- Waiting-room display
- Current consultation
- Automatic refresh every 5 seconds

## Project structure

```text
digital_queue_clinic_project/
├── app.py
├── requirements.txt
├── schema.sql
├── README.md
├── static/
│   ├── style.css
│   └── app.js
└── templates/
    ├── base.html
    ├── index.html
    ├── login.html
    ├── patient.html
    ├── doctor.html
    ├── admin.html
    └── queue.html
```

## Reset demo data
Delete `clinic_queue.db` while the server is stopped, then run `python app.py` again. The demo accounts and sample queue will be recreated.

> This is a college/demo application. Passwords are intentionally simple for demonstration and should be hashed and protected before production use.
