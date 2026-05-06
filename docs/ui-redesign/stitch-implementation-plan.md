# Stitch UI Implementation Plan

## Source

- Stitch export root: `docs/ui-redesign/stitch_ui`
- Design tokens: `docs/ui-redesign/stitch_ui/playful_imagery_hub/DESIGN.md`

## Page Mapping

| Stitch page | Mini Program page | Purpose |
| --- | --- | --- |
| `_1` | `miniprogram/pages/index/index` | Home |
| `_2` | `miniprogram/pages/ai/index` | Feature detail: palm reading |
| `_3` | `miniprogram/pages/ai/upload/index` | Upload photo |
| `_4` | `miniprogram/pages/ai/progress/index` | Generating |
| `_5` | `miniprogram/pages/ai/result/index` | Result |
| `_6` | `miniprogram/pages/mine/task-detail` | Task detail |
| `_7` | `miniprogram/pages/mine/tasks` | Generation records |
| `_8` | `miniprogram/pages/mine/index` | Mine |
| `_9` | Shared components/pages | Popups and earn-points modules |

## Token Mapping

Stitch uses CSS pixels. Mini Program styles use `rpx`.

- General conversion: `1px ~= 2rpx`
- Page horizontal margin: `20px -> 40rpx`
- Card padding: `16px -> 32rpx`
- Small gap: `8px -> 16rpx`
- Medium gap: `16px -> 32rpx`
- Large gap: `24px -> 48rpx`
- Primary card radius: `20px -> 40rpx`
- Large card radius: `24px -> 48rpx`

Do not mechanically convert safe areas, top navigation, tabBar, or fixed bottom docks. Those must be adapted to WeChat Mini Program behavior.

## Global Tokens

| Token | Value | Mini Program variable |
| --- | --- | --- |
| Background | `#FBFCF8` | `--ui-bg` |
| Surface | `#F3FCF2` | `--ui-surface` |
| Card | `#FFFFFF` | `--ui-card` |
| Text | `#17211B` | `--ui-text` |
| Muted text | `#8A938D` | `--ui-muted` |
| Primary | `#15C77A` | `--ui-primary` |
| Primary dark | `#006D40` | `--ui-primary-dark` |
| Accent | `#F6A512` | `--ui-accent` |
| Error | `#D85043` | `--ui-error` |
| Outline | `#BBCABD` | `--ui-outline` |

## Mini Program Adaptation Rules

1. Keep the native Mini Program tabBar. Do not port Stitch's web tab bar into pages.
2. Tab pages use page content titles and top padding. Avoid custom headers that collide with the WeChat capsule.
3. Secondary pages use one shared custom navigation pattern and reserve space for the capsule.
4. Keep current business logic intact. UI implementation should preserve cloud calls, upload flow, task polling, result save, share rewards, and check-in behavior.
5. Do not use Stitch external image URLs in production pages. Use existing cloud preview images or local assets in `miniprogram/images`.
6. Rebuild each page as a coherent page from Stitch structure instead of applying small patches to old styles.
7. Validate after every page with `node --check` for changed JS and `git diff --check`.

## Implementation Order

1. Global tokens and shared utilities
2. Home (`_1`)
3. Generation records (`_7`)
4. Mine (`_8`)
5. Feature detail (`_2`)
6. Upload (`_3`)
7. Generating (`_4`)
8. Result (`_5`)
9. Task detail (`_6`)
10. Popups and earn-points modules (`_9`)

## Current Status

- [x] Global tokens and shared utilities
- [x] Home
- [x] Generation records
- [x] Mine
- [x] Feature detail
- [x] Upload
- [x] Generating
- [x] Result
- [x] Task detail
- [x] Popups and earn-points modules
