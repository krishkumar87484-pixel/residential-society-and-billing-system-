# Five-minute video demonstration script

**Project:** Design and Implementation of a Database Management System for a Residential Society  
**Presenter:** Krish | Roll No. 25WU0102333 | Team AIML Rhinos | Project 42  
**Target length:** approximately 5 minutes

## 0:00-0:30 - Introduction

"Hello ma'am. This is our DBMS project, the Residential Society Resident and Maintenance Billing System. The purpose is to keep flat and resident records together, generate monthly maintenance bills, record payments, track complaints and quickly identify outstanding dues. The repository is organized to hold all three project presentations alongside the database schemas and submission documents."

**On screen:** show the dashboard and the project title.

## 0:30-1:10 - Dashboard and database overview

"The dashboard gives a quick summary of flats, residents, pending bills and recorded payments. The prototype uses five connected relational tables: FLAT, RESIDENT, MAINTENANCE_BILL, PAYMENT and COMPLAINT. Primary keys identify records, while foreign keys connect residents to flats, bills to flats, payments to bills and complaints to residents."

**On screen:** point to the summary cards, then briefly show the README or MySQL schema.

## 1:10-1:50 - Flats and residents

"In the Flats section, the office can register a flat with its wing, floor and area. In Residents, we can register an owner or tenant and link them to an existing flat. Keeping these records in related tables reduces repeated data and makes it easier to query residents by flat."

**On screen:** add one clearly fictional test flat, then add a fictional resident and show the new rows. Avoid showing real personal data.

## 1:50-2:40 - Monthly billing

"In Maintenance Bills, we select a month, year, due date and a configurable sample rate per square foot. The prototype calculates the bill from each flat's area and creates one bill per flat for that month. A unique constraint prevents a duplicate bill for the same flat and billing period. The rate shown is only a demo value because the review presentation did not specify an official rate."

**On screen:** generate bills for a month that does not already exist in the sample dataset and show the results.

## 2:40-3:30 - Payments and status tracking

"The Payments section records the payment date, method and amount. The system supports partial payments and checks that a payment does not exceed the outstanding balance. After recording a payment, the bill status is recalculated as UNPAID, PARTIAL or PAID. The MySQL schema also includes triggers for recalculating the bill status when a payment is inserted, updated or deleted."

**On screen:** pay part of a test bill, show PARTIAL, then pay the remaining balance and show PAID. If there is not enough time, use one already-part-paid sample bill.

## 3:30-4:10 - Complaints and reports

"Residents' service issues can be registered under categories such as plumbing, lift or electrical. The society office can move a complaint from Open to In Progress and then Resolved. Reports show outstanding balances and compare the total billed amount with payments received for each month. This supports faster follow-up with residents who still have dues."

**On screen:** add a complaint, update its status and open Reports.

## 4:10-4:40 - Technology and repository

"The local prototype runs with Python's standard library and SQLite so it can be demonstrated without extra package installation. We have separately included a MySQL 8 schema with primary keys, foreign keys, constraints and payment triggers for the DBMS implementation. The README explains how to run the demo, and the repository contains the presentation and submission documents."

**On screen:** show `README.md`, `db/schema_mysql.sql` and the `presentations/` folder.

## 4:40-5:00 - Conclusion

"To conclude, the system brings flat details, resident records, maintenance billing, payment tracking and complaints into one structured database workflow. It reduces manual calculations and makes due reports easier to generate. Thank you."

**On screen:** return to the dashboard and end recording.

## Recording checklist

- Start with the browser already open and the prototype running.
- Use fictional test data; do not show real phone numbers or private resident data.
- Increase browser zoom if the tables look small in the recording.
- Avoid long pauses while typing; prepare the names and sample values in advance.
- Check the finished video duration, sound, readability and public share link before uploading.
