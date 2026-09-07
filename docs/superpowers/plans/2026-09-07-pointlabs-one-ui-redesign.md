# Pointlabs One UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task.

**Goal:** Replace the basic Pointlabs One pages with a polished responsive HR-product interface while preserving Flask behaviors.

**Architecture:** Introduce a shared Jinja base shell and reusable partials; replace isolated one-line templates with semantic page templates. One design-token stylesheet owns responsive and light/dark styling, with a small JavaScript module for menu and theme state.

**Tech Stack:** Flask/Jinja, vanilla CSS, vanilla JavaScript, existing tests, browser smoke checks.

---

### Task 1: Shared responsive application shell

**Files:** Create `app/templates/base.html`, `app/templates/partials/navigation.html`, `app/static/app.js`; modify all templates and `app/static/app.css`.

- [ ] Write a failing browser check for the sidebar, mobile navigation, and theme toggle.
- [ ] Implement semantic shell/partials and responsive navigation.
- [ ] Run the browser check at desktop and 390px widths.

### Task 2: Dashboard and workflow page components

**Files:** Modify all `app/templates/*.html` except base/partials.

- [ ] Write failing route-render tests asserting key headings/actions.
- [ ] Build dashboard metrics/cards, page headers, data tables, forms, and empty states.
- [ ] Verify existing leave, employee, profile, document, designation, birthday, and auth flows.

### Task 3: Visual QA

**Files:** Modify `app/static/app.css`, `app/static/app.js` as needed.

- [ ] Test light/dark mode persistence and responsive overflow.
- [ ] Run full pytest suite and local browser smoke check.
- [ ] Commit the completed redesign.
