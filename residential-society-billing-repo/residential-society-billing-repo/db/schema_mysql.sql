-- Residential Society Billing System - MySQL 8+
-- Source-aligned tables: FLAT, RESIDENT, MAINTENANCE_BILL, PAYMENT, COMPLAINT.
CREATE DATABASE IF NOT EXISTS residential_society;
USE residential_society;

CREATE TABLE IF NOT EXISTS FLAT (
    flat_no VARCHAR(20) PRIMARY KEY,
    wing VARCHAR(10) NOT NULL,
    floor INT NOT NULL,
    area_sqft DECIMAL(10,2) NOT NULL,
    CHECK (floor >= 0),
    CHECK (area_sqft > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS RESIDENT (
    resident_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    type ENUM('Owner', 'Tenant') NOT NULL,
    flat_no VARCHAR(20) NOT NULL,
    CONSTRAINT fk_resident_flat FOREIGN KEY (flat_no) REFERENCES FLAT(flat_no)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS MAINTENANCE_BILL (
    bill_id INT AUTO_INCREMENT PRIMARY KEY,
    flat_no VARCHAR(20) NOT NULL,
    month TINYINT NOT NULL,
    year SMALLINT NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    due_date DATE NOT NULL,
    status ENUM('UNPAID', 'PARTIAL', 'PAID') NOT NULL DEFAULT 'UNPAID',
    CONSTRAINT uq_bill_flat_period UNIQUE (flat_no, month, year),
    CONSTRAINT fk_bill_flat FOREIGN KEY (flat_no) REFERENCES FLAT(flat_no)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CHECK (month BETWEEN 1 AND 12),
    CHECK (amount >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS PAYMENT (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    bill_id INT NOT NULL,
    pay_date DATE NOT NULL,
    amount_paid DECIMAL(12,2) NOT NULL,
    mode ENUM('Cash', 'UPI', 'Card', 'Bank Transfer') NOT NULL,
    CONSTRAINT fk_payment_bill FOREIGN KEY (bill_id) REFERENCES MAINTENANCE_BILL(bill_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CHECK (amount_paid > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS COMPLAINT (
    complaint_id INT AUTO_INCREMENT PRIMARY KEY,
    resident_id INT NOT NULL,
    category VARCHAR(60) NOT NULL,
    date_raised DATE NOT NULL,
    status ENUM('Open', 'In Progress', 'Resolved') NOT NULL DEFAULT 'Open',
    description VARCHAR(500) NOT NULL DEFAULT '',
    CONSTRAINT fk_complaint_resident FOREIGN KEY (resident_id) REFERENCES RESIDENT(resident_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Trigger approach used in the MySQL schema: recalculate the affected bill status
-- when a payment is inserted, updated, or deleted.
DROP TRIGGER IF EXISTS trg_payment_after_insert;
DROP TRIGGER IF EXISTS trg_payment_after_update;
DROP TRIGGER IF EXISTS trg_payment_after_delete;
DELIMITER $$
CREATE TRIGGER trg_payment_after_insert AFTER INSERT ON PAYMENT
FOR EACH ROW
BEGIN
    UPDATE MAINTENANCE_BILL b
    SET b.status = CASE
        WHEN (SELECT COALESCE(SUM(p.amount_paid), 0) FROM PAYMENT p WHERE p.bill_id = NEW.bill_id) >= b.amount THEN 'PAID'
        WHEN (SELECT COALESCE(SUM(p.amount_paid), 0) FROM PAYMENT p WHERE p.bill_id = NEW.bill_id) > 0 THEN 'PARTIAL'
        ELSE 'UNPAID' END
    WHERE b.bill_id = NEW.bill_id;
END$$

CREATE TRIGGER trg_payment_after_update AFTER UPDATE ON PAYMENT
FOR EACH ROW
BEGIN
    UPDATE MAINTENANCE_BILL b
    SET b.status = CASE
        WHEN (SELECT COALESCE(SUM(p.amount_paid), 0) FROM PAYMENT p WHERE p.bill_id = NEW.bill_id) >= b.amount THEN 'PAID'
        WHEN (SELECT COALESCE(SUM(p.amount_paid), 0) FROM PAYMENT p WHERE p.bill_id = NEW.bill_id) > 0 THEN 'PARTIAL'
        ELSE 'UNPAID' END
    WHERE b.bill_id = NEW.bill_id;
    IF OLD.bill_id <> NEW.bill_id THEN
        UPDATE MAINTENANCE_BILL b
        SET b.status = CASE
            WHEN (SELECT COALESCE(SUM(p.amount_paid), 0) FROM PAYMENT p WHERE p.bill_id = OLD.bill_id) >= b.amount THEN 'PAID'
            WHEN (SELECT COALESCE(SUM(p.amount_paid), 0) FROM PAYMENT p WHERE p.bill_id = OLD.bill_id) > 0 THEN 'PARTIAL'
            ELSE 'UNPAID' END
        WHERE b.bill_id = OLD.bill_id;
    END IF;
END$$

CREATE TRIGGER trg_payment_after_delete AFTER DELETE ON PAYMENT
FOR EACH ROW
BEGIN
    UPDATE MAINTENANCE_BILL b
    SET b.status = CASE
        WHEN (SELECT COALESCE(SUM(p.amount_paid), 0) FROM PAYMENT p WHERE p.bill_id = OLD.bill_id) >= b.amount THEN 'PAID'
        WHEN (SELECT COALESCE(SUM(p.amount_paid), 0) FROM PAYMENT p WHERE p.bill_id = OLD.bill_id) > 0 THEN 'PARTIAL'
        ELSE 'UNPAID' END
    WHERE b.bill_id = OLD.bill_id;
END$$
DELIMITER ;


-- Views used by the society-office reports.
CREATE OR REPLACE VIEW vw_outstanding_dues AS
SELECT b.bill_id, b.flat_no, b.month, b.year, b.amount, b.due_date, b.status,
       COALESCE(p.paid, 0) AS amount_paid,
       GREATEST(b.amount - COALESCE(p.paid, 0), 0) AS balance_due
FROM MAINTENANCE_BILL b
LEFT JOIN (SELECT bill_id, SUM(amount_paid) AS paid FROM PAYMENT GROUP BY bill_id) p
       ON p.bill_id = b.bill_id
WHERE COALESCE(p.paid, 0) < b.amount;

CREATE OR REPLACE VIEW vw_monthly_collection_summary AS
SELECT b.year, b.month, SUM(b.amount) AS total_billed,
       SUM(COALESCE(p.paid, 0)) AS total_collected
FROM MAINTENANCE_BILL b
LEFT JOIN (SELECT bill_id, SUM(amount_paid) AS paid FROM PAYMENT GROUP BY bill_id) p
       ON p.bill_id = b.bill_id
GROUP BY b.year, b.month;

-- Example report: unpaid/part-paid bills (matching the review presentation's query goal).
SELECT f.flat_no, r.name, b.month, b.year, b.amount, b.status
FROM MAINTENANCE_BILL b
JOIN FLAT f ON f.flat_no = b.flat_no
LEFT JOIN RESIDENT r ON r.flat_no = f.flat_no
WHERE b.status <> 'PAID'
ORDER BY b.year DESC, b.month DESC, f.flat_no;
