---
name: Industrial IoT Supervisory & Technician Control
colors:
  background: '#0B0F12'
  surface: '#121A20'
  border: '#22323D'
  primary: '#10B981'
  text: '#F1F5F9'
  muted: '#8197A4'
typography:
  display:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.025em
  section-header:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.015em
  card-title:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0em
  body:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  micro-caption:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.01em
  tech-code:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style
This design system provides an uncompromising, mission-critical operational interface for field technicians, compliance officers, and plant supervisors managing IoT-driven permit verification and hardware telemetry. Designed for high-stress, low-visibility industrial environments, the style fuses industrial utilitarianism with crisp data legibility.

The interface prioritizes instant cognitive parsing, verifiable states, and zero visual ambiguity. Visual clutter, decorative gradients, and micro-interactions that add latency are completely eliminated. The emotional tone is authoritative, fail-safe, and precise—resembling advanced avionics or specialized diagnostic hardware where every pixel serves operational safety.

## Colors
The system enforces a closed, six-token color architecture. No auxiliary tints, alphas, or decorative mid-tones are permitted outside this spectrum:

- **Canvas / Background (`#0B0F12`)**: The foundational deep slate surface. Establishes the optical floor for battery conservation on OLED field tablets and total contrast isolation.
- **Card / Container Surface (`#121A20`)**: The primary structural plane for panels, inspection modules, telemetry cards, and modal dialogs.
- **Border / Divider Stroke (`#22323D`)**: The rigid structural bounding line used for 1px structural framing, grid gutters, section separations, and inactive input outlines.
- **Primary / Verified State (`#10B981`)**: The single functional accent color. Denotes confirmed NFC telemetry, active safe permits, compliant hardware statuses, and primary operational triggers.
- **Primary Text / Foreground (`#F1F5F9`)**: The optical peak off-white tone. Used for system-critical metrics, page titles, interactive states, and active readings requiring instantaneous parsing under direct sunlight or headlamp glare.
- **Muted Text / Secondary Labels (`#8197A4`)**: The structural slate gray used for metadata, hardware IDs, descriptive subheadings, inactive labels, and auxiliary parameters.

## Typography
Typographic hierarchy is strictly constrained to 6 roles to prevent optical noise and enforce visual rhythm:

1. **Display / Page Title**: 24px/32px Bold (`Plus Jakarta Sans`), tight tracking. Used exclusively for top-level operational breadcrumbs and plant floor designations. Color: `#F1F5F9`.
2. **Section Header**: 18px/26px SemiBold (`Plus Jakarta Sans`). Used for major zone modules, sensor arrays, and batch permit lists. Color: `#F1F5F9`.
3. **Card Title / Form Label**: 14px/20px Medium (`Plus Jakarta Sans`). Structural header for telemetry cards, parameters, and input anchors. Color: `#F1F5F9`.
4. **Body Text**: 14px/22px Regular (`Plus Jakarta Sans`). Descriptive status narrative, procedure notes, and inspection instructions. Color: `#8197A4`.
5. **Meta / Micro Caption**: 12px/16px Medium (`Plus Jakarta Sans`). Timestamps, auxiliary metric units, and status hints. Color: `#8197A4`.
6. **Code / Tech Identifier**: 12px/16px SemiBold (`JetBrains Mono`). Standardized tracking-wide monospaced rendering for IoT hardware MACs, permit hashes, zone coordinates, and sensor registers. Color: `#F1F5F9` or `#10B981` when verified.

## Layout & Spacing
The layout model employs an industrial fluid-grid architecture anchored by an 8px base rhythm. Content conforms to high-density operational panels designed for rugged handheld tablets (portrait/landscape) and supervisory field monitors:

- **Desktop & Supervisory Consoles (1024px+)**: 12-column dynamic grid with a fixed 2rem outer canvas margin and 1.5rem gutters. Heavy density allows side-by-side verification: floor layout, real-time permit stream, and technician telematics.
- **Tablet & Mobile Handhelds (<1024px)**: Single or dual-column stacked layout with 1rem canvas margins and 1rem gutters. All actionable touch targets measure at least 48px to accommodate gloved operation.
- **Component Padding Scale**: Internal card padding uses `space-md` (1rem) for standard cards and `space-lg` (1.5rem) for high-priority emergency controls. Element adjacency (label-to-input, icon-to-metric) is locked strictly to `space-xs` (4px) or `space-sm` (8px).

## Elevation & Depth
Depth is produced strictly through tonal layering and structural outlines—never drop shadows, glows, or synthetic blurs. 

- **Ground Canvas**: `#0B0F12` acts as the unlit mechanical baseline.
- **Active Structural Planes**: `#121A20` containers define cards, panels, and data surfaces.
- **Separation & Bounding**: A crisp 1px solid stroke of `#22323D` outlines every individual card, table row, panel boundary, and module separator. This flat, structural border system provides military-grade contrast delineation in bright ambient conditions or pitch-black industrial enclosures.
- **Focused / Elevated State**: Interactive elements in focus or high-priority warning do not elevate along a z-axis; instead, their perimeter stroke shifts crisply from `#22323D` to `#10B981`.

## Shapes
A conservative, structural roundedness level of `1` (0.25rem / 4px) is utilized system-wide. This slight radius prevents harsh jagged corners on industrial touchscreen glass while avoiding the soft, consumer-app aesthetic of pill or high-radius shapes. 

Containers, inputs, status badges, and buttons maintain uniform 4px outer radiuses. Dividers, data telemetry bars, and status indicator dots remain strictly rectangular or circle-bounded (e.g. 8px pulse dot).

## Components

### Buttons
- **Primary / Actionable Trigger**: Solid `#10B981` background, `#0B0F12` text (Medium 14px), 4px border radius. Padding: 10px 16px. Active/Hover state deepens boundary without shifting hues.
- **Secondary / Operational Neutral**: Solid `#121A20` background, 1px `#22323D` border, `#F1F5F9` text. On hover, the border transitions to `#8197A4`.

### Cards & Telemetry Containers
- Built on `#121A20` with a persistent 1px `#22323D` border. Header regions contain a 14px Card Title (`#F1F5F9`) alongside an auxiliary Tech Identifier (`#8197A4`). Internal content dividers use 1px solid `#22323D`.

### Verification Badges & Status Chips
- **Verified / Safe**: 1px solid `#10B981` outline enclosing `#121A20` background. Label set in 12px Code/Tech Identifier in `#10B981` text accompanied by a solid 6px `#10B981` status square.
- **Pending / Inactive**: 1px solid `#22323D` outline, `#121A20` background, `#8197A4` text.

### Form Inputs & NFC Scanner Fields
- **Container**: `#0B0F12` background framed in 1px `#22323D`. Height: 44px.
- **Typography**: Entered text in `#F1F5F9` (14px Body). Placeholder text in `#8197A4`.
- **Active / Scan State**: Border immediately transitions to 1px `#10B981` stroke.

### Data Lists & Audit Logs
- Structured with alternating or consistent `#121A20` rows separated by 1px `#22323D` bottom borders. Left column anchors the Monospace Tech ID (`#10B981` or `#F1F5F9`), center column displays Body Text notes (`#8197A4`), and right column preserves timestamps in Micro Caption (`#8197A4`).