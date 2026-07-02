// Producer: OSM natural=coastline for HK → RDP-simplified polyline asset for the glow layer.
import fs from 'node:fs';
const BBOX = '22.13,113.82,22.58,114.45';
const Q = `[out:json][timeout:120];way["natural"="coastline"](${BBOX});out geom;`;
const MIRRORS = ['https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter', 'https://overpass.kumi.systems/api/interpreter'];
const HDRS = { 'User-Agent': 'jubit-living-map/1.0 (coastline asset)', Accept: 'application/json' };

function rdp(pts, eps) {
  if (pts.length < 3) return pts;
  let dmax = 0, idx = 0;
  const [ax, ay] = pts[0], [bx, by] = pts[pts.length - 1];
  const dx = bx - ax, dy = by - ay, len2 = dx * dx + dy * dy || 1e-12;
  for (let i = 1; i < pts.length - 1; i++) {
    const [px, py] = pts[i];
    const t = ((px - ax) * dx + (py - ay) * dy) / len2;
    const cx = ax + t * dx, cy = ay + t * dy;
    const d = Math.hypot(px - cx, py - cy);
    if (d > dmax) { dmax = d; idx = i; }
  }
  if (dmax > eps) return rdp(pts.slice(0, idx + 1), eps).slice(0, -1).concat(rdp(pts.slice(idx), eps));
  return [pts[0], pts[pts.length - 1]];
}
function lenM(pts) {
  let m = 0;
  for (let i = 1; i < pts.length; i++) {
    const dlat = (pts[i][0] - pts[i - 1][0]) * 110540;
    const dlon = (pts[i][1] - pts[i - 1][1]) * 111320 * Math.cos(pts[i][0] * Math.PI / 180);
    m += Math.hypot(dlat, dlon);
  }
  return m;
}

const RAW_CACHE = '/tmp/coastline_raw.json';
let data = null;
if (fs.existsSync(RAW_CACHE)) {
  data = JSON.parse(fs.readFileSync(RAW_CACHE, 'utf8'));
  console.error('using cached raw Overpass response');
}
if (!data) for (const url of MIRRORS) {
  try {
    const r = await fetch(url + '?data=' + encodeURIComponent(Q), { headers: HDRS });
    if (r.ok) { data = await r.json(); console.error('OK', url); break; }
    console.error('mirror', url, r.status);
  } catch (e) { console.error('mirror fail', url, e.message); }
  await new Promise((res) => setTimeout(res, 2500));
}
if (!data) { console.error('ALL MIRRORS FAILED'); process.exit(1); }
if (!fs.existsSync(RAW_CACHE)) fs.writeFileSync(RAW_CACHE, JSON.stringify(data));

const rawWays = (data.elements || []).filter((e) => e.type === 'way' && e.geometry);
const EPS = 0.00007, MIN_LEN = 250; // ~8m: tight enough for HD-district zoom (4px/m)
let rawV = 0, keptV = 0;
const ways = [];
for (const w of rawWays) {
  const pts = w.geometry.map((g) => [+g.lat.toFixed(5), +g.lon.toFixed(5)]);
  rawV += pts.length;
  if (lenM(pts) < MIN_LEN) continue;
  const simp = rdp(pts, EPS);
  if (simp.length < 2) continue;
  keptV += simp.length;
  ways.push(simp);
}
const out = { ways, _meta: { source: 'OSM natural=coastline', bbox: BBOX, epsDeg: EPS, minLenM: MIN_LEN, rawWays: rawWays.length, keptWays: ways.length, rawVerts: rawV, keptVerts: keptV } };
fs.writeFileSync('/tmp/coastline.json', JSON.stringify(out));
console.log(JSON.stringify(out._meta, null, 2));
console.log('bytes:', fs.statSync('/tmp/coastline.json').size);
