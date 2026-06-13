# Aesthetic Spec — "Soft-Stylised Dimetric HK"

**LOCKED** (2026-06-13, from the styling-DNA workflow that extracted jubuddy-game Codex + Pictorial Book + GPT-image DNA). Canonical target for: (a) the fine-tune training-set "after" images (`inference/training-set/`), and (b) the deterministic render camera/lighting (`src/web_render/`). Hex values are exact.

**One-line lock:** *a warm illustrated SimCity-2000 Hong Kong seen at dimetric 2:1 / 26.57°, three faces (top·left·right, front never shown), flat cel-style fills with a soft anti-aliased edge on visible rice-paper grain (never crisp pixel art), Jubit teal/pink as engineered hero accents under a 70/20/8/2 budget, soft AO in the canyon creases and flat fills on the faces, day-primary with a day↔night re-light axis — harmonized with the plush folklore characters by shared paper, shared light, shared warmth, and a strict saturation hierarchy where the character is always the brightest thing in frame.*

This welds the city tiles to the Codex character line: both paint from the same swatches, same paper grain, same light, same single soft-graffiti contour rule. Built on `jubuddy-game` `prompt-themes/yok.ts` (palette/texture), `arcane.ts` (environment/lighting), `buddy-core/tokens` (mascot/brand), and the production-asset taste rubric (read-first / chunky-silhouette / quiet-center).

## 0. The locked LoRA contract

| Constant | Value | Where |
|---|---|---|
| **Trigger token** | `<jubit hk soft iso>` | `inference/train.py` `HK_TRIGGER_TOKEN`; generation prompts must emit it verbatim once trained (checklist #11-14) |
| **LoRA model id** | `jubit-hk-soft-iso` | `train.py` `HK_LORA_MODEL_ID`; served via `server.py` `LORA_MODEL_ID` |
| **Modal volume** | `hk-tiles-lora-vol` | LoRA saved to `/data/loras/jubit-hk-soft-iso/`; `server.py` loads from the same volume (checklist #6) |
| **Base model** | `Qwen/Qwen-Image-Edit` | unchanged from upstream |

**LOCKED 2026-06-13.** The token is a one-line contract the LoRA + every generation prompt must agree on — changing it means retraining. `inference/train.py` is the fine-tune entrypoint (was missing); it trains the 40-pair set (§5) to respond to this token and saves to the volume `server.py` reads.

## 1. Palette — 70/20/8/2 budget

**Base (70%)** — warm sun-bleached HK (SC2K warmth, no SC2K brown ground):
| Role | Hex |
|---|---|
| Rice-paper substrate (whole tile) | `#F6F1E8` |
| Warm off-white highlight | `#EFE7D8` |
| Concrete light / mid / shadow | `#C9C2B6` / `#A89F90` / `#8A8378` |
| Ink (soft contour + deepest creases) | `#1F1A17` |

**Structure (20%)** — copper/cream/matte-gold built form: Piltover cream `#F0E2C9`, copper `#C8A36A`, matte antique gold `#C7A25B` (divider/highlight only — never chrome/gloss).

**Accent (8%)** — Jubit brand, the fingerprint the LoRA learns to *inject* (~5–10% of pixels, placed not fielded): teal `#14B8A6`, pink `#EC4899`.

**Punctuation (2%)** — max 1–2/tile: cinnabar `#E63946` (tram/lantern/one sign), jade `#7C9C8E` (Star Ferry/piers).

**Sky/water:** day sky warm wash `#EFE7D8`→`#E3D6BE` (25–40% negative space, no hard gradient); harbour water jade-grey `#A8B8A3` + ink ripples `#1F1A17` @12%, gold reflection `#C7A25B` only at the waterline.

**HK neon (reserve):** day = dormant desaturated sign shapes (−60% sat); night = ignited — hot pink-orange `#FF5E7A`, electric yellow `#FFE600`, sky-cyan `#00E5FF`, magenta `#FF0080`, shimmer green `#3FFF7A` (rare). Night is a **re-light of the same tile**, never a new composition.

## 2. Texture / edge — the soft-stylised lock

| Quality | DO | BANNED |
|---|---|---|
| Edge | soft anti-aliased lip (grid-sliceable but not jaggy) | crisp 1px pixel, dither, "pixel sprite" |
| Outline | ONE soft-graffiti ink `#1F1A17` contour per major form; rest clean cel-flats | heavy outline on every shape; zero-outline vector |
| Faces | flat cel fills, gentle internal gradient only | photoreal gradient, gloss, chrome |
| Substrate | rice-paper grain visible across whole tile, subtle | clean digital flat; competing paper noise |
| Metal | matte antique gold, brushed | chrome/mirror |
| Shadow | soft, low-contrast | heavy drop/cast shadows |
| Colors | ~24–40 working (SC2K discipline, soft execution) | unbounded photographic |

Surface verdict: **"flat illustration with a soft brush, painted on rice paper"** — Arcane's painted-texture-over-2.5D through Yok's flat low-contrast discipline.

## 3. Lighting — `src/web_render` (applied)

**Day (primary) — current defaults in `main.js`:**
- DirectionalLight: intensity **1.9**, color **`#FFEAC4`** (warm key), upper-left (matches camera azimuth)
- HemisphereLight: intensity **1.35**, sky **`#F0E2C9`**, ground **`#A89F90`**
- *Follow-up*: soft **ambient occlusion** (0.55–0.7, small radius) in creases/canyon-gaps only — needs an EffectComposer SAO/SSAO pass; deferred to keep the deterministic bake simple. Governing rule: **soft in the gaps, flat on the faces.**

**Night/neon (controllable 2nd axis, not yet wired):** key 0.6 cool `#4A5568`; ambient 0.5 `#2A2F3A`/`#1F2937`; emissive layer ignites Jubit teal/pink + HK neon; AO ~0.8. Same geometry + camera — a re-light only.

## 4. Camera — SC2000 dimetric (applied)

**elevation −26.565° (arctan 0.5, dimetric 2:1), azimuth −15° (constant for tileability), orthographic.** Chosen by visual A/B on dense Mong Kok AND independently by this workflow. Beats true-iso 35.264° for HK because the lower angle shows more tower **face** (where HK identity lives — windows/balconies/AC/light-bleed), occludes less in dense clusters, locks the SC2K nostalgia signal, and gives clean 2:1 grid-slicing. (Spec's ideal azimuth is 45° for exactly-3-faces; we use −15° matching the upstream renderer's convention — revisit if the 3-face read needs it.) **Same angle on every training image — mixed angles poison the LoRA.**

## 5. The 40-pair training rubric (grades every "after" image)

1. **Projection** — dimetric 2:1, identical angle every image, 3 faces, front never shown.
2. **Base palette (70%)** — warm concrete `#C9C2B6`→`#8A8378`, rice-paper, jade water; no SC2K brown, no photoreal grey-blue; 24–40 colors.
3. **Structure/accent/punctuation (20/8/2)** — copper/cream/gold; Jubit teal+pink hero accents 5–10%; ≤2 punctuation; neon dormant in day. Budget is graded.
4. **Edge/texture** — soft AA lip + one soft-graffiti contour; flat cel fills; rice-paper grain; matte. Not pixel, not clean-3D.
5. **Lighting** — fixed upper-left warm key, 3-tone faces, soft AO in creases. Matches character cel-shadow logic.
6. **Density legibility** — tower-face emphasis, varied silhouettes per cluster (no two adjacent identical), dark canyon gaps, one focal motif. Parse per-building @100%, per-cluster @25%.
7. **Day↔night axis** — day-primary; night = same geometry re-lit, neon ignited.

**Harmonization gate (vs the character line):** shared paper grain; shared single soft-graffiti accent contour; shared palette family per scene; same cel-shade + light direction + warmth; gold reserved for the same role; **strict saturation hierarchy — the placed character is ALWAYS the most saturated thing in frame.**

**40-image composition:** all six tile families × {day, night, a few seam/edge}, deliberate silhouette spread. Text-free, logo-free, original stylized HK forms, grid-sliceable.

## 6. HK stage motifs → per-tile treatment

Each tile = one dominant read; all obey 70/20/8/2 + 25–40% negative space + rice-paper grain + single soft-graffiti contour; must read at 64px.

| Family | Focal | Treatment |
|---|---|---|
| **Harbour** | water plane + one pier | ivory water + ink ripples; junk/skyline as distant edge motif; gold reflection at waterline only; big negative space |
| **Neon canyon** | the value-contrast canyon | deep dark gaps + bright lit upper faces; neon = single soft-graffiti glow line (teal/pink), NOT a flood; depth via value; day = dormant |
| **Skybridge** | calm horizontal deck | chunky read-first silhouette; copper railings; deck kept to canvas edges |
| **Tram/ferry** | the single charming vehicle | soft plush vehicle-keepsake; ding-ding cinnabar `#E63946`, Star Ferry jade `#7C9C8E`; strong 3/4 silhouette + wake/track sweep |
| **Island pier** | stilts + gangway + lantern string | wood/earth textures (tea-brown `#8D6B4D`, kraft grain); paper-lantern string as warm punctuation |
| **Transit concourse** | repeating column/turnstile rhythm | metal vocabulary softened to designer-toy matte; quiet center, readable lane |

## Deferred follow-ups
- AO pass (EffectComposer SAO/SSAO) for the in-crease shadow.
- Night/neon emissive axis in the renderer.
- 45° azimuth experiment (exactly-3-faces) vs the current −15°.
