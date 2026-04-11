# terrAIn Design System

Based on Linear's design language. This is the authoritative visual specification for the terrAIn frontend. All UI components must conform to this system.

## 1. Visual Theme & Atmosphere

Dark-mode-first application UI built for sustained use. The aesthetic is calm, confident, and information-dense — a pipeline monitoring and application management tool, not a marketing site. Content emerges from near-black surfaces through carefully calibrated luminance steps. Structure comes from semi-transparent white borders and background opacity shifts, not heavy dividers or color blocks.

The typography system is built entirely on Inter with OpenType features `"cv01"` and `"ss03"` enabled globally, giving the typeface a cleaner, more geometric character. The signature weight 510 (between regular and medium) creates subtle emphasis without heaviness. At display sizes, aggressive negative letter-spacing creates compressed, engineered headlines.

The achromatic foundation (dark surfaces, white/gray text) is punctuated by two accent systems: a primary brand indigo for CTAs and interactive elements, and a set of five pipeline stage colors that provide semantic meaning throughout the dashboard.

**Key Characteristics:**
- Dark-mode-native: `#08090a` base, `#0f1011` panels, `#191a1b` elevated surfaces
- Inter with `"cv01", "ss03"` globally — geometric alternates for a cleaner aesthetic
- Signature weight 510 as default emphasis weight
- Aggressive negative letter-spacing at display sizes (-1.584px at 72px, -1.056px at 48px)
- Brand indigo: `#5e6ad2` (bg) / `#7170ff` (accent) / `#828fff` (hover)
- Pipeline stage colors for semantic dashboard elements
- Semi-transparent white borders: `rgba(255,255,255,0.05)` to `rgba(255,255,255,0.08)`
- Button backgrounds at near-zero opacity: `rgba(255,255,255,0.02)` to `rgba(255,255,255,0.05)`
- Multi-layered shadows with inset variants for depth on dark surfaces
- JetBrains Mono for code and technical content

## 2. Color Palette & Roles

### Background Surfaces
- **Base Black** (`#08090a`): Deepest background canvas.
- **Panel Dark** (`#0f1011`): Sidebar and panel backgrounds.
- **Surface Elevated** (`#191a1b`): Card backgrounds, dropdowns, elevated areas.
- **Surface Hover** (`#28282c`): Hover states, slightly elevated components.

### Text & Content
- **Primary Text** (`#f7f8f8`): Near-white, default text. Not pure white — prevents eye strain.
- **Secondary Text** (`#d0d6e0`): Body text, descriptions.
- **Tertiary Text** (`#8a8f98`): Placeholders, metadata, de-emphasized content.
- **Quaternary Text** (`#62666d`): Timestamps, disabled states, subtle labels.

### Brand & Accent
- **Brand Indigo** (`#5e6ad2`): Primary CTA backgrounds, brand marks.
- **Accent Violet** (`#7170ff`): Interactive elements — links, active states, selected items.
- **Accent Hover** (`#828fff`): Hover states on accent elements.

### Pipeline Stage Colors

These five colors identify pipeline stages throughout the dashboard — in stage cards, status indicators, charts, and timeline elements. Each has a primary (full) and tinted (background) variant.

| Stage | Primary | Tinted Background | Use |
|-------|---------|-------------------|-----|
| **Harvest** | `#e0a862` | `rgba(224,168,98,0.12)` | Warm amber. Ingestion, gathering, arrival. |
| **Dedup** | `#9fc9a2` | `rgba(159,201,162,0.12)` | Sage green. Filtering, cleaning, resolution. |
| **Score** | `#9fbbe0` | `rgba(159,187,224,0.12)` | Soft blue. Analysis, evaluation, assessment. |
| **Promote** | `#c0a8dd` | `rgba(192,168,221,0.12)` | Lavender. Advancement, selection, decision. |
| **Cover Letter** | `#dfa88f` | `rgba(223,168,143,0.12)` | Warm peach. Creation, generation, output. |

### Status Colors
- **Success** (`#27a644`): Active, completed, healthy states.
- **Warning** (`#d97706`): Attention needed, approaching threshold.
- **Error** (`#cf2d56`): Failed, blocked, critical.
- **Info** (`#7170ff`): Informational, uses accent violet.

### Recommendation Tier Colors

Used in scoring displays and opportunity lists:

| Tier | Color | Tinted Background |
|------|-------|-------------------|
| **STRONG FIT** | `#27a644` | `rgba(39,166,68,0.12)` |
| **GOOD FIT** | `#9fc9a2` | `rgba(159,201,162,0.12)` |
| **MARGINAL FIT** | `#d97706` | `rgba(217,119,6,0.12)` |
| **SKIP** | `#62666d` | `rgba(255,255,255,0.05)` |

### Border & Divider
- **Border Subtle** (`rgba(255,255,255,0.05)`): Default border — whisper-thin.
- **Border Standard** (`rgba(255,255,255,0.08)`): Cards, inputs, code blocks.
- **Border Solid Primary** (`#23252a`): Prominent separations.
- **Border Solid Secondary** (`#34343a`): Slightly lighter.

### Overlay
- **Overlay** (`rgba(0,0,0,0.85)`): Modal/dialog backdrop.

## 3. Typography Rules

### Font Family
- **Primary**: `Inter`, with fallbacks: `SF Pro Display, -apple-system, system-ui, Segoe UI, Roboto, Helvetica Neue, Arial`
- **Monospace**: `JetBrains Mono`, with fallbacks: `ui-monospace, SF Mono, Menlo, Monaco, Consolas`
- **OpenType Features**: `"cv01", "ss03"` enabled globally on Inter.

### Hierarchy

| Role | Size | Weight | Line Height | Letter Spacing | Notes |
|------|------|--------|-------------|----------------|-------|
| Display XL | 72px | 510 | 1.00 | -1.584px | Hero headlines, maximum impact |
| Display | 48px | 510 | 1.00 | -1.056px | Section headlines, dashboard title |
| Heading 1 | 32px | 400 | 1.13 | -0.704px | Major section titles |
| Heading 2 | 24px | 400 | 1.33 | -0.288px | Sub-section headings |
| Heading 3 | 20px | 590 | 1.33 | -0.24px | Card headers, panel titles |
| Body Large | 18px | 400 | 1.60 | -0.165px | Feature descriptions, summaries |
| Body | 16px | 400 | 1.50 | normal | Standard reading text |
| Body Medium | 16px | 510 | 1.50 | normal | Navigation, labels |
| Body Semibold | 16px | 590 | 1.50 | normal | Strong emphasis |
| Small | 15px | 400 | 1.60 | -0.165px | Secondary body text |
| Small Medium | 15px | 510 | 1.60 | -0.165px | Emphasized small text |
| Caption Large | 14px | 510 | 1.50 | -0.182px | Sub-labels, category headers |
| Caption | 13px | 400–510 | 1.50 | -0.13px | Metadata, timestamps |
| Label | 12px | 400–590 | 1.40 | normal | Button text, small labels |
| Micro | 11px | 510 | 1.40 | normal | Tiny labels |
| Tiny | 10px | 400–510 | 1.50 | -0.15px | Overline text |
| Mono Body | 14px (JetBrains Mono) | 400 | 1.50 | normal | Code blocks, technical content |
| Mono Caption | 13px (JetBrains Mono) | 400 | 1.50 | normal | Code labels |
| Mono Label | 12px (JetBrains Mono) | 400 | 1.40 | normal | Code metadata |

### Principles
- **510 is the signature weight**: Between regular (400) and medium (500). Creates subtle emphasis without heaviness.
- **Compression at scale**: Letter-spacing tightens with font size. -1.584px at 72px, -1.056px at 48px, -0.704px at 32px. Below 16px, spacing relaxes toward normal.
- **Three-tier weight system**: 400 (reading), 510 (emphasis/UI), 590 (strong emphasis). No bold (700).
- **OpenType as identity**: `"cv01", "ss03"` are non-negotiable — they give Inter its geometric, purposeful character.

## 4. Component Stylings

### Buttons

**Primary Brand**
- Background: `#5e6ad2`
- Text: `#ffffff`
- Padding: 8px 16px
- Radius: 6px
- Hover: background shifts to `#828fff`
- Use: Primary CTAs, key actions

**Ghost (Default)**
- Background: `rgba(255,255,255,0.02)`
- Text: `#e2e4e7`
- Padding: 8px 12px
- Radius: 6px
- Border: `1px solid rgb(36, 40, 44)`
- Hover: background shifts to `rgba(255,255,255,0.05)`
- Use: Standard actions, secondary CTAs

**Subtle**
- Background: `rgba(255,255,255,0.04)`
- Text: `#d0d6e0`
- Padding: 4px 8px
- Radius: 6px
- Use: Toolbar actions, contextual buttons

**Pill**
- Background: transparent
- Text: `#d0d6e0`
- Padding: 2px 10px
- Radius: 9999px
- Border: `1px solid rgb(35, 37, 42)`
- Use: Filter chips, tags, status indicators

**Small Toolbar**
- Background: `rgba(255,255,255,0.05)`
- Text: `#62666d`
- Radius: 2px
- Border: `1px solid rgba(255,255,255,0.05)`
- Font: 12px weight 510
- Use: Toolbar actions, quick-access controls

**Icon Button (Circle)**
- Background: `rgba(255,255,255,0.03)`
- Text: `#f7f8f8`
- Radius: 50%
- Border: `1px solid rgba(255,255,255,0.08)`
- Use: Close, toggle, icon-only actions

### Cards & Containers
- Background: `rgba(255,255,255,0.02)` to `rgba(255,255,255,0.05)` (always translucent, never solid)
- Border: `1px solid rgba(255,255,255,0.08)` (standard) or `rgba(255,255,255,0.05)` (subtle)
- Radius: 8px (standard), 12px (featured), 22px (large panels)
- Hover: subtle background opacity increase

### Data Tables
- Header row: `rgba(255,255,255,0.03)` background, Caption Large (14px weight 510) text in `#8a8f98`
- Body rows: transparent background, Body (16px weight 400) or Small (15px weight 400) text
- Row hover: `rgba(255,255,255,0.02)` background
- Row border: `1px solid rgba(255,255,255,0.05)` between rows
- Selected row: `rgba(94,106,210,0.08)` background (brand indigo tint)
- Sortable column header: `#d0d6e0` text with hover to `#f7f8f8`
- Cell padding: 8px 12px

### Status Badges
- Background: tinted variant of status color (see Status Colors, Recommendation Tier Colors)
- Text: primary variant of status color
- Padding: 2px 8px
- Radius: 9999px
- Font: 12px weight 510

### Pipeline Stage Cards (Dashboard)
- Left border: 3px solid stage primary color
- Background: `rgba(255,255,255,0.02)`
- Border: `1px solid rgba(255,255,255,0.08)`
- Radius: 8px
- Stage label: Caption Large in stage primary color
- Metric value: Heading 2 (24px weight 400) in `#f7f8f8`
- Metric label: Caption in `#8a8f98`

### Charts & Visualizations
- Background: transparent (sits on panel surface)
- Grid lines: `rgba(255,255,255,0.05)`
- Axis labels: Caption (13px weight 400–510) in `#62666d`
- Data series: pipeline stage colors for stage-related charts, brand indigo for aggregate metrics
- Tooltip: `#191a1b` background, `1px solid rgba(255,255,255,0.08)` border, 8px radius

### Inputs & Forms

**Text Input**
- Background: `rgba(255,255,255,0.02)`
- Text: `#d0d6e0`
- Placeholder: `#62666d`
- Border: `1px solid rgba(255,255,255,0.08)`
- Padding: 8px 12px
- Radius: 6px
- Focus: border shifts to `#7170ff`

**Text Area (Notes)**
- Same as text input, with min-height: 120px
- Monospace option for markdown editing: JetBrains Mono 14px

**Select / Dropdown**
- Trigger: ghost button styling
- Dropdown: `#191a1b` background, `1px solid rgba(255,255,255,0.08)` border, 8px radius
- Options: 15px weight 400, `#d0d6e0` text, hover `rgba(255,255,255,0.05)` background
- Selected: `#f7f8f8` text, `rgba(94,106,210,0.08)` background

**Filter Bar**
- Container: `rgba(255,255,255,0.02)` background, bottom border `1px solid rgba(255,255,255,0.05)`
- Filter pills: pill button styling with active state using brand indigo tint
- Active filter: `rgba(94,106,210,0.12)` background, `#7170ff` text
- Clear all: subtle button, `#8a8f98` text

### Navigation
- Sidebar: `#0f1011` background, full height
- Logo/wordmark: top of sidebar, `#f7f8f8`
- Nav items: 14px weight 510, `#8a8f98` text
- Active nav item: `#f7f8f8` text, `rgba(255,255,255,0.05)` background, left accent border `2px solid #7170ff`
- Section dividers: `1px solid rgba(255,255,255,0.05)` with 16px vertical margin

### Modals & Overlays
- Backdrop: `rgba(0,0,0,0.85)`
- Modal: `#191a1b` background, `1px solid rgba(255,255,255,0.08)` border, 12px radius
- Multi-layer shadow for depth
- Header: Heading 3 (20px weight 590), bottom border `rgba(255,255,255,0.05)`
- Close button: icon button in top-right
- Padding: 24px

## 5. Layout Principles

### Spacing System
- Base unit: 8px
- Scale: 4px, 8px, 12px, 16px, 20px, 24px, 32px, 48px, 64px
- Fine adjustments: 2px, 4px, 6px for icon/text micro-alignment

### Application Layout
- **Sidebar**: 240px wide, collapsible to 48px (icon-only)
- **Main content area**: fluid, max-width as needed per view
- **Dashboard grid**: CSS Grid, auto-fill columns with min 280px
- **Detail panels**: 50/50 or 60/40 split for list + detail views

### Whitespace Philosophy
- **Darkness as space**: The near-black background IS the whitespace. Content emerges from darkness through luminance steps.
- **Compressed text, open layout**: Dense headlines with generous surrounding margins create productive tension.
- **Section isolation**: Generous vertical padding (32px–48px) between sections. No visible dividers — background tone shifts provide natural separation.
- **Information density**: This is a tool, not a marketing site. Favor density over spaciousness in data views. Use the spacing scale to create clear hierarchy, not to push content apart.

### Border Radius Scale
- Micro (2px): Inline badges, toolbar buttons
- Standard (4px): Small containers, list items
- Comfortable (6px): Buttons, inputs
- Card (8px): Cards, dropdowns
- Panel (12px): Panels, featured cards
- Large (22px): Large panel elements
- Full Pill (9999px): Chips, filter pills, status tags
- Circle (50%): Icon buttons, status dots

## 6. Depth & Elevation

| Level | Treatment | Use |
|-------|-----------|-----|
| Flat (Level 0) | No shadow, `#08090a` bg | Page background |
| Subtle (Level 1) | `rgba(0,0,0,0.03) 0px 1.2px 0px` | Toolbar buttons |
| Surface (Level 2) | `rgba(255,255,255,0.05)` bg + border | Cards, inputs |
| Inset (Level 2b) | `rgba(0,0,0,0.2) 0px 0px 12px 0px inset` | Recessed panels |
| Ring (Level 3) | `rgba(0,0,0,0.2) 0px 0px 0px 1px` | Border-as-shadow |
| Elevated (Level 4) | `rgba(0,0,0,0.4) 0px 2px 4px` | Floating elements, dropdowns |
| Dialog (Level 5) | Multi-layer shadow stack | Modals, command palette |

**Shadow Philosophy**: On dark surfaces, elevation is communicated through background luminance steps — each level slightly increases white opacity (`0.02` → `0.04` → `0.05`). Semi-transparent white borders are the primary depth indicator. Shadows are supplementary, not primary.

## 7. Do's and Don'ts

### Do
- Use Inter with `"cv01", "ss03"` on ALL text
- Use weight 510 as default emphasis weight
- Apply negative letter-spacing at display sizes
- Build on near-black backgrounds with luminance stepping for elevation
- Use semi-transparent white borders (`rgba(255,255,255,0.05–0.08)`)
- Keep button backgrounds nearly transparent
- Reserve brand indigo for CTAs and interactive accents only
- Use pipeline stage colors consistently for their designated stages
- Use `#f7f8f8` for primary text, never pure `#ffffff`
- Favor information density in data views — this is a tool

### Don't
- Don't use pure white (`#ffffff`) as primary text
- Don't use solid colored backgrounds for buttons (transparency is the system)
- Don't apply brand indigo decoratively — it's for interactive elements only
- Don't use positive letter-spacing on display text
- Don't use visible/opaque borders on dark backgrounds
- Don't skip the OpenType features
- Don't use weight 700 (bold) — maximum is 590
- Don't introduce warm colors into the UI chrome — the palette is cool gray
- Don't use drop shadows as the primary elevation indicator on dark surfaces
- Don't sacrifice density for white space in data views — this is not a marketing site

## 8. Responsive Behavior

### Breakpoints
| Name | Width | Key Changes |
|------|-------|-------------|
| Compact | <768px | Sidebar collapses to icon-only, single column |
| Standard | 768–1280px | Full sidebar, responsive grid |
| Wide | >1280px | Full layout, generous content area |

### Collapsing Strategy
- Sidebar: full (240px) → icon-only (48px) → hamburger overlay on compact
- Dashboard grid: auto-fill with min 280px — naturally responsive
- Detail views: side-by-side → stacked on compact
- Data tables: horizontal scroll on compact, column priority (hide low-priority columns first)
- Charts: maintain aspect ratio, reduce labels on compact

## 9. Agent Implementation Guide

### Quick Color Reference
- Page background: `#08090a`
- Panel background: `#0f1011`
- Elevated surface: `#191a1b`
- Primary text: `#f7f8f8`
- Secondary text: `#d0d6e0`
- Muted text: `#8a8f98`
- Subtle text: `#62666d`
- Brand CTA: `#5e6ad2`
- Interactive accent: `#7170ff`
- Accent hover: `#828fff`
- Border default: `rgba(255,255,255,0.08)`
- Border subtle: `rgba(255,255,255,0.05)`
- Success: `#27a644`
- Warning: `#d97706`
- Error: `#cf2d56`

### Pipeline Stage Quick Reference
- Harvest: `#e0a862` / `rgba(224,168,98,0.12)`
- Dedup: `#9fc9a2` / `rgba(159,201,162,0.12)`
- Score: `#9fbbe0` / `rgba(159,187,224,0.12)`
- Promote: `#c0a8dd` / `rgba(192,168,221,0.12)`
- Cover Letter: `#dfa88f` / `rgba(223,168,143,0.12)`

### Design Token Implementation

All colors, spacing, and typography values in this document MUST be implemented as CSS custom properties or Tailwind theme extensions — not hardcoded in components. This enables future theme changes without rewriting component code.

```css
/* Example token structure — implement in tailwind.config or CSS variables */
:root {
  --color-bg-base: #08090a;
  --color-bg-panel: #0f1011;
  --color-bg-surface: #191a1b;
  --color-text-primary: #f7f8f8;
  --color-text-secondary: #d0d6e0;
  --color-text-tertiary: #8a8f98;
  --color-text-quaternary: #62666d;
  --color-brand: #5e6ad2;
  --color-accent: #7170ff;
  --color-accent-hover: #828fff;
  --color-border-default: rgba(255,255,255,0.08);
  --color-border-subtle: rgba(255,255,255,0.05);
  --color-success: #27a644;
  --color-warning: #d97706;
  --color-error: #cf2d56;
  --color-stage-harvest: #e0a862;
  --color-stage-dedup: #9fc9a2;
  --color-stage-score: #9fbbe0;
  --color-stage-promote: #c0a8dd;
  --color-stage-coverletter: #dfa88f;
}
```

### Key Implementation Notes
- This is an application UI, not a marketing site. Prioritize information density, data tables, filter bars, status badges, and chart containers.
- Every component in this spec should be buildable with React + Tailwind CSS.
- Use Recharts for data visualization. Apply chart styling from section 4.
- JetBrains Mono (open source) replaces Berkeley Mono from the original Linear spec.
- All interactive elements need clear hover and focus states — this is a keyboard-friendly tool.
