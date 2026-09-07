# Pointlabs One — project reference

## Source brief

Build Pointlabs One, a mobile-first, installable PWA for Pointlabs HR. It must provide an employee database, secure login and role-based access, employee-document storage, leave requests and approvals, HR notifications, birthday email workflows, dashboards, reports, and data administration.

### Required capabilities

- Roles are data-configured, not hard-coded. Admins manage users, roles, employee details, and reporting relationships. Reporting officers can view team/leave information but cannot add, edit, or delete HR data. Everyone can see today's employees on leave.
- Employees submit leave requests. Their reporting officer receives an in-app and email notification and can approve, reject, or return the request for more information. Approved requests notify `askhr@pointlabs.ai`; rejection/return notifies the employee.
- The admin dashboard shows leave data and balances, upcoming and current leave, HR data, upcoming birthdays, and an action to record whether a gift voucher is included. Birthday emails are sent on the birthday; an admin reminder appears three days before. Voucher emails may include a code and/or attached voucher image.
- Accounts are created with an employee code, user ID, registered email, temporary password, and a compulsory first-login password change. Password recovery uses username plus registered email and an emailed OTP.
- Employee records include identity, employment, reporting, contact, banking, leave-balance, and document information described in the source brief. Employees may update only their profile image, phone number, and personal address; admins control all other fields.
- Store uploaded images compressed and converted to WebP. Accept images and PDFs only; PDFs are stored uncompressed.
- Reports require filtering, pagination where needed, and Excel export.
- Use Python with HTML/CSS/JavaScript. Use SQLite for local testing and MySQL in deployment. Email credentials will be supplied in environment variables.
- Support dark and light themes, using the supplied `logo1.jpg`, `logo2.png`, and `icon.png`; base visual palette: light green, gold, and white.

## Spreadsheet-reference decisions

`Staff Info.xlsx` is not an employee-data import. It is solely the source for the designation catalog and for identifying which designations may act as reporting officers. Individual employee details will be created and completed manually by an administrator after the system is delivered. Missing spreadsheet data must not block development.

The initial test data will contain only an administrator account with a temporary password. Do not create employee accounts or employee records from the spreadsheet. The initial account may be used to test login; the full OTP-based password-reset flow will be added once email configuration is connected.

The initial test administrator username is `admin`. Its temporary development password is user-supplied and must be configured securely during local setup; do not store it in this reference document or commit it to source control.

When later creating a user whose employee ID is unavailable, an administrator will assign a temporary employee ID. `Dilip DS` and `Dilip D S` are the same person. Date of joining and every other missing employee field will be entered manually by the administrator. New fields not present in the spreadsheet may be added when requested.

### Designation catalog

The initial catalog has 33 designations. Each designation has an `is_reporting_officer_designation` setting. The following eleven are initially marked true because people holding them are referenced as reporting managers in the spreadsheet:

- Chief Executive Officer
- Chief Finance & Compliance Officer
- Chief Technology & Innovation Officer
- Head of Engineering
- Head of Operations
- Head of Product
- Head – Global Partnerships & Alliances
- Lead Back-End Engineer
- Manager Quality Assurance
- Principal Software Developer
- Senior Developer

All other designation records initially have the setting false. Administrators can change it without code changes.

## Workflow status

The agreed scope is the full Pointlabs One system, delivered in safe milestones while retaining every requested module. The consolidated specification at `docs/superpowers/specs/2026-09-07-pointlabs-one-design.md` is approved. The delivery roadmap is `docs/superpowers/plans/2026-09-07-pointlabs-one-program.md`; foundation execution is detailed in `docs/superpowers/plans/2026-09-07-pointlabs-one-foundation.md`.

## Approved technical direction

Use a modular Flask application with server-rendered responsive templates and focused JavaScript enhancements. Use SQLAlchemy and migrations with SQLite locally and MySQL in deployment. Deliver PWA installation support, with one maintainable codebase rather than a separate frontend application.

### Approved foundation and access model

Use administrator, reporting-officer, and employee access levels. Designations are data records with an editable `is_reporting_officer_designation` flag; reporting relationships are stored on individual employee records. Every user can view today's employees on leave. Store and administer leave policies, public-holiday calendars, and working days separately per entity/location.

### Approved leave workflow

Employees submit a leave type, dates, duration, and note. The system validates the balance and working calendar, then sends the request to the assigned reporting officer. The officer may approve, reject, or return it for information; every action has an actor, timestamp, and optional comment. Approval updates the balance and notifies HR at `askhr@pointlabs.ai`; rejection and return notify the employee. In-app notifications are created regardless of email availability; email delivery is logged and retried after SMTP is configured.

### Approved employee-record and document model

Administrators manually create and maintain employee records, assigning temporary employee IDs if necessary. Employees can edit only profile image, phone number, and personal address; all other details remain administrator-controlled. Per-employee documents support standard and custom categories. Uploads accept images and PDFs only; valid images are compressed to WebP and PDFs remain unchanged. Access and downloads are permission-checked and logged.

### Approved dashboard, reporting, and experience model

Administrators see leave approvals, balances, upcoming/current leave, birthday reminders, HR activity, and email-delivery issues. Reporting officers see restricted authorized-team data; everyone sees today's employees on leave. Reports have filtering, sorting, pagination, and Excel export. A daily birthday task creates a three-day admin reminder and sends the birthday email, with optional voucher code/image, on the birthday. The UI uses supplied brand assets, light/dark themes, accessible responsive layouts, and PWA installation/offline shell support. Include configurable approval delegation, audit trails, company announcements, and a leave calendar.
