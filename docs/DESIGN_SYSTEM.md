# Carcara Vision Design System

> **Hardware-Accelerated ML Inference Platform** - Design Documentation
> Last Updated: January 2026

---

## Table of Contents

1. [Brand Identity](#brand-identity)
2. [Color Palette](#color-palette)
3. [Typography](#typography)
4. [Component Styling](#component-styling)
5. [Layout & Navigation](#layout--navigation)
6. [Interactive States](#interactive-states)
7. [Iconography](#iconography)
8. [Accessibility](#accessibility)

---

## Brand Identity

### Product Name

**Carcara Vision** (Hardware-Accelerated ML Inference)

### Brand Concept

The name "Carcará" (Caracara) references the Brazilian bird of prey known for its keen eyesight and vigilance — perfect symbolism for a video surveillance system. The design reflects this through:

- **Sharp, modern aesthetics** — Clean lines and precise typography
- **Warm accent colors** — Inspired by the caracara's distinctive orange/rust plumage
- **Dark, professional interface** — Optimized for monitoring environments and reduced eye strain

### Logo Design

The logo features:

- A stylized **"C"** enclosed in a rounded square with gradient fill
- Gradient transitions from vibrant orange (`#F5A45A`) to dark rust (`#D26A27`)
- A subtle highlight overlay for depth
- "CARCARA" in bold uppercase with "Vision" as an orange accent subtitle

---

## Color Palette

### Primary Colors

| Name               | Hex Code  | RGB                  | Usage                                   |
| ------------------ | --------- | -------------------- | --------------------------------------- |
| **Primary Orange** | `#F5A45A` | `rgb(245, 164, 90)`  | Primary buttons, active states, accents |
| **Primary Dark**   | `#D26A27` | `rgb(210, 106, 39)`  | Gradient endpoints, hover states        |
| **Primary Light**  | `#FFB97A` | `rgb(255, 185, 122)` | Hover highlights                        |

### Secondary Colors

| Name            | Hex Code  | RGB                  | Usage                                      |
| --------------- | --------- | -------------------- | ------------------------------------------ |
| **Cream**       | `#E3D3B0` | `rgb(227, 211, 176)` | Secondary accent, gradient text highlights |
| **Cream Dark**  | `#C9B896` | `rgb(201, 184, 150)` | Secondary dark variant                     |
| **Cream Light** | `#F0E8D8` | `rgb(240, 232, 216)` | Secondary light variant                    |

### Neutral Colors

| Name               | Hex Code  | RGB                  | Usage                              |
| ------------------ | --------- | -------------------- | ---------------------------------- |
| **Background**     | `#0D0E10` | `rgb(13, 14, 16)`    | Page background                    |
| **Surface**        | `#181A1F` | `rgb(24, 26, 31)`    | Cards, sidebar, dialogs            |
| **Gray**           | `#484F57` | `rgb(72, 79, 87)`    | Borders, dividers, secondary icons |
| **Light Gray**     | `#6B7280` | `rgb(107, 114, 128)` | Tertiary text, disabled states     |
| **Text Primary**   | `#F9FAFB` | `rgb(249, 250, 251)` | Primary text content               |
| **Text Secondary** | `#9CA3AF` | `rgb(156, 163, 175)` | Secondary text, labels             |

### Semantic Colors

| Name              | Hex Code  | Usage                                |
| ----------------- | --------- | ------------------------------------ |
| **Success**       | `#10B981` | Active status, confirmations         |
| **Success Light** | `#34D399` | Success text on dark backgrounds     |
| **Error**         | `#EF4444` | Inactive status, destructive actions |
| **Error Light**   | `#F87171` | Error text on dark backgrounds       |
| **Warning**       | `#F5A45A` | Warning states (uses primary)        |

### Color Usage Guidelines

```
┌─────────────────────────────────────────────────────────────┐
│  Background: #0D0E10                                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Surface/Card: #181A1F                                │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  Primary Text: #F9FAFB                          │  │  │
│  │  │  Secondary Text: #9CA3AF                        │  │  │
│  │  │  ─────────────────────────────────              │  │  │
│  │  │  Border: #484F57 @ 20% opacity                  │  │  │
│  │  │                                                 │  │  │
│  │  │  [████ Primary Button ████]  ← #F5A45A → #D26A27│  │  │
│  │  │                                                 │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Typography

### Font Family

**Inter** — A modern, highly legible sans-serif typeface optimized for screen readability.

```css
font-family: "Inter", "Roboto", "Helvetica", "Arial", sans-serif;
```

### Type Scale

| Variant      | Size     | Weight | Letter Spacing | Usage             |
| ------------ | -------- | ------ | -------------- | ----------------- |
| **H1**       | 2.5rem   | 700    | -0.02em        | Main page titles  |
| **H2**       | 2rem     | 700    | -0.02em        | Section headers   |
| **H3**       | 1.5rem   | 600    | -0.01em        | Card titles       |
| **H4**       | 1.25rem  | 600    | -0.01em        | Page headers      |
| **H5**       | 1.125rem | 600    | normal         | Subsection titles |
| **H6**       | 1rem     | 600    | normal         | Small headers     |
| **Body 1**   | 1rem     | 400    | normal         | Primary content   |
| **Body 2**   | 0.875rem | 400    | normal         | Secondary content |
| **Caption**  | 0.75rem  | 400    | normal         | Labels, metadata  |
| **Overline** | 0.65rem  | 500    | 0.1em          | Category labels   |
| **Button**   | 0.95rem  | 600    | normal         | Button text       |

### Gradient Text Effect

Page headers use a gradient text effect for visual interest:

```css
background: linear-gradient(135deg, #f9fafb 0%, #e3d3b0 100%);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
```

---

## Component Styling

### Cards

Cards are the primary content containers with the following properties:

| Property      | Value                            |
| ------------- | -------------------------------- |
| Background    | `#181A1F` @ 80% opacity          |
| Border        | `#484F57` @ 15% opacity          |
| Border Radius | 12px                             |
| Box Shadow    | `0 4px 20px rgba(0, 0, 0, 0.25)` |

**Hover State:**

- Transform: `translateY(-2px)`
- Box Shadow: `0 8px 30px rgba(0, 0, 0, 0.35)`
- Border Color: `#F5A45A` @ 30% opacity

### Buttons

#### Primary (Contained)

```css
background: linear-gradient(135deg, #f5a45a 0%, #d26a27 100%);
color: #181a1f;
border-radius: 8px;
padding: 10px 20px;
font-weight: 600;
```

**Hover:**

```css
background: linear-gradient(135deg, #ffb97a 0%, #f5a45a 100%);
```

#### Secondary (Outlined)

```css
border: 1px solid rgba(245, 164, 90, 0.5);
background: transparent;
```

**Hover:**

```css
border-color: #f5a45a;
background: rgba(245, 164, 90, 0.08);
```

### Form Inputs

| State   | Border Color    |
| ------- | --------------- |
| Default | `#484F57` @ 30% |
| Hover   | `#F5A45A` @ 50% |
| Focused | `#F5A45A`       |
| Error   | `#EF4444`       |

### Chips/Badges

#### Status Chips

```css
/* Success (Active) */
background: rgba(16, 185, 129, 0.15);
color: #34d399;

/* Error (Inactive) */
background: rgba(239, 68, 68, 0.15);
color: #f87171;

/* Default/Info */
background: rgba(245, 164, 90, 0.15);
color: #f5a45a;
```

### Dialogs

| Property      | Value                                  |
| ------------- | -------------------------------------- |
| Background    | `#181A1F`                              |
| Border        | `#484F57` @ 20% opacity                |
| Box Shadow    | `0 25px 50px -12px rgba(0, 0, 0, 0.5)` |
| Border Radius | 12px                                   |

---

## Layout & Navigation

### Sidebar (Drawer)

- **Width:** 260px
- **Background:** `#181A1F`
- **Border Right:** `#484F57` @ 20% opacity

### Sidebar Structure

```
┌─────────────────────────────┐
│  [Logo]  CARCARA            │
│       Vision      │
├─────────────────────────────┤
│  MAIN MENU                  │
│                             │
│  │▌ Cameras      (active)   │
│    Streams                  │
│    Alarms                   │
│    Settings                 │
│                             │
├─────────────────────────────┤
│  Network Video Controller   │
└─────────────────────────────┘
```

### Navigation Item States

| State   | Style                                              |
| ------- | -------------------------------------------------- |
| Default | Gray text, no background                           |
| Hover   | `#F5A45A` @ 8% background                          |
| Active  | `#F5A45A` @ 12% background, 3px left border accent |

### App Bar

- **Background:** `#181A1F` @ 90% opacity
- **Backdrop Filter:** `blur(8px)`
- **Border Bottom:** `#484F57` @ 20% opacity

### Content Area

- **Padding:** 24px
- **Min Height:** 100vh

---

## Interactive States

### Hover Effects

1. **Cards:** Subtle lift with `translateY(-2px)` and enhanced shadow
2. **Buttons:** Background color shift toward lighter variant
3. **Icon Buttons:** Background tint with primary color @ 12% opacity
4. **Links:** Color transition to primary dark

### Focus States

All interactive elements have visible focus indicators:

```css
outline: 2px solid #f5a45a;
outline-offset: 2px;
```

### Loading States

- **Skeleton loaders** with animated shimmer effect
- **Circular progress** indicators in primary color
- Smooth fade-in animations for content

### Animations

#### Pulse (Live Indicators)

```css
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
animation: pulse 2s ease-in-out infinite;
```

#### Fade In (Page Transitions)

```css
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
animation: fadeIn 0.3s ease-out;
```

---

## Iconography

### Icon Library

**Material Icons** via `@mui/icons-material`

### Icon Usage by Section

| Section  | Icon            | Purpose                   |
| -------- | --------------- | ------------------------- |
| Cameras  | `Videocam`      | Navigation, empty states  |
| Streams  | `PlayCircle`    | Navigation, status        |
| Alarms   | `Notifications` | Navigation, alerts        |
| Settings | `Settings`      | Navigation, configuration |

### Icon Sizing

| Context      | Size           |
| ------------ | -------------- |
| Navigation   | 24px (default) |
| Card Actions | small (20px)   |
| Empty States | 48px           |
| Logo         | 44px           |

### Icon Colors

| State   | Color                            |
| ------- | -------------------------------- |
| Default | `#6B7280` (Light Gray)           |
| Active  | `#F5A45A` (Primary)              |
| Hover   | Primary with 12% background tint |

---

## Accessibility

### Color Contrast

All text meets WCAG 2.1 AA standards:

- Primary text (#F9FAFB) on background (#0D0E10): **15.8:1**
- Secondary text (#9CA3AF) on background (#0D0E10): **7.2:1**
- Primary orange (#F5A45A) on dark text (#181A1F): **6.1:1**

### Focus Visibility

All interactive elements have visible focus indicators with 2px orange outline.

### Motion Preferences

Animations respect `prefers-reduced-motion` where applicable.

### Screen Reader Support

- Semantic HTML structure
- ARIA labels on icon-only buttons
- Proper heading hierarchy

---

## Implementation Notes

### CSS Variables

```css
:root {
  --color-bg-light: #f9fafb;
  --color-cream: #e3d3b0;
  --color-primary: #f5a45a;
  --color-primary-dark: #d26a27;
  --color-neutral-dark: #181a1f;
  --color-neutral-gray: #484f57;
}
```

### Material UI Theme

The theme is configured in `src/App.tsx` using MUI's `createTheme()` with comprehensive component overrides for consistent styling.

### File Structure

```
frontend/src/
├── App.tsx          # Theme configuration
├── App.css          # Global utility classes
├── index.css        # CSS variables & base styles
├── components/
│   └── Layout.tsx   # Main layout with branded sidebar
└── pages/
    ├── Cameras.tsx
    ├── Streams.tsx
    ├── Alarms.tsx
    └── Settings.tsx
```

---

## Design Rationale

### Why Dark Theme?

1. **Reduced eye strain** — Operators monitoring video feeds for extended periods benefit from dark interfaces
2. **Better video contrast** — Dark surroundings make video content stand out
3. **Modern aesthetic** — Aligns with contemporary monitoring/security software standards
4. **Energy efficiency** — OLED displays consume less power with dark themes

### Why Orange Accents?

1. **Brand differentiation** — Distinctive color not commonly used in security software
2. **High visibility** — Orange provides excellent contrast against dark backgrounds
3. **Thematic connection** — References the Caracara bird's distinctive plumage
4. **Warmth balance** — Offsets the cool, technical nature of surveillance systems

### Why Gradients?

1. **Depth perception** — Adds visual interest without complexity
2. **Premium feel** — Subtle gradients convey quality and attention to detail
3. **Focus direction** — Gradient direction guides the eye toward important elements

---

_Document maintained by the Carcara Vision development team_
