# Pointlabs One product rebuild

## Product direction

Pointlabs One is a premium people-operations workspace for an AI company. It must feel like a considered product, not a collection of admin forms: a calm, high-density desktop workspace with a capable mobile experience.

## Visual system

- Light mode uses a near-white green canvas, white working surfaces and purposeful gold actions.
- Dark mode uses near-black surfaces with soft light-gold emphasis; it is not a dark-green inversion.
- Use the supplied Pointlabs wordmarks according to contrast and the supplied ring icon as the One `O`, application icon and PWA icon.
- The application has a persistent left rail, a compact context bar, data-rich panels, clear empty states and a responsive mobile drawer.

## Information architecture

1. Employee directory: search, filters, CSV export and employee creation.
2. Messages: a private internal inbox with a conversational layout and delivery email notification when a recipient has an email address.
3. Dashboard: time-aware greeting, leave coverage, approvals, notices and quick actions.
4. Reports: HR metrics and leave export.
5. Administration: a clear hub for people, documents, designations and birthday communications.
6. Personal account: profile, leave, files and password settings are available from the signed-in identity in the rail.

## Core behaviour

- Seeding always provisions an employee profile for the test administrator, so every logged-in identity has a usable profile surface.
- Administrators can upload a document against any employee; employees can only upload to themselves.
- The document area shows ownership and safe file metadata.
- Dynamic greetings use server local time: morning, afternoon or evening.
- SMTP credentials are only read from ignored local environment configuration; they must never enter version control or UI output.

## Acceptance checks

- `/profile` for `admin` renders a complete profile rather than an error after seeding.
- Admin document upload offers an employee selector and persists the selected owner.
- Directory, messages, dashboard, reports, admin and personal account routes render through the professional shell.
- Light/dark themes, supplied brand assets and PWA manifest all reference the intended assets.
