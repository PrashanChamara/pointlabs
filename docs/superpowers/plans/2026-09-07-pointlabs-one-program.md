# Pointlabs One Delivery Program

**Goal:** Deliver the complete Pointlabs One HR PWA in independently testable milestones.

**Approved scope:** The complete system is in scope; milestones sequence delivery without removing features.

**Repository note:** This workspace has no Git repository. Initialize one before execution if commits and a dedicated worktree are required.

## Plan sequence

1. [Foundation and authentication](2026-09-07-pointlabs-one-foundation.md): Flask project, configuration, database, designation seed, test administrator, login, forced password change, base responsive/PWA shell.
2. Employee administration: configurable entities/locations/departments/designations, permissions, employee profiles, manual creation, document categories and secure uploads.
3. Leave operations: policy/calendar configuration, balances, working-day calculation, employee requests, reporting-officer decisions, audit history, in-app notifications, dashboards.
4. HR operations: report filters/pagination/Excel export, birthday reminders/voucher workflow, approval delegation, announcements, calendar, audit views.
5. Integration and release: SMTP email/retry queue, OTP reset, MySQL deployment configuration, PWA acceptance testing, accessibility and security review.

Each milestone begins by creating failing tests, executes with the user-selected method, and ends with the relevant automated and browser verification.
