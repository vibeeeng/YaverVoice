---
name: YaverVoice
description: A compact desktop voice workspace with soft signal color, calm depth, and explicit processing states.
colors:
  background: "#10151A"
  surface: "#151B20"
  surface-raised: "#1A2228"
  surface-selected: "#26312F"
  border: "#2C353D"
  border-strong: "#3A464E"
  text: "#EDF1F2"
  text-muted: "#8F9AA2"
  text-secondary: "#BCC5CA"
  accent: "#70CFBD"
  accent-ink: "#10201D"
  creative: "#8F85F5"
  recording-danger: "#DB6A78"
  processing-warning: "#C69B4D"
typography:
  headline:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "24px"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "normal"
  title:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "18px"
    fontWeight: 800
    lineHeight: 1.25
    letterSpacing: "normal"
  body:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.42
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: "normal"
rounded:
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "12px"
  pill: "999px"
spacing:
  2xs: "4px"
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "36px"
  button-secondary:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "36px"
  button-danger:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.recording-danger}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "36px"
  icon-button:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.md}"
    height: "36px"
    width: "36px"
  input:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0 8px"
    height: "36px"
  navigation-active:
    backgroundColor: "{colors.surface-selected}"
    textColor: "{colors.accent}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "6px 4px"
    height: "52px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "16px"
---

# Design System: YaverVoice

## 1. Overview

**Creative North Star: "Soft Signal Studio"**

YaverVoice is a focused desktop studio: dark enough for sustained microphone, file, Docs, Converter, Library, and Settings work, but never cold, anonymous, or gamer-coded. Its energy comes from a soft signal accent, clear semantic color, the rhythm of compact controls, and small state-responsive motion. The interface must feel creative and alive without asking the user to watch the design instead of completing a task.

The stable documented core is the single sans-serif stack, compact spacing scale, restrained corner scale, and repeated component vocabulary. The extracted root palette is the current renderer baseline, not an immutable future palette. Literal colors, 7px radii, and one-off compact patterns elsewhere in the current stylesheet are implementation drift, not new design tokens. The main Electron/React renderer is in scope; the separate Quick Dictation surface is explicitly excluded.

Soft Signal Studio rejects the generic, sterile utility; the neon or gamer interface; the over-decorated concept product; and the oversized, sparsely populated dashboard. It uses familiar desktop affordances, balanced density, and explicit status language. Color always works with labels, icons, shape, or supporting text so Groq Cloud, Local Whisper, local processing, cloud processing, progress, success, warning, recording, and error states remain understandable without color perception.

**Key Characteristics:**

- Layered charcoal surfaces with a cool, low-chroma foundation.
- Soft mint signal color used for action and selection, not ambient decoration.
- Recording coral and processing amber reserved for named operational states.
- Compact 36–40px controls, a 96px application rail, a 48px top bar, and bounded workspaces that preserve scanning speed.
- State-driven transitions with immediate reduced-motion fallbacks.
- Signal Violet used sparingly for brand and creative context inside a stable product vocabulary.

## 2. Colors

The current palette pairs cool charcoal depth with a soft mint signal, a non-semantic Signal Violet accent, and two explicit operational colors. The frontmatter is the canonical record of the renderer today, not a locked redesign target. One-off blue-gray, bright-cyan, green, orange, and translucent literals in the current stylesheet are audit evidence, not reusable color roles.

### Primary

- **Soft Signal Mint** (`{colors.accent}`): Primary actions, current navigation or tab selection, focus outlines, ready or completed states, and progress fill. Its rarity keeps it meaningful.
- **Deep Mint Ink** (`{colors.accent-ink}`): High-contrast text and icons placed directly on Soft Signal Mint.

### Secondary

- **Signal Violet** (`{colors.creative}`): Brand and creative context such as the logo field, Docs studio signature, provider-kind icons, and informational toast icon. It never communicates provider selection or operational state.
- **Recording Coral** (`{colors.recording-danger}`): Active recording, stop actions, destructive emphasis, and error states. Pair it with an icon and explicit label such as “Recording,” “Stop,” or “Error.”

### Tertiary

- **Processing Amber** (`{colors.processing-warning}`): In-progress work, warnings, unlocked editing, and attention states that are neither success nor failure. Pair it with status copy or progress information.

### Neutral

- **Night Slate** (`{colors.background}`): Application canvas and the deepest progress tracks.
- **Charcoal Surface** (`{colors.surface}`): Sidebar, top bar, primary panels, settings groups, and stable content containers.
- **Raised Graphite** (`{colors.surface-raised}`): Controls, secondary actions, inputs, and surfaces that sit one level above a panel.
- **Quiet Teal Slate** (`{colors.surface-selected}`): Selected and active rows where a filled accent would be too strong.
- **Soft Graphite Line** (`{colors.border}`): Default dividers and container boundaries.
- **Firm Graphite Line** (`{colors.border-strong}`): Interactive boundaries and stronger grouping.
- **Frosted White** (`{colors.text}`): Headings, primary values, input content, and body copy.
- **Slate Mist** (`{colors.text-muted}`): Secondary explanations and metadata; verified above AA contrast on Night Slate and Charcoal Surface.
- **Clouded Silver** (`{colors.text-secondary}`): Interactive secondary copy and labels that need more prominence than Slate Mist.

**The Signal, Not Decoration Rule.** Soft Signal Mint is reserved for primary action, selection, focus, readiness, completion, and progress. Never scatter it as ornamental glow.

**The Named State Rule.** Color never carries meaning alone. Every semantic color requires a visible word, icon, progress value, control label, or state description.

**The Deliberate Secondary Accent Rule.** Signal Violet supports brand and creative context only. It never represents provider, selection, success, error, warning, recording, or processing state.

## 3. Typography

**Display Font:** None; product UI does not use a separate display face.
**Body Font:** Inter with the committed system sans-serif fallback stack.
**Label/Mono Font:** The body stack for controls; the platform monospace stack only for timestamps, paths, logs, and Markdown preview content.

**Character:** One compact sans-serif family keeps dense workflows familiar and stable. Energy comes from weight, hierarchy, color, and interaction—not from decorative type pairing. Inter is named in CSS but not bundled, so the fallback stack is part of current behavior and must not be treated as an accidental exception.

### Hierarchy

- **Headline** (`{typography.headline}`): Workspace titles only. Keep the scale fixed; product headings do not use fluid `clamp()` sizing.
- **Title** (`{typography.title}`): Workflow, settings-category, empty-state, and dialog titles.
- **Body** (`{typography.body}`): Transcript content and longer explanations. Cap prose at roughly 65–75 characters where the layout permits; data and file paths may run wider.
- **Label** (`{typography.label}`): Buttons, fields, tabs, navigation, metadata, and compact status copy.
- **Microcopy:** 11px is allowed for secondary status, logs, paths, and dense metadata only; it must retain AA contrast and must not become the default body size.

**The One Working Voice Rule.** Use the single sans stack across UI labels, buttons, headings, and body text. Monospace is functional, never decorative.

**The No Eyebrow Scaffold Rule.** Repeated tiny uppercase, widely tracked eyebrow labels are not a reusable section primitive. Existing instances are implementation history, not permission to place one above every heading.

**The Fixed Product Scale Rule.** Typography remains fixed across renderer breakpoints. Responsive behavior changes structure and wrapping, not heading drama.

## 4. Elevation

YaverVoice is tonal and layered by default. Night Slate, Charcoal Surface, Raised Graphite, Quiet Teal Slate, and line strength establish depth without making every group a floating card. Dialogs, popovers, and toasts share the existing structural floating shadow; it is reserved for genuine overlays and must not spread to ordinary panels or buttons.

### Shadow Vocabulary

- **Surface Inset:** A faint one-pixel top highlight appears on a limited set of legacy panels. Treat it as optional surface texture, never pair it with a large decorative drop shadow.
- **Floating Layer:** Dialogs, popovers, and toasts share `0 18px 48px rgba(0, 0, 0, 0.34)` over Raised Graphite. It is a floating-only treatment, not a reusable panel or control shadow.

**The Tonal-First Rule.** At-rest panels are flat. Use background level and boundary strength before shadow.

**The Float Only When Floating Rule.** Dialogs, popovers, and toasts may rise. Sidebar items, settings groups, file rows, buttons, and cards stay grounded.

## 5. Components

Components are tactile, clear, and controlled. The 36px compact control is the default, while primary navigation and high-frequency settings rows use 40–52px heights. WCAG 2.2 AA is achieved through contrast, visible focus, keyboard behavior, and sufficient target area without inflating every surface.

### Buttons

- **Shape:** Gently curved controls use `{rounded.md}`; full circles are reserved for the main record control and true icon geometry.
- **Primary:** Soft Signal Mint with Deep Mint Ink, `{components.button-primary}`. Use one clear primary action per local workflow region.
- **Hover / Focus:** Hover strengthens the boundary without decorative lift. Keyboard focus uses a visible two-pixel Soft Signal Mint outline with a two-pixel offset. Active state must provide immediate tactile feedback; disabled state remains legible and visibly inactive.
- **Secondary / Ghost / Tertiary:** Secondary actions use Raised Graphite and a firm boundary. Text actions remain transparent but keep a 36px target. Danger actions use Recording Coral plus explicit destructive copy.

### Chips

- **Style:** Status and metadata chips use pill geometry only when the content is genuinely compact and categorical.
- **State:** Success, missing, recording, processing, selected order, and chunk state always include text or an icon. Pills are not decorative tags.

### Cards / Containers

- **Corner Style:** Stable groups use `{rounded.lg}`; compact subpanels use `{rounded.md}`; the capture surface alone may use `{rounded.xl}`.
- **Background:** Charcoal Surface is the default group; Raised Graphite is reserved for controls and nested interactive regions.
- **Shadow Strategy:** Follow the tonal-first elevation system. Do not pair a one-pixel border with a wide soft shadow on ordinary containers.
- **Border:** Soft Graphite Line is the default; Firm Graphite Line indicates interaction or stronger grouping.
- **Internal Padding:** `{spacing.md}` to `{spacing.lg}` for normal groups and `{spacing.xl}` only for high-focus work areas or deliberate empty states.

### Inputs / Fields

- **Style:** Raised Graphite, Frosted White, a firm one-pixel boundary, `{rounded.md}`, and a 36px default height. Labels remain visible above fields; placeholder text is never the only label.
- **Focus:** A Soft Signal Mint border and visible focus ring reinforce native keyboard focus.
- **Error / Disabled:** Use explicit message text and semantic iconography with Recording Coral or Slate Mist. Never rely on border color alone.

### Navigation

- **Style:** The primary app rail is a fixed 96px column with icon-plus-label items and Settings anchored last. Default items use Clouded Silver; hover and current-page states use Quiet Teal Slate, a stronger boundary, and Soft Signal Mint.
- **Secondary navigation:** File workflows use a low-profile tab row; Settings uses a 160px category rail that becomes a five-column strip below the compact breakpoint.
- **Keyboard:** Every navigation control exposes native button semantics, visible focus, and `aria-current` or selected state where applicable.

### Segmented Controls

- **Style:** Use segmented controls only for mutually exclusive modes such as Quick Dictation versus Record or Hold-to-talk versus Toggle. The containing track is grounded; the selected segment uses Quiet Teal Slate or Soft Signal Mint according to emphasis.
- **Behavior:** Provide tab or button semantics, selected state, and complete keyboard access. Never use a segmented control as a decorative filter strip.

### Provider Choice

- **Style:** Groq Cloud and Local Whisper are peer choices, never a hidden fallback relationship. Each option includes provider name, processing-location description, selected state, and sufficient target area.
- **Behavior:** The active provider is communicated by text and selected semantics in addition to color. Local and cloud data handling must remain visible wherever the choice affects user trust.

### Processing Context

- **Files modes:** Transcribe shows the selected transcription provider and location. Create Notes shows both the selected transcription boundary and the separate Groq Cloud notes-generation boundary. Convert shows only FFmpeg media conversion as on-device processing.
- **Compact context:** Capture and the top bar retain the selected transcription provider without extra visual copy; their accessible name explicitly identifies transcription, provider, and location. Context groups wrap without hiding visible meaning.

### Progress, Toasts, and Dialogs

- **Progress:** Show a label, numeric percentage when known, track, and semantic outcome. Background progress remains actionable and returns users to the source workflow.
- **Toasts:** Short operational feedback appears above content without replacing persistent error or readiness information. Success, error, warning, and info messages pair their unchanged copy with a distinct icon so color is never the only state cue.
- **Dialogs:** Modal information is reserved for focused provider or dependency explanations. The shared ModalSurface provides initial focus, Tab and Shift+Tab containment, Escape handling, focus return, optional backdrop dismissal, an explicit close control in each consumer, and reduced-motion behavior.

## 6. Do's and Don'ts

### Do:

- **Do** use Signal Violet only for brand and creative context while preserving the fixed product type scale, the 4/6/8/12/16/24 spacing rhythm, and the 6/8/10/12 corner hierarchy.
- **Do** keep important controls compact but comfortably targetable: 36px for standard controls, 40px for tabs and category navigation, and 52px for primary rail items.
- **Do** use Soft Signal Mint for primary action, selection, focus, readiness, completion, and progress—not ambient decoration.
- **Do** pair every recording, processing, success, warning, local, cloud, and error color with text, an icon, semantics, or a numeric value.
- **Do** preserve visible keyboard focus, complete keyboard access, AA contrast, and `prefers-reduced-motion` fallbacks.
- **Do** use the 900px and 1100px structural breakpoints to collapse columns and reflow controls while keeping typography fixed.
- **Do** preserve every feature and workflow across Capture, Files, Library, Docs, Converter, and Settings while improving hierarchy.

### Don't:

- **Don't** make YaverVoice resemble a “generic, sterile utility,” a “neon or gamer interface,” an “over-decorated concept product,” or an “oversized, sparsely populated dashboard.”
- **Don't** use Signal Violet for provider, selection, success, error, warning, recording, or processing state.
- **Don't** turn every group into a bordered card, nest cards for layout, or combine a one-pixel border with a wide decorative shadow.
- **Don't** use colored side-stripe borders, gradient text, decorative glassmorphism, repeating stripe backgrounds, or hand-drawn fallback illustrations.
- **Don't** repeat tiny uppercase tracked eyebrows or numbered section markers as page scaffolding.
- **Don't** use color as the sole carrier of processing location, provider, selection, recording, warning, completion, or error meaning.
- **Don't** invent new radius, spacing, shadow, or literal color values when a documented token covers the need.
- **Don't** use decorative motion, orchestrated page-load sequences, bounce, elastic easing, or transitions that ignore reduced-motion preferences.
- **Don't** modify or derive design rules from the separate Quick Dictation window in this renderer-focused system.
