#!/usr/bin/env python3
"""Smoke test the HTTP prototype using only Python's standard library."""
from __future__ import annotations
import http.client
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]

def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main() -> int:
    port = free_port()
    with tempfile.TemporaryDirectory(prefix="society-smoke-") as tmp:
        env = os.environ.copy()
        env["SOCIETY_PORT"] = str(port)
        env["SOCIETY_DB_PATH"] = str(Path(tmp) / "test.db")
        proc = subprocess.Popen([sys.executable, str(ROOT / "run.py")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(60):
                try:
                    with urlopen(base + "/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(0.15)
            else:
                print("FAIL: server did not start")
                return 1
            checks = {
                "/": b"Your society, at a glance.",
                "/flats": b"Property directory",
                "/residents": b"Resident directory",
                "/bills": b"Maintenance billing",
                "/payments": b"Payment register",
                "/complaints": b"Resident service requests",
                "/reports": b"Billing and collection reports",
                "/static/style.css": b"--navy",
            }
            for path, marker in checks.items():
                with urlopen(base + path, timeout=3) as response:
                    payload = response.read()
                    if response.status != 200 or marker not in payload:
                        print(f"FAIL: {path} returned an unexpected response")
                        return 1
                print(f"PASS: {path}")
            def post(path: str, body: str):
                raw = body.encode("utf-8")
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
                conn.request("POST", path, body=raw, headers={"Content-Type":"application/x-www-form-urlencoded", "Content-Length":str(len(raw))})
                resp = conn.getresponse()
                result = (resp.status, resp.getheader("Location", ""), resp.read())
                conn.close()
                return result

            status, location, _ = post("/flats", "flat_no=C-909&wing=C&floor=9&area_sqft=900")
            if status != 303 or "Flat%20C-909" not in location:
                print("FAIL: flat creation did not redirect with a success message")
                return 1
            with urlopen(base + "/flats", timeout=3) as response:
                if b"C-909" not in response.read():
                    print("FAIL: newly added flat was not displayed")
                    return 1
            print("PASS: POST /flats creates and persists a flat")

            status, location, _ = post("/bills", "month=10&year=2026&rate=1&due_date=2026-10-25")
            if status != 303 or "Generated%204%20bill" not in location:
                print("FAIL: monthly bill generation did not create expected bills")
                return 1
            db_path = Path(env["SOCIETY_DB_PATH"])
            with sqlite3.connect(db_path) as db:
                bill = db.execute("SELECT bill_id,amount,status FROM maintenance_bill WHERE flat_no='A-101' AND month=10 AND year=2026").fetchone()
                if not bill or bill[1] != 850 or bill[2] != "UNPAID":
                    print("FAIL: generated monthly bill has unexpected values")
                    return 1
                bill_id = bill[0]
            print("PASS: monthly billing calculates amounts from area and rate")

            status, location, _ = post("/payments", f"bill_id={bill_id}&amount_paid=200&pay_date=2026-10-13&mode=UPI")
            with sqlite3.connect(db_path) as db:
                state = db.execute("SELECT status FROM maintenance_bill WHERE bill_id=?", (bill_id,)).fetchone()[0]
            if status != 303 or state != "PARTIAL":
                print("FAIL: partial payment did not update bill status")
                return 1
            status, location, _ = post("/payments", f"bill_id={bill_id}&amount_paid=700&pay_date=2026-10-13&mode=UPI")
            if status != 303 or "level=error" not in location:
                print("FAIL: overpayment was not blocked")
                return 1
            status, location, _ = post("/payments", f"bill_id={bill_id}&amount_paid=650&pay_date=2026-10-13&mode=UPI")
            with sqlite3.connect(db_path) as db:
                state = db.execute("SELECT status FROM maintenance_bill WHERE bill_id=?", (bill_id,)).fetchone()[0]
            if status != 303 or state != "PAID":
                print("FAIL: final payment did not update bill status to PAID")
                return 1
            print("PASS: partial/full payments update status and overpayment is rejected")

            status, _, _ = post("/complaints", "resident_id=1&category=Electrical&date_raised=2026-10-13&description=Smoke+test+complaint")
            with sqlite3.connect(db_path) as db:
                complaint_count = db.execute("SELECT COUNT(*) FROM complaint WHERE category='Electrical'").fetchone()[0]
            if status != 303 or complaint_count != 1:
                print("FAIL: complaint creation failed")
                return 1
            print("PASS: complaint form stores resident service requests")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
    print("All smoke tests passed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
