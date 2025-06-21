# SimLane Design Language

_Last updated: {{DATE}}

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

1. **Buttons**  
   - Primary: `bg-brand-primary text-white hover:bg-opacity-90`  
   - Secondary: `border border-brand-primary text-brand-primary hover:bg-brand-primary/10`  
   - Disabled: `opacity-50 cursor-not-allowed`
2. **Card**  
   - Wrapper: `bg-white shadow-sm rounded-lg p-6`  
   - Use for dashboard panels.
3. **Alert**  
   - Success / Warning / Error variants defined via background + icon utilities.
4. **Form Field**  
   - Input: `block w-full rounded-md border-gray-300 focus:border-brand-primary focus:ring-brand-primary`  
   - Error state adds `border-error`.

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

---

## 8. Assets & Naming

| Asset Type | Location | Naming Convention |
|------------|----------|-------------------|
| Images | `static/images/` | `context-name_size.ext` (e.g., `logo_inverted_square.png`) |
| SVG Icons | `static/images/` | `icon-[semantic].svg` |
| CSS Partial | `static/css/` | `[_]component.css` |

---

## 9. Accessibility Checklist

- [ ] Text/background contrast ≥ 4.5:1 (body) or 3:1 (large text).
- [ ] All interactive elements are focusable & reachable via keyboard.
- [ ] `aria-label`, `aria-describedby` set for custom controls.
- [ ] Language attribute set on `<html>`.

---

## 10. Code Snippets

```html
<button class="btn-primary">Save changes</button>

<!-- tailwind.css -->
@layer components {
  .btn-primary {
    @apply inline-flex items-center justify-center rounded-md bg-brand-primary px-4 py-2 text-sm font-medium text-white shadow hover:bg-opacity-90 focus:outline-none focus:ring-2 focus:ring-brand-primary focus:ring-offset-2;
  }
}
```

---

## 11. Changelog

| Date | Author | Note |
|------|--------|------|
| 2024-07-?? | _You_ | Initial draft |

---

### Contributing

1. Propose edits via PR to `docs/design/DESIGN_LANGUAGE.md`.  
2. Attach relevant screenshots / Figma links.  
3. Once merged, update component files + Tailwind tokens if needed. 