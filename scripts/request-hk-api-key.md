# Action: request the HK 3D map API key

This is a blocker for **Week 2** (Central pilot render). The HK Lands Department issues API keys on email request, free of charge.

## Send this email

**To**: `3dmap@landsd.gov.hk`
**CC**: (your address — they want a single reply target)
**Subject**: API key request — 3D Visualisation Map / 3D Spatial Data API (Cesium 3D Tiles)

```
Dear Lands Department team,

I'd like to request an API key for the 3D Visualisation Map API and 3D Spatial
Data API, hosted at data.map.gov.hk.

Intended use: building an isometric pixel-art map of Hong Kong from the
territory-wide 3D dataset. The pipeline renders the official Cesium 3D Tiles
output through an orthographic camera to produce a stylized pixel-art view,
intended to be hosted at a public website (dseek.ai/data/life) and reused as
backdrops in an independent video game. Game design is listed as a sanctioned
application of the dataset in the official materials.

Endpoints I expect to use:
- https://data.map.gov.hk/api/3d-data/3dtiles/f2/tileset.json
- https://data.map.gov.hk/api/3d-data/3dsd/WGS84/building/tileset.json
- https://data.map.gov.hk/api/3d-data/3dsd/WGS84/infrastructure/tileset.json

I'll comply with the DATA.GOV.HK terms in full: clear attribution to the
Government of HK SAR / Lands Department / DATA.GOV.HK on every consumer
surface, no resale of the data, no third-party imagery composited in.

Could you please issue an API key and indicate any documentation I should
review for fair-use limits beyond the published 5 GB/sec bandwidth and 100
concurrent users?

Thank you,
<your name>
<your role / organisation if applicable>
```

## After the key arrives

1. Store it in your shell env, not the repo: `export HK_LANDSD_API_KEY=...` in `~/.zshrc` or `~/.bashrc`.
2. Also add to `.env.local` at the repo root (which is `.gitignore`d) for local Python scripts. Pattern:
   ```
   HK_LANDSD_API_KEY=...
   ```
3. The stubbed adapter at `src/isometric_nyc/data/hk_lands_dept.py` reads from `HK_LANDSD_API_KEY`. Once set, the Week 2 Central pilot can run.

## Estimated wait

Per third-party reports, the HK gov turnaround on these requests has been 1–5 business days. If urgent, the CSDI portal (`portal.csdi.gov.hk`) offers some downloads without the API key — useful for an offline pilot if the API key takes longer than expected.

## Privacy / opsec

- Do not commit the API key.
- Do not paste it into commit messages, PR descriptions, or chat logs.
- If accidentally exposed (e.g. in a public PR), notify `3dmap@landsd.gov.hk` for rotation. The key is per-requester, so rotation is fast.
