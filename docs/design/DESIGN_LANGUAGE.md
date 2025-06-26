# SimLane Design Language

_Last updated: December 2024_

## Purpose

This document defines the visual and interaction language of SimLane.  Use it as a reference whenever you add a new view, component, or asset to keep the experience consistent and on-brand.

---

## 1. Core Principles

1. **Clarity & Focus** – Surfaces should highlight the most important action and information first.
2. **Racing DNA** – A subtle motorsport aesthetic (sleek lines, dark/light contrast) without overwhelming the content.
3. **Accessibility** – Meet WCAG 2.2 AA colour-contrast ratios; support keyboard navigation and screen readers.
4. **Systematic** – Build with reusable Tailwind utility classes and Django template partials.

---

## 2. Colour Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `brand-primary` | `#FF2300` | Accent buttons, links, active states |
| `brand-secondary` | `#1E1E1E` | Dark UI elements (nav, footer) |
| `grey-100` | `#F5F5F5` | Backgrounds |
| `grey-700` | `#4B5563` | Body text |
| `grey-900` | `#111827` | Headlines |
| `success` | `#16A34A` | Positive badges |
| `warning` | `#EAB308` | Warnings |
| `error` | `#DC2626` | Destructive actions |

> Tailwind v4 custom colours are injected via `@theme colors` in `static/css/tailwind.css`.

### Contrast Reference

Use the Tailwind plugin `@tailwindcss/typography`'s `prose-invert` class for dark backgrounds when needed.  Verify contrast with tools like Axe.

---

## 3. Typography

| Element | Font Family | Weight | Size | Tailwind Class |
|---------|------------|--------|------|----------------|
| Headline 1 | Inter / system UI | 700 | 2.25 rem | `text-4xl font-bold` |
| Headline 2 | Inter | 700 | 1.875 rem | `text-3xl font-bold` |
| Headline 3 | Inter | 600 | 1.5 rem | `text-2xl font-semibold` |
| Body Large | Inter | 400 | 1.125 rem | `text-lg` |
| Body Default | Inter | 400 | 1 rem | `text-base` |
| Caption | Inter | 400 | 0.875 rem | `text-sm text-grey-700` |

System font stack is defined in `tailwind.css`.

---

## 4. Spacing & Layout

• **8-pt grid** – All margins & paddings are multiples of 0.5 rem (8 px).  
• **container** component centers content with `max-w-6xl mx-auto px-4 sm:px-6 lg:px-8`.

Breakpoints follow Tailwind defaults (`sm` 640 px, `md` 768 px, `lg` 1024 px, `xl` 1280 px, `2xl` 1536 px).

---

## 5. Components

### Buttons
- **Primary**: `btn-primary` - Primary action button with brand colors
- **Secondary**: `btn-secondary` - Secondary action button with border style
- **Small variant**: Add `btn-sm` class for compact buttons
- **Disabled**: Automatically handled with `disabled:opacity-50 disabled:cursor-not-allowed`

### Form Elements
- **Input**: `form-input` - Text input with consistent styling and focus states
- **Select**: `form-select` - Dropdown select with matching input styling
- **Checkbox**: `form-checkbox` - Checkbox with brand color theming
- All form elements include proper dark mode support

### Search Components
- **Search Container**: `search-container` - Wrapper for search sections with consistent padding and styling
- **Clear Filters**: `clear-filters` - Link-style button for clearing filters with icon support

### Card
- Wrapper: `bg-white shadow-sm rounded-lg p-6`  
- Use for dashboard panels.

### Alert
- Success / Warning / Error variants defined via background + icon utilities.

Partial templates live in `templates/components/` and should be reused.

---

## 6. Motion & Interaction

• Sub-100 ms hover/active transitions (`transition-colors`).  
• Page transitions handled by HTMX swap defaults – no fancy SPA fades.  
• Use `aria-live="polite"` for async form feedback.

---

## 7. Iconography

• Prefer Heroicons (`@heroicons/outline` + `@heroicons/solid`) already included.  
• SVGs should inherit `currentColor` for stroke/fill to align with text colour.
• Search icons consistently use the magnifying glass icon
• Clear/close actions use the X icon

---

## 8. Search UI Standards

### Layout
- Search sections use the `search-container` class for consistent styling
- Search inputs are wrapped in flex containers with proper spacing
- Filters are organized in responsive grids (2-5 columns based on content)

### Interactive Elements
- Search buttons include magnifying glass icons
- Clear filter buttons include X icons
- All buttons have proper hover and focus states
- Form elements maintain consistent styling across light/dark modes

### Accessibility
- Proper focus management with visible focus rings
- Screen reader labels for icon-only buttons
- Consistent color contrast ratios in both themes

---

## 9. Assets & Naming

| Asset Type | Location | Naming Convention |
|------------|----------|-------------------|
| Images | `static/images/` | `context-name_size.ext` (e.g., `logo_inverted_square.png`) |
| SVG Icons | `static/images/` | `icon-[semantic].svg` |
| CSS Partial | `static/css/` | `[_]component.css` |

---

## 10. Accessibility Checklist

- [ ] Text/background contrast ≥ 4.5:1 (body) or 3:1 (large text).
- [ ] All interactive elements are focusable & reachable via keyboard.
- [ ] `aria-label`, `aria-describedby` set for custom controls.
- [ ] Language attribute set on `<html>`.
- [ ] Form inputs have proper labels and error states.
- [ ] Search functionality works without JavaScript.

---

## 11. Code Snippets

```html
<!-- Primary Button -->
<button class="btn-primary">Save changes</button>

<!-- Secondary Button -->
<button class="btn-secondary">Cancel</button>

<!-- Form Input -->
<input type="text" class="form-input" placeholder="Enter text...">

<!-- Form Select -->
<select class="form-select">
  <option>Choose option</option>
</select>

<!-- Search Container -->
<div class="search-container">
  <form class="space-y-4">
    <div class="flex gap-4">
      <div class="flex-1">
        <input type="text" class="form-input w-full" placeholder="Search...">
      </div>
      <button type="submit" class="btn-primary">
        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
        </svg>
        Search
      </button>
    </div>
  </form>
</div>
```

---

## 12. Changelog

| Date | Author | Note |
|------|--------|------|
| 2024-12-?? | Assistant | Added component classes for buttons, forms, and search UI |
| 2024-07-?? | _You_ | Initial draft |

---

### Contributing

1. Propose edits via PR to `docs/design/DESIGN_LANGUAGE.md`.  
2. Attach relevant screenshots / Figma links.  
3. Once merged, update component files + Tailwind tokens if needed. 