---
name: Playful Imagery Hub
colors:
  surface: '#f3fcf2'
  surface-dim: '#d4dcd3'
  surface-bright: '#f3fcf2'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#edf6ec'
  surface-container: '#e8f0e7'
  surface-container-high: '#e2eae1'
  surface-container-highest: '#dce5db'
  on-surface: '#161d18'
  on-surface-variant: '#3c4a40'
  inverse-surface: '#2a322c'
  inverse-on-surface: '#ebf3e9'
  outline: '#6c7b6f'
  outline-variant: '#bbcabd'
  surface-tint: '#006d40'
  primary: '#006d40'
  on-primary: '#ffffff'
  primary-container: '#15c77a'
  on-primary-container: '#004c2b'
  inverse-primary: '#42e090'
  secondary: '#825500'
  on-secondary: '#ffffff'
  secondary-container: '#fdab1b'
  on-secondary-container: '#694300'
  tertiary: '#ad3128'
  on-tertiary: '#ffffff'
  tertiary-container: '#ff8f81'
  on-tertiary-container: '#84120f'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#65feaa'
  primary-fixed-dim: '#42e090'
  on-primary-fixed: '#002110'
  on-primary-fixed-variant: '#00522f'
  secondary-fixed: '#ffddb4'
  secondary-fixed-dim: '#ffb953'
  on-secondary-fixed: '#291800'
  on-secondary-fixed-variant: '#633f00'
  tertiary-fixed: '#ffdad5'
  tertiary-fixed-dim: '#ffb4aa'
  on-tertiary-fixed: '#410001'
  on-tertiary-fixed-variant: '#8c1813'
  background: '#f3fcf2'
  on-background: '#161d18'
  surface-variant: '#dce5db'
typography:
  h1:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  h2:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  h3:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
  body-lg:
    fontFamily: Be Vietnam Pro
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Be Vietnam Pro
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  margin-page: 20px
  gutter: 12px
---

## Brand & Style

The design system is built to reflect the "Playful Imagery Hub" (玩图局) personality: a blend of youthful creativity and modern technical polish. It targets a Gen-Z and Millennial demographic that values quick, delightful interactions and "share-worthy" visual outputs.

The primary style is **Modern Minimalism with Tactile Accents**. It leverages the clean, spacious qualities of high-end app design while introducing "playful" elements through soft organic shapes, vibrant color pops, and subtle depth. The goal is to evoke a sense of "digital lightness"—the interface should feel as effortless as an airy conversation, ensuring the user's photos and AI-generated results remain the hero of the experience.

## Colors

This design system utilizes a refreshing "Nature-Modern" palette. 

- **Primary Green (#15C77A):** Used for primary actions, success states, and brand recognition. It feels organic yet digital.
- **Warm Yellow (#F6A512):** Acts as a high-visibility accent for rewards, highlights, and secondary calls to action.
- **Off-White Background (#FBFCF8):** A "paper-like" white that is softer on the eyes than pure #FFFFFF, providing a premium, editorial feel.
- **Deep Slate Text (#17211B):** Provides high legibility without the harshness of pure black, maintaining the "soft" brand tone.
- **Sage Grey (#8A938D):** Used for metadata, placeholders, and inactive states to maintain a clean hierarchy.

## Typography

The typography system prioritizes clarity and a friendly, rounded aesthetic. 

- **Headlines:** Use **Plus Jakarta Sans** for its modern, geometric, and welcoming curves. It excels in short, punchy WeChat Mini Program headers.
- **Body Text:** Uses **Be Vietnam Pro**, which offers high legibility at small sizes while maintaining a contemporary, social-media-friendly vibe.
- **Chinese Characters:** Default to **PingFang SC** for macOS/iOS and **Microsoft YaHei** for general environments, ensuring weight matching with the Latin fonts (Bold for H1/H2, Regular for Body).
- **Hierarchy:** Strict adherence to 4px spacing between text levels to maintain the 8pt rhythm.

## Layout & Spacing

This design system employs a **Fluid-Safe Grid** model. While the layout adapts to different screen widths (iPhone SE to Pro Max), it maintains a fixed **20px side margin** to create a "contained" and tidy appearance.

- **8pt Grid:** All internal padding and component heights must be multiples of 8 (8, 16, 24, 32...).
- **Vertical Rhythm:** Components are separated by `lg` (24px) spacing, while internal elements use `sm` (8px) or `md` (16px).
- **Safe Areas:** Adhere strictly to WeChat's top capsule menu safe area and bottom home indicator area.

## Elevation & Depth

To maintain a "lightweight" feel, the system avoids heavy borders and uses **Tonal Layering** combined with **Ambient Shadows**.

- **Shadows:** Use extremely soft, low-opacity shadows. 
  - *Value:* `0px 4px 20px rgba(23, 33, 27, 0.04)`.
  - The shadow color should ideally be a darker tint of the background color rather than pure black.
- **Surface Tiers:**
  - **Level 0 (Background):** #FBFCF8.
  - **Level 1 (Cards):** #FFFFFF.
  - **Level 2 (Popups/Modals):** #FFFFFF with a slightly more pronounced shadow (8% opacity).
- **Glassmorphism:** Use only for fixed headers or bottom navigation bars with a high-intensity backdrop blur (20px) and 80% opacity on the surface color.

## Shapes

The shape language is defined by "Friendly Precision"—very rounded but structured.

- **Large Cards:** 20px (`rounded-lg`) for main content containers (e.g., image previews, result cards).
- **Standard Buttons:** 24px (`rounded-xl`) height-based rounding, creating a soft, clickable feel.
- **Interactive Elements:** Full capsule rounding (pill-shape) for chips, tags, and small utility buttons.
- **Icons:** Use rounded caps and joins with a 2px stroke weight to match the UI's softness.

## Components

### Buttons
- **Primary:** Solid #15C77A with white text. High contrast, 24px corner radius.
- **Secondary:** Ghost style or #F6A512 for specific "reward" actions.
- **Loading:** Integrated spinner within the primary button to maintain the "one-tap" flow.

### Cards
- White background (#FFFFFF) with 20px corner radius and ambient shadow.
- Content should have 16px internal padding.
- Avoid borders; use light grey (#F0F2EE) separators only if absolutely necessary.

### Lists & Items
- Use "Tile" layouts for the home grid.
- List items in the "Record" page should use horizontal layouts with a clear status badge (Completed, Failed, Processing) in the top right.

### Input & Interaction
- **Upload Zone:** Dashed primary-color border with a soft green tint background. 
- **Progress Bars:** Thick, rounded bars using #15C77A on a light grey track.
- **Modals:** Center-aligned with a dark overlay (40% opacity). Use the same 20px rounding as cards.

### Chips & Tags
- Used for categories (e.g., "Trending", "Portrait"). 
- Active state: Primary color text/border. 
- Inactive: Secondary text color on a very light grey-green background.