# NYC → HK retargeting checklist

**Source**: 4-agent exhaustive audit of the repo (2026-06-13), verified against the live tree. This is the roadmap for finishing the conversion of this fork (`cannoneyed/isometric-nyc` → Hong Kong). Pair with `docs/HK-ADAPTATION-PLAN.md` (per-week status).

## State of play

The **render-half is done** (Stage-1: 20 Central + 12 hero-location tiles from live HK data). Everything *downstream* of the render is still NYC: the AI restyle (`inference/`), the generation orchestration (`src/isometric_nyc/`), the DZI viewer (`src/app/`). Good news from the audit: most NYC coupling is cosmetic; the dangerous coupling is small and concentrated; the genuinely-dead NYC code (PostGIS path) already fails to import, so deleting it is free.

**The single biggest landmine**: the `<isometric nyc pixel art>` LoRA **trigger token** appears in ~13 files. It's the literal phrase the upstream LoRA was fine-tuned on — *not* a free rename. It must change in lockstep with training the HK LoRA, or restyle output silently degrades.

## 1. MUST-FIX (functional — pipeline can't run end-to-end without these)

Dependency chain: **train HK LoRA → serve it → point generation at it → render+restyle → export DZI → serve viewer.**

### A. Fine-tune side (`inference/`) — gates everything
| # | Change | Where | Verdict |
|---|---|---|---|
| 1 | Author the 40 input→target pairs + `manifest.json` (inputs = HK Stage-1 renders from `scripts/central_render_bake.py`; targets = hand-authored soft-stylised). `training-set/` currently holds only README. | `inference/training-set/` | **WRITE NET-NEW** |
| 2 | Add a fine-tune entrypoint — there is **no `train.py`** despite the README citing one. Write `inference/train.py` (Modal LoRA) or wire the Oxen path. | `inference/train.py` (missing) | **WRITE NET-NEW** |
| 3 | **Choose the HK trigger token once** (e.g. `<jubit hk soft iso>`) — the contract for §1-C. | decision | **DECIDE** |
| 4–7 | Point `DEFAULT_LORA_MODEL_ID` (`server.py:12`) at the HK adapter; dedupe hardcoded fallback (`server.py:84`); rename Modal volume `isometric-lora-vol` → `hk-tiles-lora-vol` (`server.py:41`); upload adapter + `modal deploy`. | `inference/server.py` + ops | EDIT/DEPLOY |

### B. Dead NYC geo path — DELETE (already non-importable, verified)
| # | Delete | Why |
|---|---|---|
| 8 | `whitebox.py` + `citydb/` | NYC SRID 2908/2263 PostGIS; `whitebox.py:16` imports a broken path; HK is WGS84. Dead. |
| 9 | `satellite.py` + `data/google_maps.py` | Google satellite compositing; HK plan = government mesh only. |
| 10 | `data/nyc_opendata.py` | Socrata NYC footprints; superseded by `hk_lands_dept.py`. |

### C. Generation orchestration (`src/isometric_nyc/`) — gated on §A item 3 (the token)
Do **not** touch until the HK token is chosen + the LoRA is trained on it.
| # | Change | Where |
|---|---|---|
| 11–14 | Swap `<isometric nyc pixel art>` → HK token in `generation/app_config.json:9`, `generate_omni.py` (×3), `generate_tile_nano_banana.py`, `automatic_generation.py:629`, and the `synthetic_data/create_*.py` CSV builders. |
| 15 | **Replace seed coords (Times Square)** — ✅ DONE this PR (`generations/tiny-nyc/generation_config.json` → Central 22.2816,114.1578, iso -35.264). |
| 16 | `bounds.py:29` defaults to a missing `data/nyc_boundary.json` → silent empty FeatureCollection. Provide HK bounds or make the arg required (fail loud). |
| 17 | DELETE `tile_generation/` — legacy prototype, hardcodes upstream author's absolute path; superseded by `generation/`. |

### D. DZI viewer (`src/app/`) — tiles won't load until these (Week 7-10)
| # | Change | Where |
|---|---|---|
| 18 | Repoint R2 bucket `isometric-nyc` → HK | `worker/wrangler.toml` |
| 19 | `ALLOWED_ORIGINS` → `dseek.ai` (currently rejects it — hard dep for embedding) | `worker/src/index.ts:9-14` |
| 20–23 | `R2_TILES_URL`, `DEFAULT_EXPORT_DIR` (`tiny-nyc`→`central`), `base` (`/isometric-nyc/`→`/data/life/` or `/`), `deploy.py` paths | `src/app/src/config.ts`, `vite.config.ts`, `deploy.py` |
| 24 | DZI export must emit `tiles_metadata.json` with `appDefaults` centered on Central (else NYC fallback pixel fires) | export pipeline |

## 2. SHOULD-FIX (correctness/clarity)

- ✅ **#30 AGENTS.md** — retargeted to HK this PR.
- ✅ **#31 pyproject** name/description/keywords → HK this PR.
- **#25 legal attribution** in the viewer about-modal (Lands Dept / DATA.GOV.HK / MIT) — required by `docs/legal/attribution.md`, add during viewer retarget.
- **#26-29** viewer `<h1>`, about link, `<title>`, localStorage key → HK (Week 7-12).
- **#32** `inference/README.md:118` says "convert to isometric pixel art" — contradicts the locked soft-stylised aesthetic (Rule-7); fix during fine-tune.
- **#34-38** R2 names, PMTiles metadata, favicons, `app.py` NYC defaults (Week 7-10).
- **#39 free dead-code deletes** (no live importers, verified): `collect/`, `synthetic_data/verify_coordinates.py`, legacy top-level `generate_tile*.py`, `export_views.py` (imports dead whitebox), `data/database.py`, `geo_data/manhattan/`.

## 3. DEFER (cosmetic/naming — high churn, zero output impact)

- **#40 Rename `src/isometric_nyc/` → `src/isometric_hk/`** — 91 files, 108 import lines, `[project.scripts]`, uv.lock. Atomic + reversible, no interest accrues. **Best at Week 7**, after we stop tracking upstream, as a dedicated rename-only commit (doing it now buries the functional diff + increases upstream merge friction — Rule 3).
- **#41-44** Modal app prefix, `__USE_R2_NYC__` flag name, oxen README boilerplate, `README.upstream.md`/`tasks/`/`references/` (intentional archival — leave alone).

## 4. Highest-leverage next action

**Lock the HK trigger token (#3), then author the 40-pair training set + `manifest.json` (#1) + a `train.py` (#2).** Rationale: the token is a one-line contract 13 files + the LoRA must agree on; the training set is the only fully net-new artifact and it gates the entire Week 3-4 fine-tune, which gates generation (Week 7) and the viewer (Week 7-12). Everything else is config-swap or free deletes — fast and parallelizable once the adapter exists.

## 5. Per-week mapping

| Week | Items |
|---|---|
| Now (parallel) | Dead-code deletes (#8-10, #17, #39); seed fix (#15 ✅); identity (#30 ✅, #31 ✅) |
| Week 3 | #1, #2 (training set + train.py — net-new) |
| Week 3-4 | #3 (token), #4-7 (serve), #11-14 (token swaps in lockstep), #32-33 (inference docs) |
| Week 7 | #40 (package rename), #16 (HK bounds), #38 (app defaults) |
| Week 7-10 | #18-24 (viewer/R2/CORS/export), #34-37 |
| Week 11-12 | #19 (CORS hard dep), #25-29 (branding+attribution), embed at dseek.ai/data/life |
