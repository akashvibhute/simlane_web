# Component Catalog – Proposed Slippers Components

This document lists reusable UI components identified across the existing Django templates.  Each entry specifies:

• **Description** – what the component represents / does.  
• **Slots / Props** – data or blocks passed to the component.  
• **Variants** – stylistic or behavioural options.  
• **Source Examples** – where it appears today.

> NOTE: These are *design specs* only – no code has been migrated yet. We'll implement components gradually, updating this catalog as we go.

---

## 1. Layout

### 1.1 PageHeading

| Field | Description |
|-------|-------------|
| `title` (str) | Main heading text (usually `<h1>`). |
| `subtitle` (str, optional) | Secondary descriptive text. |
| `icon` (svg class, optional) | Outline/solid icon to render at left. |
| `actions` (slot, optional) | Right-aligned action buttons/links. |

Variants: `default`, `centered`.

Appears in: `core/dashboard.html`, `sim/iracing/dashboard_*_partial.html`, `teams/*_dashboard.html`.

### 1.2 Container (already exists)
Extend with optional `size` prop (`sm`, `md`, `lg`, `xl`).

### 1.3 Card

Basic card wrapper with header, body, and optional footer.

| Prop | Description |
|------|-------------|
| `header` (slot) | Card header content |
| `body` (slot) | Main card content |
| `footer` (slot, optional) | Card footer/actions |
| `padding` (bool, default: true) | Whether to add default padding |

Source: Repeated card patterns in dashboard templates.

---

## 2. Feedback

### 2.1 Alert (partially exists in allauth)

Props: `type` (`success`, `info`, `warning`, `error`), `message`, `dismissible?`.

**Current Issue**: allauth/elements/alert.html only handles error state. Need full variant support.

Source: `components/messages.html` + flash‐message blocks in _all_auth templates.

### 2.2 EmptyState

A centered panel with icon, title, message & optional action.

| Prop | Desc |
|------|------|
| `icon` | Heroicon outline SVG class. |
| `title` | Heading. |
| `message` | Body copy. |
| `action_label` | Optional CTA button text. |
| `action_href` | URL. |
| `action_attrs` | Additional button attributes (e.g., hx-get). |

Source examples: `dashboard_*_partial.html` (when `not selected_profile`), `sim_profiles_list_partial.html`.

---

## 3. Data Display

### 3.1 StatTile

Small card used on dashboards for a single metric (value, label, delta icon).

Props: `value`, `label`, `icon`, `icon_color`, `delta`, `delta_type` (`up` / `down`).

Source: `core/dashboard.html` tiles, `sim/iracing/dashboard_overview_partial.html`, `teams/club_dashboard_content_partial.html`.

### 3.2 DataTable

Wrapper for `<table>` with slots: `head`, `rows`.

Variants: `striped`, `compact`.

Source: Many list pages such as `users/sessions_partial.html`, `teams/club_dashboard_content_partial.html`.

### 3.3 Badge (partially exists in allauth)

Props: `label`, `color` (`grey`, `green`, `yellow`, `red`, `brand`), `size` (`sm`, `md`).

**Current Issue**: allauth/elements/badge.html uses tag-based styling. Need prop-based API.

Source: status labels in account & admin tables, verification badges in sim profiles.

### 3.4 Avatar

User avatar with fallback to initials.

Props: `user`, `size` (`sm`, `md`, `lg`), `src` (optional image URL).

Source: navbar user dropdown, team member lists.

---

## 4. Navigation & Actions

### 4.1 NavBar (already exists)
**Enhancement needed**: Add slot for `user_menu`, `links` array. Current implementation is monolithic.

### 4.2 SideNav

Vertical navigation for dashboard sub-pages.

Props: `items` (list of `{href, icon, label, active}`).

Source: `sim/iracing/dashboard.html` sidebar.

### 4.3 Button (partially exists in allauth)

Utility Tailwind classes collated into a component.

Props: `variant` (`primary`, `secondary`, `danger`, `link`), `size` (`sm`, `md`, `lg`), `block?`, `icon?`, `href?`.

**Current Issue**: allauth/elements/button.html has good variants but complex template logic. Simplify API.

Source: repeated `<a class="btn ...">` throughout templates.

### 4.4 Dropdown

Button-triggered menu with items.

Props: `trigger_label`, `items` (array of `{label, href, icon?, divider?}`), `align` (`left`, `right`).

Source: navbar user dropdown, future action menus.

---

## 5. Domain-Specific

### 5.1 SimProfileCard

Displays simulator avatar, driver's name, ratings badges.

Props: `profile`, `show_actions` (bool), `edit_url`, `disconnect_url`.

Source: `users/_sim_profile_card_partial.html`, dashboard profile grids.

### 5.2 TeamCard

Props: `team`, `show_stats` (bool), `href`.

Source: `teams/club_dashboard_content_partial.html` & club pages.

### 5.3 EventCard

Props: `event`, `entry_status`, `show_meta` (bool).

Source: `sim/iracing/dashboard_events_partial.html`.

### 5.4 TrackCard / CarCard

Small card with image, name, meta.

Props: `item` (track/car object), `variant` (`track`, `car`), `size` (`sm`, `md`).

Source: `dashboard_tracks_partial.html`, `dashboard_cars_partial.html`.

### 5.5 MemberCard

Display team/club member with avatar and join date.

Props: `member`, `show_role` (bool), `show_actions` (bool).

Source: `teams/club_dashboard_content_partial.html` member grids.

---

## 6. Forms

### 6.1 Form (already exists)
Add `method` prop & optional `inline_errors` flag.

### 6.2 FormField (already exists)
**Enhancement needed**: Expose `addon_before`, `addon_after` slots for icons. Current implementation is basic.

---

## 7. Utility Components

| Component | Purpose | Props |
|-----------|---------|-------|
| `Modal` | Overlay dialog with header/body/footer slots. | `title`, `size`, `dismissible` |
| `Pagination` | Page links with current/prev/next. | `page_obj`, `url_name` |
| `Tabs` | HTMX-friendly tab switcher. | `items[]`, `active`, `target` |
| `ThemeToggle` | Dark/light mode switcher. | `position` (`navbar`, `footer`) |

---

## 8. Missing/Identified Issues

### 8.1 Inconsistent Card Patterns
- Dashboard uses different card structures across sections
- Need unified Card component with flexible slots

### 8.2 Repeated Empty States
- Multiple templates have similar empty state markup
- EmptyState component would eliminate duplication

### 8.3 Icon Inconsistency
- Some use Heroicons, others inline SVG
- Need Icon component with consistent sizing/styling

### 8.4 Theme Toggle Logic
- Complex JavaScript in base.html for theme switching
- Should be componentized

---

## Implementation Status

### ✅ Implemented Components
1. **Alert** - Full variant support (success, warning, error, info) with dismissible functionality
2. **StatTile** - Dashboard metrics with icon, value, label, and slot support
3. **Card** - Basic card wrapper with header, body, footer slots
4. **Button** - Multiple variants (primary, secondary, danger, link) with size options
5. **EmptyState** - Centered panel with icon, title, message, and optional action

### 🔄 In Progress
- Updating existing templates to use new components
- Testing component functionality across different pages

### 📋 Next Steps

1. **High Priority**: `Badge`, `SimProfileCard`, `Avatar`
2. **Medium Priority**: `Modal`, `Dropdown`, `Tabs`
3. **Low Priority**: `ThemeToggle`, `Pagination`

Implementation order should focus on components with highest reuse across templates.

---

**Feel free to append additional components or fields as new UI patterns emerge.** 