// Deterministic "Soft-Stylised Dimetric HK" post-process — no AI.
//
// Stage-3 styling done as a shader pass instead of a fine-tuned LoRA (the
// "shaders now, AI later" hybrid). Because HK b3dm is already textured, a
// cel + warm-grade + paper-grain + soft-contour pass gets most of the way to
// docs/design/aesthetic-spec.md without GPU training or per-tile inference.
//
// Enabled via the `style=soft` URL param (main.js). When off, the renderer
// emits the RAW deterministic render — that raw output is the input the
// optional AI restyle (inference/train.py) would later consume, so both paths
// coexist from one renderer.
//
// Reference: aesthetic-spec.md §2 (edge/texture), §3 (lighting), §1 (palette).

import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { Vector2 } from "three";

// The soft-stylise fragment shader. Deterministic (grain keyed off screen
// position, not time) so re-renders are identical — required for tileability.
const SoftStyliseShader = {
  uniforms: {
    tDiffuse: { value: null },
    uResolution: { value: new Vector2(1, 1) },
    uCelBands: { value: 4.0 },      // 3-tone-ish face shading (aesthetic-spec §3)
    uWarm: { value: 1.0 },          // warm-grade strength
    uGrain: { value: 1.0 },         // rice-paper grain strength
    uEdge: { value: 1.0 },          // soft-graffiti contour strength
    // "Yok-Iso HK: soft isometric parchment city" — soft diorama, NOT crunchy
    // retro pixel-art. Default uPixelSize 1.0 = clean native edges (no mosaic).
    // Set >1 only for an optional chunky pixel variant; the shipped look is soft.
    uPixelSize: { value: 1.0 },     // mosaic block in screen px (1 = off / clean)
    uPaletteMix: { value: 0.85 },   // 0=off, 1=full snap to the 15-colour Yok palette
    uNight: { value: 0.0 },         // 0=day, 1=night re-light (ignite neon accents)
    uSeaFill: { value: 0.0 },       // f2 visualisation layer: paint empty/sea the day-water tone
    // Phase B — weather/time scenario (live-render axis, mirrors weather_grade.py):
    // 0=none/day, 1=golden-hour, 3=rain, 4=typhoon (night = uNight above). The
    // deployed DZI variants are produced seamlessly by weather_grade.py (absolute
    // pixel coords); this uniform is the live/single-frame counterpart.
    uScenario: { value: 0.0 },
  },
  vertexShader: /* glsl */ `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse;
    uniform vec2 uResolution;
    uniform float uCelBands, uWarm, uGrain, uEdge, uPixelSize, uPaletteMix, uNight, uSeaFill, uScenario;
    varying vec2 vUv;

    float luma(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }
    float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
    float chroma(vec3 c) { return max(max(c.r,c.g),c.b) - min(min(c.r,c.g),c.b); }

    // The locked palette ANCHOR (aesthetic-spec §1). 0-1,4 + the two derived
    // warm-concrete mids (2-3) are the neutral massing ramp; 5 gold is structure;
    // 6-9 are the saturated harbour/cinnabar accents, chroma-gated below so the
    // grey concrete city never mis-snaps to them. (Indices 2-3 are derived warm
    // mids between parchment and ink — not anchor colours — for smooth massing.)
    // HK Jubuddy Soft Isometric palette (docs/design/game-assets/
    // hk-jubuddy-isometric-palette-swatches.svg). 0-1 paper terrain, 2 soft-stone +
    // 3 charcoal give buildings a NEUTRAL tone distinct from parchment terrain (the
    // wash collapsed everything to parchment before); 5 gold = structure; 6-9 are the
    // chroma-gated accents incl. peak-green for hills/vegetation + harbour teal water.
    vec3 yok(int i) {
      if (i==0)  return vec3(0.953,0.906,0.812); // rice paper      F3E7CF
      if (i==1)  return vec3(0.851,0.773,0.612); // warm parchment  D9C59C
      if (i==2)  return vec3(0.659,0.667,0.627); // soft stone      A8AAA0
      if (i==3)  return vec3(0.196,0.220,0.231); // wet charcoal    32383B
      if (i==4)  return vec3(0.102,0.102,0.090); // matte ink       1A1A17
      if (i==5)  return vec3(0.780,0.635,0.357); // antique gold    C7A25B
      if (i==6)  return vec3(0.051,0.239,0.275); // deep harbour    0D3D46 (accent)
      if (i==7)  return vec3(0.122,0.435,0.451); // harbour teal    1F6F73 (accent)
      if (i==8)  return vec3(0.310,0.478,0.318); // peak green      4F7A51 (accent)
      return            vec3(0.714,0.278,0.204); // lantern cinnabar B64734 (accent)
    }

    // Snap to nearest anchor colour. Accents (6-9: harbour/jade/cinnabar) get a
    // penalty scaled by how GREY the source is, so only genuinely-colourful
    // pixels reach them — the concrete city stays on the neutral ramp + gold.
    vec3 snapYok(vec3 c) {
      float srcCh = chroma(c);
      float best = 1e9; vec3 bestc = c;
      for (int i = 0; i < 10; i++) {
        vec3 p = yok(i);
        float d = distance(c, p);
        if (i >= 6) d += (1.0 - srcCh) * 0.6; // chroma-gate the saturated accents
        if (d < best) { best = d; bestc = p; }
      }
      return bestc;
    }

    void main() {
      // 0. Pixelate — sample on a mosaic grid for the pixel-art read.
      vec2 grid = uResolution / max(uPixelSize, 1.0);
      vec2 puv = (floor(vUv * grid) + 0.5) / grid;
      vec4 src = texture2D(tDiffuse, puv);
      vec3 col = src.rgb;

      // viz (f2 real photo textures): the aerial source is dark + muted — brighten and
      // saturate it into a vibrant cute cartoon base before the cel/outline passes.
      if (uSeaFill > 0.5) {
        col = clamp(pow(clamp(col, 0.0, 1.0), vec3(0.80)) * 1.12, 0.0, 1.0); // gamma-lift + gain
        float l0 = luma(col);
        col = clamp(mix(vec3(l0), col, 1.55), 0.0, 1.0);                     // saturation boost
      }
      float lum = luma(col);

      // 1. Cel posterize, lifted into the warm-concrete range (no black crush).
      // Floor 0.30 keeps shadow faces as deep concrete (not black) while giving
      // the massing more tonal punch than a 0.40 floor (which washed pale).
      float bands = uCelBands;
      float banded = floor(lum * bands + 0.5) / bands;
      float lifted = 0.30 + 0.70 * banded;
      col *= lifted / max(lum, 1e-3);

      // 2. Warm rice-paper grade.
      col *= mix(vec3(1.0), vec3(1.06, 1.01, 0.92), uWarm);

      // 3. Restrained pixel-sharp contour — fixed ~1.5px tap (independent of the
      // mosaic) so a crisp ink outline defines every form in the soft-clean look
      // (the mosaic used to supply this; at uPixelSize 1 it must be explicit).
      vec2 estep = 1.5 / uResolution;
      float lr = luma(texture2D(tDiffuse, puv + vec2(estep.x, 0.0)).rgb);
      float ld = luma(texture2D(tDiffuse, puv + vec2(0.0, estep.y)).rgb);
      float edge = clamp((abs(lum - lr) + abs(lum - ld)) * 4.0, 0.0, 1.0);
      col *= 1.0 - 0.32 * edge * uEdge;

      // 4. Rice-paper grain, on a FIXED ~2px paper cell (decoupled from the
      // mosaic so the parchment texture stays subtle even at uPixelSize 1).
      float g = hash(floor(vUv * uResolution / 2.0));
      col *= mix(1.0, 0.965 + 0.035 * g, uGrain);

      // 5. Snap to the Yok palette (limited-palette = pixel-art + Jubit colours).
      col = mix(col, snapYok(clamp(col, 0.0, 1.0)), uPaletteMix);

      // 5b. f2 sea fill. In the visualisation tileset the sea/harbour carries NO
      // mesh — those pixels fall through to the renderer's clear colour (sky-blue
      // 135,206,235). Detect that exact background from the RAW src and paint it a
      // soft day-harbour tone so the sea reads as water (gated by uSeaFill so the
      // building-only bakes keep their parchment empties). Faint screen-keyed
      // ripple so it isn't a dead-flat fill.
      float bg = 1.0 - smoothstep(0.04, 0.12, distance(src.rgb, vec3(0.529, 0.808, 0.922)));
      float ripple = 0.97 + 0.03 * hash(floor(vUv * uResolution / 3.0));
      vec3 seaCol = vec3(0.30, 0.55, 0.56) * ripple;  // day harbour teal (HK Jubuddy)
      col = mix(col, seaCol, bg * uSeaFill);

      // 6. Day↔night re-light axis (same geometry, never a new composition —
      // aesthetic-spec §1 HK-neon / §3). NIGHT: drop the neutral city into a
      // deep-harbour dusk and IGNITE the chroma accents (teal/cinnabar/gold) as
      // neon. Most of the concrete city is neutral → goes dark; the sparse
      // accent pixels glow — exactly a HK night skyline.
      if (uNight > 0.001) {
        float ch = chroma(col);
        float l = luma(col);
        vec3 deepH = vec3(0.051, 0.239, 0.275);   // 0D3D46 deep harbour
        vec3 dusk  = mix(vec3(0.035, 0.045, 0.055), deepH, clamp(l * 1.25, 0.0, 1.0)) * 0.72;
        // accents ignite: keep hue, push saturation + brightness (neon bloom)
        vec3 neon  = clamp(col * 1.7 + ch * 0.6, 0.0, 1.0);
        // Ignite ONLY saturated, mid-dark pixels (teal/cinnabar/jade signs) — the
        // warm parchment neutrals are chromatic too but BRIGHT, so the luminance
        // factor excludes them so the concrete city dusks instead of glowing.
        float isAccent = smoothstep(0.22, 0.36, ch) * (1.0 - smoothstep(0.48, 0.64, l));
        vec3 nightCol = mix(dusk, neon, isAccent);
        col = mix(col, nightCol, uNight);
      }

      // 7. Weather / time-of-day scenarios (Phase B). Mirrors weather_grade.py so
      // the live render and the baked-image variants read the same look. Streaks
      // key off gl_FragCoord (screen-space) — seamless within a single live frame;
      // for SEAMLESS baked scenario maps use weather_grade.py (absolute coords).
      if (uScenario > 0.5) {
        float wl = luma(col);
        if (uScenario < 1.5) {                       // golden-hour
          vec3 warm = col * vec3(1.14, 1.01, 0.80);
          col = warm * 0.88 + vec3(1.0, 0.78, 0.43) * ((1.0 - wl) * 0.30);
          col = (col - 0.5) * 1.08 + 0.5 + 0.015;
        } else if (uScenario > 2.5 && uScenario < 3.5) {   // rain
          vec3 gray = mix(vec3(wl), col, 0.45);
          col = mix(gray * vec3(0.93, 0.97, 1.05), vec3(0.60, 0.64, 0.70), 0.18);
          float ph = mod(gl_FragCoord.x * 0.5 + gl_FragCoord.y, 7.0) / 7.0;
          col = (col + clamp(1.0 - ph / 0.18, 0.0, 1.0) * 0.06) * 0.96;
        } else if (uScenario > 3.5) {                // typhoon
          vec3 gray = mix(vec3(wl), col, 0.28);
          col = mix(gray * vec3(0.86, 0.92, 0.88), vec3(0.52, 0.56, 0.57), 0.28) * 0.82;
          float ph = mod(gl_FragCoord.x * 0.8 + gl_FragCoord.y, 5.0) / 5.0;
          col = col + clamp(1.0 - ph / 0.30, 0.0, 1.0) * 0.05;
        }
      }

      gl_FragColor = vec4(clamp(col, 0.0, 1.0), src.a);
    }
  `,
};

/**
 * Build an EffectComposer that renders the scene then applies the soft-stylise
 * pass. Call composer.render() instead of renderer.render() in the loop.
 */
export function createSoftStyliseComposer(renderer, scene, camera, width, height) {
  const composer = new EffectComposer(renderer);
  composer.setSize(width, height);
  composer.addPass(new RenderPass(scene, camera));

  // (A three.js SAOPass crease-AO was trialled here but produced radial depth
  // artifacts with the 3d-tiles-renderer's ortho/dynamic scene — reverted. AO
  // stays a future deepening; the cel contour already separates forms.)

  const stylise = new ShaderPass(SoftStyliseShader);
  stylise.uniforms.uResolution.value.set(width, height);
  composer.addPass(stylise);

  composer.addPass(new OutputPass());
  return composer;
}
