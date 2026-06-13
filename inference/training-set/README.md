# Fine-tune training set — soft-stylised isometric (Jubit aesthetic)

**Purpose**: the ~40 input→target image pairs that fine-tune Qwen/Image-Edit to restyle deterministic HK tile renders into the Jubit house aesthetic. The plan calls this **"the design anchor; must be authored carefully and reviewed before the run."** This README is its spec; the pairs get authored against it in Week 3.

**Aesthetic — LOCKED**: **soft stylised isometric** (not crisp pixel art). Decision recorded in the plan's FINAL research update #3. One-way door — once the 40 pairs enforce this look, retraining to crisp pixel means re-authoring the set.

> **📐 CANONICAL aesthetic + grading rubric → [`docs/design/aesthetic-spec.md`](../../docs/design/aesthetic-spec.md)** ("Soft-Stylised Dimetric HK"). That spec — synthesized from the jubuddy-game Codex + Pictorial Book + GPT-image DNA — is authoritative: exact palette hexes (70/20/8/2 budget, Jubit teal/pink accents), the soft-stylised edge/texture lock, the dimetric 26.565° camera, the tuned warm lighting, the 7-attribute grading rubric every "after" image scores on, and the per-motif treatments (harbour / neon canyon / skybridge / tram-ferry / island pier / transit concourse). The buckets + workflow below remain valid; grade against the spec.

## Why soft-stylised (the locked rationale)

- **Harmonizes with existing Jubit anime/kawaii character sprites** — the game and dseek surfaces show these tiles *behind/around* hand-drawn anime characters. A painterly soft-iso ground reads as one world; hard pixel-art would read as two games stapled together.
- **Consistency is achievable** — AI restyle output is ~50/50 consistent even after fine-tune; soft-stylised is forgiving of that variance, crisp pixel punishes it (visible palette/edge breaks).
- **It's what isometric-nyc actually is** — the upstream output is a stylised downscaled render, not strict pixel art. We're matching a proven-achievable target, not fighting for a stricter one.

## Target aesthetic — the rubric every "after" image must hit

| Attribute | Target |
|---|---|
| Edges | Soft, painterly anti-aliased — NOT hard 1px pixel edges |
| Palette | Limited but not locked-indexed; warm earthy base + Jubit accents (teal `#…`, pink `#…` — pull exact from jubit design tokens) used sparingly on focal elements |
| Lighting | Flat ambient + a single soft directional key (matches the orthographic bake's lighting) |
| Detail level | Readable at ~256px tile size; legible silhouette; no photoreal micro-texture |
| Signage/trademark | Abstracted to colour blocks — never legible brand text (IFC/ICC/BoC/MTR) |
| Water | Stylised flat fill with a subtle pattern (NOT noisy/photoreal — the upstream water-mask problem) |
| Vegetation | Simplified canopy masses, not individual photoreal leaves |

## Pair structure

40 pairs, each: `pairNN_input.png` (deterministic Stage-1 orthographic render) + `pairNN_target.png` (hand-authored soft-stylised restyle of that exact render). Naming:

```
inference/training-set/
  pairs/
    pair01_input.png   pair01_target.png
    pair02_input.png   pair02_target.png
    ...
    pair40_input.png   pair40_target.png
  manifest.json        # see schema below
  README.md            # this file
```

## Coverage — what the 40 pairs must span

The set must teach the model HK's hard cases, weighted to where the bake struggles:

| Bucket | Count | Why |
|---|---|---|
| Dense urban towers (Central/TST) | 10 | The core look; verticality occlusion cases |
| Mid-rise / tong lau / mixed | 8 | The most common HK texture; tests consistency |
| Water (harbour edge, open water) | 8 | Biggest upstream failure mode — over-weight it |
| Vegetation / hillside / country park | 6 | HK's ~40% green cover; second-biggest failure mode |
| Infrastructure (bridges, flyovers, footbridges) | 4 | Distinctive HK silhouettes |
| Coastline / islands / stilt houses | 4 | Identity cases for the curated backdrops (Output B/F) |

## manifest.json schema

```json
{
  "aesthetic": "soft-stylised-isometric",
  "version": "1.0",
  "pairs": [
    {
      "id": "pair01",
      "input": "pairs/pair01_input.png",
      "target": "pairs/pair01_target.png",
      "bucket": "dense-urban",
      "district": "central",
      "notes": "two 200m+ towers + a 6-storey tong lau on a slope — verticality case"
    }
  ]
}
```

## Authoring workflow (Week 3)

1. Run the Stage-1 deterministic render (once the render-half lands) on ~40 hand-picked framings spanning the buckets above → the `*_input.png` set.
2. An artist restyles each into soft-stylised Jubit aesthetic per the rubric → the `*_target.png` set.
3. Fill `manifest.json`.
4. **Review gate before fine-tune**: do the 40 targets look like one coherent aesthetic that sits comfortably behind Jubit anime characters? If not, re-author — do NOT proceed to the ~$12 Modal fine-tune on an incoherent set.
5. Fine-tune Qwen/Image-Edit on Modal (upstream recipe in `inference/`), then generate the 100-tile validation sample (plan Week 4 gate).

## Open items

- **Exact Jubit accent hex values**: pull from the jubit design tokens (`design-system/tokens/colors.json` in jubit-ai-universe — teal `#14B8A6`, pink `#EC4899` per project convention) and fill the palette row above before authoring.
- The `*_input.png` set is blocked on the render-half (Week 2 render). The spec + buckets + manifest schema are authorable now (this file); the actual images follow the render.
