#!/usr/bin/env python3
"""Zero-dependency web prototype for the Residential Society Billing System.
Run: python run.py, then open http://127.0.0.1:8000
Requires Python 3.10+ only. Data is stored in SQLite under app/instance/.
"""
from __future__ import annotations

import html
import os
import sqlite3
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DB_DIR = ROOT / "app" / "instance"
DB_PATH = Path(os.environ.get("SOCIETY_DB_PATH", str(DB_DIR / "society.db")))
CSS_PATH = ROOT / "app" / "static" / "style.css"


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def money(value) -> str:
    return f"₹{float(value or 0):,.2f}"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db() -> None:
    db = connect()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS flat (
            flat_no TEXT PRIMARY KEY, wing TEXT NOT NULL, floor INTEGER NOT NULL CHECK(floor >= 0),
            area_sqft REAL NOT NULL CHECK(area_sqft > 0)
        );
        CREATE TABLE IF NOT EXISTS resident (
            resident_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('Owner','Tenant')), flat_no TEXT NOT NULL,
            FOREIGN KEY(flat_no) REFERENCES flat(flat_no) ON UPDATE CASCADE ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS maintenance_bill (
            bill_id INTEGER PRIMARY KEY AUTOINCREMENT, flat_no TEXT NOT NULL, month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
            year INTEGER NOT NULL CHECK(year >= 2020), amount REAL NOT NULL CHECK(amount >= 0), due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'UNPAID' CHECK(status IN ('UNPAID','PARTIAL','PAID')),
            UNIQUE(flat_no, month, year), FOREIGN KEY(flat_no) REFERENCES flat(flat_no) ON UPDATE CASCADE ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS payment (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT, bill_id INTEGER NOT NULL, pay_date TEXT NOT NULL,
            amount_paid REAL NOT NULL CHECK(amount_paid > 0), mode TEXT NOT NULL CHECK(mode IN ('Cash','UPI','Card','Bank Transfer')),
            FOREIGN KEY(bill_id) REFERENCES maintenance_bill(bill_id) ON UPDATE CASCADE ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS complaint (
            complaint_id INTEGER PRIMARY KEY AUTOINCREMENT, resident_id INTEGER NOT NULL, category TEXT NOT NULL,
            date_raised TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Open' CHECK(status IN ('Open','In Progress','Resolved')),
            description TEXT NOT NULL DEFAULT '', FOREIGN KEY(resident_id) REFERENCES resident(resident_id) ON UPDATE CASCADE ON DELETE RESTRICT
        );
        CREATE VIEW IF NOT EXISTS vw_outstanding_dues AS
        SELECT b.bill_id, b.flat_no, b.month, b.year, b.amount, b.due_date, b.status,
               COALESCE(p.paid, 0) AS amount_paid, MAX(b.amount - COALESCE(p.paid, 0), 0) AS balance_due
        FROM maintenance_bill b
        LEFT JOIN (SELECT bill_id, SUM(amount_paid) AS paid FROM payment GROUP BY bill_id) p ON p.bill_id = b.bill_id
        WHERE COALESCE(p.paid, 0) < b.amount;
        CREATE VIEW IF NOT EXISTS vw_monthly_collection_summary AS
        SELECT b.year, b.month, SUM(b.amount) AS total_billed, SUM(COALESCE(p.paid, 0)) AS total_collected
        FROM maintenance_bill b
        LEFT JOIN (SELECT bill_id, SUM(amount_paid) AS paid FROM payment GROUP BY bill_id) p ON p.bill_id = b.bill_id
        GROUP BY b.year, b.month;
        """
    )
    if db.execute("SELECT COUNT(*) FROM flat").fetchone()[0] == 0:
        db.executemany("INSERT INTO flat(flat_no,wing,floor,area_sqft) VALUES(?,?,?,?)", [
            ("A-101", "A", 1, 850), ("A-202", "A", 2, 1050), ("B-103", "B", 1, 920)
        ])
        db.executemany("INSERT INTO resident(name,phone,type,flat_no) VALUES(?,?,?,?)", [
            ("Aarav Sharma", "9000000001", "Owner", "A-101"),
            ("Diya Mehta", "9000000002", "Tenant", "A-202"),
            ("Rohan Verma", "9000000003", "Owner", "B-103")
        ])
        db.executemany("INSERT INTO maintenance_bill(flat_no,month,year,amount,due_date,status) VALUES(?,?,?,?,?,?)", [
            ("A-101", 6, 2026, 4250, "2026-06-10", "PAID"),
            ("A-202", 6, 2026, 5250, "2026-06-10", "UNPAID"),
            ("B-103", 6, 2026, 4600, "2026-06-10", "PARTIAL")
        ])
        db.execute("INSERT INTO payment(bill_id,pay_date,amount_paid,mode) VALUES(1,'2026-06-08',4250,'UPI')")
        db.execute("INSERT INTO payment(bill_id,pay_date,amount_paid,mode) VALUES(3,'2026-06-09',2000,'Cash')")
        db.executemany("INSERT INTO complaint(resident_id,category,date_raised,status,description) VALUES(?,?,?,?,?)", [
            (1, "Lift", "2026-06-02", "In Progress", "Lift service requested for Wing A."),
            (3, "Plumbing", "2026-06-04", "Open", "Leak reported near the kitchen sink.")
        ])
    db.commit()
    db.close()


def status_update(db: sqlite3.Connection, bill_id: int) -> None:
    row = db.execute("SELECT b.amount, COALESCE(SUM(p.amount_paid),0) AS paid FROM maintenance_bill b LEFT JOIN payment p ON p.bill_id=b.bill_id WHERE b.bill_id=? GROUP BY b.bill_id", (bill_id,)).fetchone()
    if row:
        paid, amount = float(row["paid"]), float(row["amount"])
        status = "PAID" if paid >= amount - 0.009 else ("PARTIAL" if paid > 0 else "UNPAID")
        db.execute("UPDATE maintenance_bill SET status=? WHERE bill_id=?", (status, bill_id))


def get_paid(db: sqlite3.Connection, bill_id: int) -> float:
    row = db.execute("SELECT COALESCE(SUM(amount_paid),0) AS paid FROM payment WHERE bill_id=?", (bill_id,)).fetchone()
    return float(row["paid"])


def table(headers, rows, empty="No records found.") -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    if not rows:
        body = f'<tr><td class="empty" colspan="{len(headers)}">{esc(empty)}</td></tr>'
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def panel(title: str, subtitle: str, inner: str, symbol: str = "") -> str:
    symbol_html = f'<span class="panel-symbol">{esc(symbol)}</span>' if symbol else ""
    return f'<section class="panel"><div class="panel-header"><div><h3>{esc(title)}</h3><p>{esc(subtitle)}</p></div>{symbol_html}</div>{inner}</section>'


def field(label: str, name: str, input_type: str = "text", value: str = "", placeholder: str = "", required=True, options=None, extra="") -> str:
    req = " required" if required else ""
    if options is not None:
        choices = "".join(f'<option value="{esc(v)}" {"selected" if str(v)==str(value) else ""}>{esc(label_text)}</option>' for v, label_text in options)
        control = f'<select name="{esc(name)}"{req} {extra}>{choices}</select>'
    elif input_type == "textarea":
        control = f'<textarea name="{esc(name)}" rows="3" placeholder="{esc(placeholder)}" {extra}>{esc(value)}</textarea>'
    else:
        control = f'<input type="{esc(input_type)}" name="{esc(name)}" value="{esc(value)}" placeholder="{esc(placeholder)}"{req} {extra}>'
    return f'<label>{esc(label)}{control}</label>'


def form_card(title: str, subtitle: str, action: str, fields: str, button: str, disabled=False) -> str:
    dis = " disabled" if disabled else ""
    return f'<section class="panel form-panel"><div class="panel-header"><div><h3>{esc(title)}</h3><p>{esc(subtitle)}</p></div></div><form method="post" action="{esc(action)}" class="form-grid">{fields}<button class="button primary span-two" type="submit"{dis}>{esc(button)}</button></form></section>'


def layout(path: str, title: str, body: str, query: dict) -> str:
    nav = [("/", "◫", "Overview"), ("/flats", "▦", "Flats"), ("/residents", "♙", "Residents"), ("/bills", "▤", "Maintenance bills"), ("/payments", "₹", "Payments"), ("/complaints", "☷", "Complaints"), ("/reports", "▥", "Reports")]
    links = "".join(f'<a class="nav-link {"active" if path==href else ""}" href="{href}"><span>{icon}</span> {label}</a>' for href, icon, label in nav)
    message = query.get("message", [""])[0]
    level = query.get("level", ["success"])[0]
    flash = f'<div class="flash-stack"><div class="flash {esc(level)}">{esc(message)}<button type="button" onclick="this.parentElement.remove()" aria-label="Dismiss">×</button></div></div>' if message else ""
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} | SocietyDesk</title><link rel="stylesheet" href="/static/style.css"></head><body>
    <aside class="sidebar"><a class="brand" href="/"><span class="brand-mark">S</span><span>Society<span class="brand-light">Desk</span><small>RESIDENT & BILLING</small></span></a><div class="nav-label">WORKSPACE</div><nav>{links}</nav><div class="sidebar-bottom"><div class="avatar">KR</div><div><strong>Society Office</strong><small>Prototype workspace</small></div></div></aside>
    <main class="main-content"><header class="topbar"><div><span class="eyebrow">RESIDENTIAL SOCIETY MANAGEMENT</span><h1>{esc(title)}</h1></div><div class="topbar-right"><span class="demo-pill"><i></i> Demo data</span></div></header><section class="page-body">{flash}{body}<footer>SocietyDesk · DBMS project prototype · Demo records only</footer></section></main></body></html>'''


def render_dashboard(db):
    stats = {
        "flats": db.execute("SELECT COUNT(*) FROM flat").fetchone()[0],
        "residents": db.execute("SELECT COUNT(*) FROM resident").fetchone()[0],
        "pending": db.execute("SELECT COUNT(*) FROM maintenance_bill WHERE status!='PAID'").fetchone()[0],
        "collection": db.execute("SELECT COALESCE(SUM(amount_paid),0) FROM payment").fetchone()[0],
    }
    recent = db.execute("SELECT b.*,f.wing,COALESCE((SELECT SUM(p.amount_paid) FROM payment p WHERE p.bill_id=b.bill_id),0) AS paid FROM maintenance_bill b JOIN flat f ON f.flat_no=b.flat_no ORDER BY b.year DESC,b.month DESC,b.bill_id DESC LIMIT 6").fetchall()
    rows = [[f'<strong>{esc(b["flat_no"])}</strong><small class="cell-sub">Wing {esc(b["wing"])}</small>', f'{b["month"]:02d}/{b["year"]}', money(b["amount"]), money(b["paid"]), f'<span class="status {b["status"].lower()}">{esc(b["status"])}</span>'] for b in recent]
    stat_items = [("▦", "blue", "PROPERTY", stats["flats"], "Total flats", "Registered units"), ("♙", "violet", "PEOPLE", stats["residents"], "Residents", "Owners and tenants"), ("▤", "amber", "BILLING", stats["pending"], "Pending bills", "Unpaid or part-paid"), ("₹", "green", "COLLECTION", money(stats["collection"]), "Payments recorded", "Across demo records")]
    cards = "".join(f'<article class="stat-card"><div class="stat-top"><span class="stat-icon {cls}">{icon}</span><span class="stat-tag">{tag}</span></div><div class="stat-number">{esc(num)}</div><div class="stat-label">{label}</div><div class="stat-foot">{foot}</div></article>' for icon,cls,tag,num,label,foot in stat_items)
    quick = ''.join(f'<a class="action-row" href="{href}"><span class="action-icon">{icon}</span><span><strong>{label}</strong><small>{sub}</small></span><b>→</b></a>' for href,icon,label,sub in [('/residents','♙','Add a resident','Record owner or tenant details'),('/payments','₹','Record a payment','Update outstanding maintenance dues'),('/complaints','☷','Track a complaint','Manage resident service requests'),('/reports','▥','Review due reports','View outstanding balances and collections')])
    return f'''<div class="welcome-row"><div><h2>Your society, at a glance.</h2><p>Manage flats, residents, monthly maintenance, payments and service complaints from one place.</p></div><a class="button primary" href="/bills">＋ Generate bills</a></div><div class="stat-grid">{cards}</div><div class="overview-grid"><section class="panel"><div class="panel-header"><div><h3>Recent maintenance bills</h3><p>Latest generated bills and current payment status</p></div><a class="text-link" href="/bills">View all →</a></div>{table(['Flat','Billing period','Amount','Paid','Status'],rows,'No bills yet.')}</section><section class="panel quick-panel"><div class="panel-header"><div><h3>Quick actions</h3><p>Common society-office tasks</p></div></div>{quick}</section></div><div class="notice-strip"><span class="notice-icon">i</span><span><strong>Project note</strong> The app uses a local SQLite database for a quick demo. A MySQL schema with payment-status triggers is included in <code>db/schema_mysql.sql</code>.</span></div>'''


def render_flats(db):
    if db.execute("SELECT COUNT(*) FROM flat").fetchone()[0]: pass
    items = db.execute("SELECT f.*,COUNT(r.resident_id) AS residents FROM flat f LEFT JOIN resident r ON r.flat_no=f.flat_no GROUP BY f.flat_no ORDER BY f.wing,f.floor,f.flat_no").fetchall()
    fields = field("Flat number *", "flat_no", placeholder="e.g. A-101") + field("Wing *", "wing", placeholder="e.g. A") + field("Floor *", "floor", "number", "1", extra='min="0"') + field("Area (sq. ft.) *", "area_sqft", "number", "850", extra='min="1" step="0.01"')
    rows = [[f'<strong>{esc(r["flat_no"])}</strong>', f'Wing {esc(r["wing"])} · Floor {r["floor"]}', f'{r["area_sqft"]:,.0f} sq. ft.', str(r["residents"])] for r in items]
    return f'<div class="page-intro"><div><h2>Property directory</h2><p>Maintain one record per flat, including its wing, floor and area.</p></div><span class="count-chip">{len(items)} flats</span></div><div class="content-grid">{form_card("Add a flat","Fields marked * are required","/flats",fields,"Add flat")}{panel("Registered flats","Flat details and linked resident count",table(["Flat","Wing / floor","Area","Residents"],rows,"No flats added."))}</div>'


def render_residents(db):
    residents = db.execute("SELECT r.*,f.wing,f.floor FROM resident r JOIN flat f ON f.flat_no=r.flat_no ORDER BY r.resident_id DESC").fetchall()
    flats = db.execute("SELECT flat_no FROM flat ORDER BY flat_no").fetchall()
    flat_opts = [(r["flat_no"],r["flat_no"]) for r in flats]
    fields = field("Full name *", "name", placeholder="Resident name") + field("Phone number *", "phone", placeholder="10-digit phone") + field("Resident type *", "type", options=[("Owner","Owner"),("Tenant","Tenant")]) + field("Flat number *", "flat_no", options=flat_opts)
    rows = [[f'<strong>{esc(r["name"])}</strong><small class="cell-sub">ID {r["resident_id"]}</small>', esc(r["flat_no"]), f'<span class="type-chip">{esc(r["type"])}</span>', esc(r["phone"])] for r in residents]
    return f'<div class="page-intro"><div><h2>Resident directory</h2><p>Keep contact details and owner / tenant status linked to each flat.</p></div><span class="count-chip">{len(residents)} residents</span></div><div class="content-grid">{form_card("Register a resident","Choose an existing flat","/residents",fields,"Add resident",not bool(flats))}{panel("Registered residents","Resident information stored in the database",table(["Name","Flat","Type","Phone"],rows,"No residents added."))}</div>'


def render_bills(db):
    rows = db.execute("SELECT b.*,COALESCE((SELECT SUM(p.amount_paid) FROM payment p WHERE p.bill_id=b.bill_id),0) AS paid FROM maintenance_bill b ORDER BY b.year DESC,b.month DESC,b.flat_no").fetchall()
    bills_table = [[f'<strong>#{b["bill_id"]} · {esc(b["flat_no"])}</strong>',f'{b["month"]:02d}/{b["year"]}',esc(b["due_date"]),money(b["amount"]),money(b["paid"]),money(max(0,b["amount"]-b["paid"])),f'<span class="status {b["status"].lower()}">{esc(b["status"])}</span>'] for b in rows]
    months = [(str(m), f'{m:02d} - {date(2026,m,1).strftime("%B")}') for m in range(1,13)]
    fields = field("Month", "month", options=months, value="10") + field("Year", "year", "number", "2026", extra='min="2020"') + field("Rate per sq. ft. (₹)", "rate", "number", "5.00", extra='min="0" step="0.01"') + field("Due date", "due_date", "date", "2026-10-25")
    gen = form_card("Generate monthly bills","Rate is a configurable demo input, not a fixed rate from the review presentation.","/bills",fields,"Generate bills")
    return f'<div class="page-intro"><div><h2>Maintenance billing</h2><p>Generate one bill per flat and month. Duplicate bills are automatically skipped.</p></div><span class="count-chip">{len(rows)} bills</span></div>{gen}{panel("All maintenance bills","Payment status updates as payments are recorded",table(["Bill / Flat","Period","Due date","Bill amount","Paid","Balance","Status"],bills_table,"No bills yet."))}'


def render_payments(db):
    outstanding = db.execute("SELECT b.*,COALESCE(SUM(p.amount_paid),0) AS paid FROM maintenance_bill b LEFT JOIN payment p ON p.bill_id=b.bill_id GROUP BY b.bill_id HAVING b.amount-paid>0.009 ORDER BY b.year DESC,b.month DESC,b.flat_no").fetchall()
    opts = [(str(b["bill_id"]),f'#{b["bill_id"]} · {b["flat_no"]} · {b["month"]:02d}/{b["year"]} · Balance {money(b["amount"]-b["paid"])}') for b in outstanding]
    fields = '<div class="span-two">'+field("Bill / flat *","bill_id",options=opts)+"</div>" + field("Amount paid (₹) *", "amount_paid", "number", placeholder="1000", extra='min="0.01" step="0.01"') + field("Payment date *", "pay_date", "date", date.today().isoformat()) + '<div class="span-two">'+field("Payment method *","mode",options=[("UPI","UPI"),("Cash","Cash"),("Card","Card"),("Bank Transfer","Bank Transfer")])+"</div>"
    payments = db.execute("SELECT p.*,b.flat_no,b.month,b.year FROM payment p JOIN maintenance_bill b ON b.bill_id=p.bill_id ORDER BY p.pay_date DESC,p.payment_id DESC LIMIT 30").fetchall()
    rows = [[f'<strong>#{p["payment_id"]}</strong>',esc(p["flat_no"]),esc(p["pay_date"]),esc(p["mode"]),money(p["amount_paid"])] for p in payments]
    form = form_card("Record a payment","Full and partial payments are supported; overpayments are blocked.","/payments",fields,"Record payment",not bool(outstanding))
    return f'<div class="page-intro"><div><h2>Payment register</h2><p>Record full or partial payments against an existing maintenance bill.</p></div><span class="count-chip">{len(payments)} recent payments</span></div><div class="content-grid">{form}{panel("Recent transactions","Recorded payments and their billing period",table(["Payment","Flat","Date","Method","Amount"],rows,"No payments recorded."))}</div>'


def render_complaints(db):
    complaint_rows = db.execute("SELECT c.*,r.name,r.flat_no FROM complaint c JOIN resident r ON r.resident_id=c.resident_id ORDER BY CASE c.status WHEN 'Open' THEN 0 WHEN 'In Progress' THEN 1 ELSE 2 END,c.date_raised DESC").fetchall()
    residents = db.execute("SELECT resident_id,name,flat_no FROM resident ORDER BY name").fetchall()
    resident_opts = [(str(r["resident_id"]),f'{r["name"]} · {r["flat_no"]}') for r in residents]
    fields = '<div class="span-two">'+field("Resident *","resident_id",options=resident_opts)+"</div>" + field("Category *","category",options=[("Plumbing","Plumbing"),("Lift","Lift"),("Electrical","Electrical"),("Security","Security"),("Cleaning","Cleaning"),("Other","Other")]) + field("Date raised *","date_raised","date",date.today().isoformat()) + '<div class="span-two">'+field("Description","description","textarea",value="",placeholder="Briefly describe the issue",required=False)+"</div>"
    new_form = form_card("New complaint","Link each complaint to a registered resident.","/complaints",fields,"Submit complaint",not bool(residents))
    complaint_html=[]
    for c in complaint_rows:
        opts = [(s,s) for s in ("Open","In Progress","Resolved")]
        select = field("Status","status",options=opts,value=c["status"],required=True).replace("<label>Status</label>","").replace("<label>Status","")
        complaint_html.append(f'''<article class="complaint-item"><div class="complaint-head"><div><span class="type-chip">{esc(c["category"])}</span><strong>{esc(c["flat_no"])} · {esc(c["name"])}</strong></div><small>{esc(c["date_raised"])}</small></div><p>{esc(c["description"] or "No additional description provided.")}</p><form method="post" action="/complaints" class="inline-form"><input type="hidden" name="action" value="update"><input type="hidden" name="complaint_id" value="{c["complaint_id"]}"><select name="status" aria-label="Complaint status">{''.join(f'<option {"selected" if s==c["status"] else ""}>{s}</option>' for s in ("Open","In Progress","Resolved"))}</select><button class="button secondary small" type="submit">Update status</button></form></article>''')
    listing = '<div class="complaint-list">'+("".join(complaint_html) if complaint_html else '<div class="empty">No complaints have been registered.</div>')+'</div>'
    return f'<div class="page-intro"><div><h2>Resident service requests</h2><p>Log complaints and track them from open to resolved.</p></div><span class="count-chip">{len(complaint_rows)} complaints</span></div><div class="content-grid">{new_form}{panel("Complaint tracker","Update service request status",listing)}</div>'


def render_reports(db):
    rows = db.execute("SELECT b.*,COALESCE(SUM(p.amount_paid),0) AS paid FROM maintenance_bill b LEFT JOIN payment p ON p.bill_id=b.bill_id GROUP BY b.bill_id HAVING b.amount-paid>0.009 ORDER BY b.amount-paid DESC").fetchall()
    dues = [[f'<strong>{esc(b["flat_no"])}</strong>',f'{b["month"]:02d}/{b["year"]}',esc(b["due_date"]),money(b["amount"]),money(b["paid"]),f'<strong>{money(b["amount"]-b["paid"])}</strong>',f'<span class="status {b["status"].lower()}">{esc(b["status"])}</span>'] for b in rows]
    collections = db.execute("SELECT b.month,b.year,SUM(b.amount) AS billed,SUM(COALESCE(p.paid,0)) AS collected FROM maintenance_bill b LEFT JOIN (SELECT bill_id,SUM(amount_paid) AS paid FROM payment GROUP BY bill_id) p ON p.bill_id=b.bill_id GROUP BY b.year,b.month ORDER BY b.year DESC,b.month DESC").fetchall()
    collect_rows = [[f'<strong>{r["month"]:02d}/{r["year"]}</strong>',money(r["billed"]),money(r["collected"]),f'{(r["collected"] / r["billed"] * 100):.1f}%' if r["billed"] else "—"] for r in collections]
    return f'<div class="page-intro"><div><h2>Billing and collection reports</h2><p>Identify outstanding balances and compare bills with receipts.</p></div><span class="count-chip">Live database report</span></div>{panel("Outstanding dues","Any bill where the paid amount is less than the billed amount",table(["Flat","Period","Due date","Billed","Paid","Outstanding","Status"],dues,"No outstanding dues."),"₹")}<div class="report-panel">{panel("Monthly collection summary","Aggregated bill value and recorded payments per month",table(["Period","Total billed","Total collected","Collection rate"],collect_rows,"No monthly billing information available."))}</div>'


class Handler(BaseHTTPRequestHandler):
    server_version = "SocietyDesk/1.0"

    def log_message(self, fmt, *args):
        # Keep terminal output readable while demonstrating locally.
        print("[SocietyDesk] " + fmt % args)

    def send_html(self, content: str, status=200):
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def redirect_message(self, path: str, message: str, level="success"):
        from urllib.parse import quote
        self.send_response(303)
        self.send_header("Location", f'{path}?message={quote(message)}&level={quote(level)}')
        self.end_headers()

    def form_data(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        values = parse_qs(raw, keep_blank_values=True)
        return {key: vals[0] for key, vals in values.items()}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/static/style.css":
            if CSS_PATH.exists():
                data = CSS_PATH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/css; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404)
            return
        if path == "/health":
            self.send_html('{"status":"ok","application":"Residential Society Billing System"}')
            return
        db = connect()
        titles = {"/":"Overview","/flats":"Flats","/residents":"Residents","/bills":"Maintenance bills","/payments":"Payments","/complaints":"Complaints","/reports":"Reports"}
        if path == "/": body = render_dashboard(db)
        elif path == "/flats": body = render_flats(db)
        elif path == "/residents": body = render_residents(db)
        elif path == "/bills": body = render_bills(db)
        elif path == "/payments": body = render_payments(db)
        elif path == "/complaints": body = render_complaints(db)
        elif path == "/reports": body = render_reports(db)
        else:
            db.close()
            self.send_error(404, "Page not found")
            return
        db.close()
        self.send_html(layout(path, titles[path], body, query))

    def do_POST(self):
        path = urlparse(self.path).path
        data = self.form_data()
        db = connect()
        try:
            if path == "/flats":
                flat_no = data.get("flat_no", "").strip().upper()
                wing = data.get("wing", "").strip().upper()
                floor = int(data.get("floor", ""))
                area = float(data.get("area_sqft", ""))
                if not flat_no or not wing or floor < 0 or area <= 0: raise ValueError("Enter valid flat details and a positive area.")
                db.execute("INSERT INTO flat(flat_no,wing,floor,area_sqft) VALUES(?,?,?,?)", (flat_no,wing,floor,area))
                db.commit(); self.redirect_message(path, f"Flat {flat_no} added successfully.")
            elif path == "/residents":
                name, phone, kind, flat_no = (data.get(k, "").strip() for k in ("name","phone","type","flat_no"))
                if not name or not phone or kind not in ("Owner","Tenant") or not flat_no: raise ValueError("Enter valid resident details and select a flat.")
                db.execute("INSERT INTO resident(name,phone,type,flat_no) VALUES(?,?,?,?)", (name,phone,kind,flat_no))
                db.commit(); self.redirect_message(path, f"Resident {name} added successfully.")
            elif path == "/bills":
                month, year, rate = int(data.get("month", "")), int(data.get("year", "")), float(data.get("rate", ""))
                due_date = data.get("due_date", "").strip()
                if month not in range(1,13) or year < 2020 or rate < 0 or not due_date: raise ValueError("Enter a valid month, year, rate and due date.")
                flats = db.execute("SELECT flat_no,area_sqft FROM flat").fetchall()
                created = 0
                for flat in flats:
                    cur = db.execute("INSERT OR IGNORE INTO maintenance_bill(flat_no,month,year,amount,due_date,status) VALUES(?,?,?,?,?,'UNPAID')", (flat["flat_no"],month,year,round(float(flat["area_sqft"])*rate,2),due_date))
                    created += cur.rowcount
                db.commit(); self.redirect_message(path, f"Generated {created} bill(s). Existing bills for that flat/month were skipped.")
            elif path == "/payments":
                bill_id = int(data.get("bill_id", "")); amount = round(float(data.get("amount_paid", "")),2)
                pay_date, mode = data.get("pay_date", "").strip(), data.get("mode", "")
                if amount <= 0 or not pay_date or mode not in ("Cash","UPI","Card","Bank Transfer"): raise ValueError("Enter a valid amount, payment date and method.")
                bill = db.execute("SELECT amount FROM maintenance_bill WHERE bill_id=?", (bill_id,)).fetchone()
                if bill is None: raise ValueError("Select a valid bill.")
                balance = round(float(bill["amount"])-get_paid(db,bill_id),2)
                if amount > balance + 0.001: raise ValueError(f"Payment exceeds outstanding balance ({money(balance)}).")
                db.execute("INSERT INTO payment(bill_id,pay_date,amount_paid,mode) VALUES(?,?,?,?)", (bill_id,pay_date,amount,mode))
                status_update(db,bill_id); db.commit(); self.redirect_message(path,"Payment recorded and bill status updated.")
            elif path == "/complaints":
                if data.get("action") == "update":
                    cid, status = int(data.get("complaint_id", "")), data.get("status", "")
                    if status not in ("Open","In Progress","Resolved"): raise ValueError("Choose a valid complaint status.")
                    db.execute("UPDATE complaint SET status=? WHERE complaint_id=?",(status,cid)); db.commit()
                    self.redirect_message(path,"Complaint status updated.")
                else:
                    resident_id = int(data.get("resident_id", "")); category = data.get("category", "").strip()
                    raised = data.get("date_raised", "").strip(); description=data.get("description", "").strip()
                    if not category or not raised: raise ValueError("Choose a category and date for the complaint.")
                    db.execute("INSERT INTO complaint(resident_id,category,date_raised,status,description) VALUES(?,?,?,'Open',?)",(resident_id,category,raised,description))
                    db.commit(); self.redirect_message(path,"Complaint submitted.")
            else:
                self.redirect_message("/", "Unknown form action.", "error")
        except (ValueError, sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
            db.rollback()
            self.redirect_message(path if path in ("/flats","/residents","/bills","/payments","/complaints") else "/", str(exc) or "Please check the submitted information.", "error")
        finally:
            db.close()


def main():
    init_db()
    port = int(os.environ.get("SOCIETY_PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("\nSocietyDesk prototype is running.")
    print(f"Open http://127.0.0.1:{port} in your browser. Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping SocietyDesk.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
