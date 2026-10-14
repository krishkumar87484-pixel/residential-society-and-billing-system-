# Residential Society Billing System

A DBMS project prototype for managing flats, residents, monthly maintenance bills, payments and resident complaints. The project is based on **Review 1** for Project 42, Team **AIML Rhinos**.

> **Current submission status:** Review 1 is included. Add Review 2 and the final presentation to `presentations/` before submitting. The Google Drive video link must be added to the link document after the video is uploaded.

## Prototype preview and features

- Dashboard with flat/resident counts, pending bills and collected payments.
- Flat register: create flats and store wing, floor and area.
- Resident register: add owners/tenants and link each resident to a flat.
- Maintenance billing: generate monthly bills from flat area and a configurable rate; duplicate flat/month bills are skipped.
- Payment register: record full or partial payments, prevent overpayment, and update bill status.
- Complaints: add a resident service request and update its status.
- Reports: show pending balances and monthly billed-versus-collected totals.
- Relational tables, primary keys, foreign keys and a unique constraint for one bill per flat/month.

## Run the working prototype

**Requirement:** Python 3.10 or newer. No third-party package installation is required.

1. Download or clone this repository.
2. Open a terminal in the repository folder.
3. Run:

   ```bash
   python run.py
   ```

4. Open **http://127.0.0.1:8000** in your browser.
5. Explore Flats, Residents, Maintenance bills, Payments, Complaints and Reports.
6. Stop the server with `Ctrl+C` in the terminal.

The first run creates a local SQLite database at `app/instance/society.db` and inserts sample records. The sample data is only for demonstration. To reset the demo, stop the server, delete that database file, and run `python run.py` again.

## Database and design

The data model follows the five entities from the review presentation:

| Table | Key fields | Purpose |
|---|---|---|
| `FLAT` | `flat_no` (PK) | Society flat, wing, floor and area |
| `RESIDENT` | `resident_id` (PK), `flat_no` (FK) | Owner/tenant details linked to a flat |
| `MAINTENANCE_BILL` | `bill_id` (PK), `flat_no` (FK) | Monthly bill, amount, due date and status |
| `PAYMENT` | `payment_id` (PK), `bill_id` (FK) | Payment date, amount and method |
| `COMPLAINT` | `complaint_id` (PK), `resident_id` (FK) | Resident service requests and status |

- `db/schema_sqlite.sql` documents the SQLite schema used by the local prototype.
- `db/schema_mysql.sql` contains the MySQL 8+ schema, payment-status triggers, an outstanding-dues view and a monthly-collection-summary view for the DBMS demonstration.
- The included browser application runs locally with SQLite so reviewers can try it without installing or configuring MySQL. Be transparent about this distinction during the demo.
- The sample rate of ₹5 per sq. ft. is only a configurable demonstration value; the review slides do not specify an official maintenance rate.

## Repository structure

```text
.
├── app/
│   ├── static/style.css        # Dashboard and form styling
│   └── instance/               # Local SQLite file created at runtime (git-ignored)
├── db/
│   ├── schema_mysql.sql         # MySQL schema, constraints and payment triggers
│   └── schema_sqlite.sql        # SQLite schema used by the prototype
├── docs/
│   ├── 5-minute-demo-script.md
│   ├── SUBMISSION-CHECKLIST.md
│   └── VIDEO-AND-PRESENTATION-LINKS.md
├── presentations/
│   ├── Review-1.pdf
│   └── README.md               # Instructions for adding Review 2 and final presentation
├── reports/
│   └── Final-Report-Draft.docx
├── tests/
│   └── smoke_test.py
├── run.py                      # No-dependency Python web server + SQLite logic
├── requirements.txt
└── README.md
```

## Test the prototype

With `python run.py` running, open another terminal and run:

```bash
python tests/smoke_test.py
```

The smoke test checks that the home page, database-backed pages and stylesheet respond. It is a lightweight sanity check, not a substitute for manually trying every form before recording the video.

## Suggested five-minute demonstration order

1. Dashboard and project purpose.
2. Flats and Residents.
3. Generate maintenance bills.
4. Record a payment and show the bill status change.
5. Create/update a complaint and open Reports.
6. Close with the database tables, constraints and MySQL trigger file.

See `docs/5-minute-demo-script.md` for a timed narration.

## Presentation and final submission files

Place all three slide decks / presentation exports in `presentations/` with clear names, for example:

- `Review-1.pdf` (already included)
- `Review-2.pdf` (to be added by the team)
- `Final-Presentation.pdf` or `.pptx` (to be added by the team)

After recording the five-minute prototype demonstration, upload it to Google Drive, set General access to **Anyone with the link – Viewer**, test the link in a private/incognito window, and paste it into `docs/VIDEO-AND-PRESENTATION-LINKS.md` and `docs/Video-and-Presentation-Links.docx` before committing those files. Do not publish private resident data; use the included fictional demo records.

## Project details

- **Project:** Design and Implementation of a Database Management System for a Residential Society
- **System:** Resident & Maintenance Billing System
- **Presented by:** Krish
- **Roll No.:** 25WU0102333
- **Team:** AIML Rhinos
- **Project No.:** 42
- **Subject:** Database Management Systems

## Limitations and future scope

This is an academic demonstration prototype, not a production society-management service. It does not include production authentication, authorization, secure deployment, backups, payment-gateway integration, automated reminders or hosting. Those should be added before any real-world use. Possible extensions include role-based login, PDF receipts, tenant move-in/move-out history, visitor logs, staff payroll and amenities management.
