# Pointlabs One — approved design

**Status:** Approved design sections; awaiting written-spec review  
**Scope:** Full Pointlabs HR PWA

## 1. Goal

Pointlabs One is a mobile-first HR web application and installable PWA for employee records, leave, approval workflows, documents, birthdays, reporting, and HR administration. It supports Pointlabs entities and locations independently while remaining administrable without code changes.

## 2. Technical architecture

- One modular Flask application with server-rendered responsive templates and focused JavaScript enhancements.
- Modules: authentication, administration, employees, leave, dashboards, documents, reports, birthdays, notifications, and shared services.
- SQLAlchemy and migrations; SQLite in local development and MySQL in deployment.
- PWA manifest, supplied app icon, service-worker offline shell, and install affordance.
- Responsive light and dark themes using supplied Pointlabs assets and a light-green, gold, and white visual system.

## 3. Access and configuration

Access is enforced by permissions, not job-title checks.

| Access level | Permissions |
|---|---|
| Administrator | Manage all data, policies, users, documents, reports, and exceptions. |
| Reporting officer | View authorized team leave data and act on direct-report requests; no HR data creation/edit/delete. |
| Employee | View own record and balances, submit/manage own leave requests, edit only own profile image, phone, and personal address. |
| All users | View today's employees on leave. |

Designations are data records, each with editable `is_reporting_officer_designation`. Individual employee records store their actual reporting officer, so promotions and reporting changes are data changes. Entities, locations, departments, designations, leave types, policies, calendars, working days, and document categories are administrator-configurable.

## 4. Initial reference data and test access

`Staff Info.xlsx` is a reference only. Do not import employee profiles, balances, or other employee data. Use it to seed 33 designation records and set the 11 designations currently used by reporting managers as reporting-officer designations. Administrators will manually create all employees and complete their data, assigning temporary employee IDs where necessary.

Seed only one local test administrator: username `admin`, with the user-supplied temporary development password. Do not commit that password or store it in long-lived reference documents. The account must change its password at first sign-in. Full email OTP password recovery will be enabled once SMTP configuration is provided.

## 5. Employee profiles and documents

An employee profile supports employee code, user ID, entity, location, designation, department, reporting officer, join/resignation dates, employee status, contact and personal-address details, DOB, gender, profile image, salary/banking details, leave balances, and custom future fields when requested.

Employee documents are stored per employee with standard categories (passport, visa, qualifications) and administrator-created categories. Permit images and PDFs only. Validate file type and size server-side. Convert valid image uploads to compressed WebP; preserve PDFs. Access, downloads, replacements, and removals require permissions and are audited.

## 6. Leave workflow

1. Employee creates a draft or submits a request with leave type, dates/duration, and note.
2. Submission validates policy entitlement, leave balance, working days, and public holidays according to entity/location.
3. The assigned reporting officer receives an in-app notification and, after SMTP setup, an email.
4. The officer approves, rejects, or returns the request for further information, with optional comment.
5. Approval updates the balance and notifies HR at `askhr@pointlabs.ai`; rejection/return notifies the employee. A returned request can be amended and resubmitted.
6. Store all state transitions, actor, time, and comments in an immutable approval history.

In-app notifications are written independently of email delivery. Email sends, failures, and retries are logged. Administrators can view all data and manage exceptions; reporting officers view only authorized team data.

## 7. Dashboards, reports, and birthdays

Administrator dashboard: pending requests, leave balances, upcoming/current leave, people on leave today, birthday reminders, HR activity, and email-delivery issues. Reporting officers get a restricted team dashboard. All users see a Today on Leave page.

Employee, leave, balance, and request reports have search, sortable columns, filters, pagination, and Excel export. Filters include entity, location, department, designation, status, leave type, reporting officer, and date range as appropriate.

A daily scheduled task identifies birthdays. At three days before, it creates an administrator reminder. The administrator may record a voucher code and/or voucher image. On the birthday, send a standard greeting or voucher-inclusive greeting; log the action and delivery result.

## 8. Professional features

- Audit trail for sensitive HR actions.
- Configurable approval delegation during a manager's absence.
- Company announcements.
- Leave calendar view.
- Configurable public-holiday calendars and working days per entity/location.

## 9. Security and reliability

- Passwords use secure salted hashes. Temporary-password users must change them at first login.
- OTP codes are short-lived, single-use, rate-limited, and sent only to the registered email address.
- Enforce server-side validation, CSRF protection, authorization checks, secure session handling, and controlled document access.
- Scheduled birthday and email-retry work reports operational failures to administrators.

## 10. Verification

Verify role boundaries; login and forced password change; password-reset OTP after email setup; leave calculations and all decision paths; notification/email retry behavior; document type validation and WebP conversion; report filtering/pagination/Excel export; birthday and voucher flow; responsive UI; dark mode; and PWA install/offline shell behavior.

## 11. Delivery sequence

1. Application foundation, configuration, authentication, initial test admin, visual system, PWA shell.
2. Designation/configuration and employee administration.
3. Leave policies, balances, requests, approvals, dashboards, and in-app notifications.
4. Documents, reports/export, birthday workflow, delegation, calendar, announcements, and audit views.
5. SMTP/OTP integration, MySQL readiness, automated verification, and deployment hardening.
