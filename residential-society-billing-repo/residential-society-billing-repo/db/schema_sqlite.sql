-- SQLite schema used by the zero-configuration Flask demo.
-- The MySQL production-style schema and payment triggers are in schema_mysql.sql.
PRAGMA foreign_keys = ON;
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
       COALESCE(p.paid, 0) AS amount_paid,
       MAX(b.amount - COALESCE(p.paid, 0), 0) AS balance_due
FROM maintenance_bill b
LEFT JOIN (SELECT bill_id, SUM(amount_paid) AS paid FROM payment GROUP BY bill_id) p ON p.bill_id = b.bill_id
WHERE COALESCE(p.paid, 0) < b.amount;

CREATE VIEW IF NOT EXISTS vw_monthly_collection_summary AS
SELECT b.year, b.month, SUM(b.amount) AS total_billed, SUM(COALESCE(p.paid, 0)) AS total_collected
FROM maintenance_bill b
LEFT JOIN (SELECT bill_id, SUM(amount_paid) AS paid FROM payment GROUP BY bill_id) p ON p.bill_id = b.bill_id
GROUP BY b.year, b.month;
