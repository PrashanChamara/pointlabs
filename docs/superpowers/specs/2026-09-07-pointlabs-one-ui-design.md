# Pointlabs One UI redesign

## Direction

Rebuild the existing functional shell as a premium, mobile-first HR command center. The application retains its Flask routes and data model; this is a presentation and interaction-system overhaul.

## Layout

- Desktop: permanent dark-evergreen sidebar with icon + label navigation, top utility bar, responsive 12-column content grid.
- Mobile: compact header, horizontally scrollable context actions, fixed bottom navigation, and a prominent apply-leave action.
- Dashboard: overview metrics, leave coverage, approvals, birthdays, activity, and empty states arranged by decision priority.

## Design tokens

Use deep evergreen for navigation, warm white surfaces, pale green secondary surfaces, restrained Pointlabs gold for primary action, accessible status colors, 16px/20px radii, generous whitespace, and a modern system type stack. Support a persistent dark theme.

## Components

Create shared base shell, sidebar, top bar, mobile navigation, stat cards, page header, filter chips, status pills, tables, form sections, empty states, alerts, and avatar treatment. Every existing route is rendered inside the shared shell.

## Verification

Verify desktop and 390px mobile layouts, sidebar/menu navigation, theme persistence, visible keyboard focus, no horizontal overflow, all existing links/forms, and no browser console errors.
