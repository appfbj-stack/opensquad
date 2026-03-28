---
name: opensquad-dashboard-design
description: Use when creating, modifying, or designing 2D virtual office scenes for the opensquad dashboard — room layouts, furniture placement, avatar integration, environment design, or any visual improvement. Also use when the dashboard looks empty, flat, lifeless, or lacks personality.
---

# Opensquad Dashboard Design — Visual Office Workflow

Design and improve the opensquad dashboard's 2D virtual office through a structured workflow with visual verification. Every change is screenshot-verified before completion.

## Workflow

Follow these 6 phases in order. Do NOT skip phases or implement without diagnosis.

> **Phase 7 — FULL SPRITE REVIEW** is an optional audit phase triggered only when the user explicitly requests a full sprite audit (e.g. "faz o full sprite review", "revisa todos os sprites"). When triggered, it replaces phases 2–6 for that session.

### Phase 1: UNDERSTAND

- Read the user's request carefully
- Identify what they want: layout change, new furniture, atmosphere fix, specific problem
- If the request is ambiguous, ask ONE clarifying question before proceeding
- Do NOT start implementing — move to Phase 2

### Phase 2: DIAGNOSE

Take a screenshot of the current dashboard state before any changes.

**Auto-detect dashboard URL:**
1. Check `dashboard/vite.config.ts` for `server.port`
2. Check `dashboard/package.json` scripts for `--port` flags
3. Fallback: `http://localhost:5173` (Vite default)

**Take screenshot via Playwright CLI** (Bash tool, NOT MCP Playwright tools):
```bash
npx playwright screenshot --browser chromium "URL" "/tmp/dashboard-before.png" --full-page
```
If `npx playwright screenshot` is unavailable, use a small inline Playwright script.

**If URL is unreachable:** tell the user to run `cd dashboard && npm run dev`.

**Analyze the screenshot:**
- Identify visible problems (empty zones, depth issues, floating sprites, poor framing)
- Emphasize problems related to the user's specific request
- Present findings to the user WITH the screenshot image

### Phase 3: PLAN

Based on diagnosis, propose an action plan:
- List specific changes grouped by file/area
- Group related changes together (independent groups can be parallelized)
- Ask clarifying questions if the diagnosis revealed ambiguity
- **WAIT for explicit user approval before proceeding to Phase 4**

### Phase 4: IMPLEMENT

**Group changes by independence:**
- Group A: `RoomBuilder.ts` (furniture placement, layout)
- Group B: `assetKeys.ts` + copy new asset files to `dashboard/public/assets/`
- Group C: `palette.ts` (colors, constants)
- Group D: `AgentSprite.ts` (animations, badges)

**Dispatch subagents** in parallel for independent groups. Each subagent receives:
- Description of changes to make
- The critical rules from the "Quick Reference" section below
- Instruction: read `.claude/skills/opensquad-dashboard-design/reference.md` if you need the asset catalog or code examples

**Respect dependencies:** assets copied first → keys registered in assetKeys.ts → placement in RoomBuilder.ts → visual adjustments.

### Phase 5: VERIFY

**Layer 1 — Screenshot:**
```bash
npx playwright screenshot --browser chromium "URL" "/tmp/dashboard-after.png" --full-page
```

**Layer 2 — Automated quality checklist:**
- [ ] No large empty zones visible
- [ ] Wall decorated (at least 1 item per wall section)
- [ ] Plants in corners (minimum 4)
- [ ] Lounge zone exists with seating + table + rug (if applicable)
- [ ] Depth sorting correct (lower objects render on top of higher ones)
- [ ] Sprite variety (max 2 identical items visible)
- [ ] Camera frames the room well with breathing room
- [ ] No hyperactive flickering or distracting animations

**Layer 3 — User approval:**
Present to the user:
1. The after-screenshot
2. Summary of what changed
3. Checklist results (pass/fail per item)

Ask: "O resultado ficou como esperado? Posso finalizar ou quer ajustes?"

- User approves → **DONE**
- User wants adjustments → Phase 6

### Phase 6: LOOP

- Collect the user's specific feedback
- Create a NEW focused plan addressing only the points raised
- Return to **Phase 4** (IMPLEMENT)
- Then **Phase 5** (VERIFY)
- Repeat until user approves

## Quick Reference

### Key Files

| File | Purpose |
|------|---------|
| `dashboard/src/office/OfficeScene.ts` | Main Phaser scene — loads assets, builds room, places agents |
| `dashboard/src/office/RoomBuilder.ts` | Procedural floor/walls + sprite furniture placement |
| `dashboard/src/office/AgentSprite.ts` | Per-agent: desk sprite + avatar sprite + name badge + status |
| `dashboard/src/office/assetKeys.ts` | Asset manifest — all sprite keys and file paths |
| `dashboard/src/office/palette.ts` | Colors (status badges, floor, wall) + layout constants |
| `dashboard/src/office/PhaserGame.tsx` | React wrapper — Phaser game initialization |

### Layout Constants (palette.ts)

TILE   = 32   // Base grid unit (px)
CELL_W = 96   // 3 tiles — desk cell width
CELL_H = 96   // 3 tiles — desk cell height
MARGIN = 96   // 3 tiles — room edge padding
WALL_H = 96   // 3 tiles — wall strip height

### Depth Sorting

Y-based painter's algorithm — objects lower on screen render on top:

  Wall decorations:  setDepth(0)          — behind everything
  Rugs:              setDepth(-0.5)       — below furniture, above floor
  Floor furniture:   setDepth(y)          — Y position
  Agent desk:        setDepth(y)          — Y position
  Avatar:            setDepth(y + 1)      — on top of desk
  Name badge:        setDepth(y + 99/101) — always on top

**Rule:** anything closer to the bottom of the screen gets a higher depth value.

### Sprite Placement

  // WALL DECORATIONS — anchor to bottom of wall, depth 0
  scene.add.image(x, WALL_H, key).setOrigin(0.5, 1).setDepth(0);

  // FLOOR ITEMS — anchor to bottom of sprite, depth = Y
  scene.add.image(x, y, key).setOrigin(0.5, 1).setDepth(y);

  // UNDER FURNITURE (rugs) — depth = -0.5
  scene.add.image(x, y, key).setOrigin(0.5, 0.5).setDepth(-0.5);

**Origin conventions:**
- Wall items: `setOrigin(0.5, 1)` — bottom-center anchored to wall base
- Floor items: `setOrigin(0.5, 1)` — bottom-center for correct Y-sorting
- Rugs/carpets: `setOrigin(0.5, 0.5)` — center-anchored

**Relative positioning** — never hardcode pixels:
- `roomW / 2` for centered items
- `MARGIN / 2` for corner items
- `roomW / N` for evenly spaced wall decorations
- `deskAreaBottom + offset` for lounge zone items

### Visual Density

| Zone | Minimum Items | Examples |
|------|--------------|----------|
| Wall (per 5 sections) | 5 | blinds, bookshelf, whiteboard, clock, poster |
| Work area corners | 2 per corner | plant + flowers, or plant + trash can |
| Lounge zone | 4+ | couch + coffee table + rug + 2 plants |
| Between desk rows | 1 per gap | floor cushion, small plant, backpack |
| Room edges | 1 per 3 tiles | plants, lamps, small furniture |

## Important Rules

- **NEVER create pixel art from scratch** — always use existing assets from `dashboard/public/assets/` or the asset pack in `temp/pixel-assets/town/`
- **Every new sprite must be registered** in `assetKeys.ts` (FURNITURE_KEYS + FURNITURE_PATHS)
- **Consult reference.md** (`.claude/skills/opensquad-dashboard-design/reference.md`) for the full asset catalog, code examples, and detailed technical guidance during implementation
