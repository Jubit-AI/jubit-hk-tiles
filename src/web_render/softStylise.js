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
    uniform float uCelBands, uWarm, uGrain, uEdge, uPixelSize, uPaletteMix;
    varying vec2 vUv;

    float luma(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }
    float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
    float chroma(vec3 c) { return max(max(c.r,c.g),c.b) - min(min(c.r,c.g),c.b); }

    // The locked palette ANCHOR (aesthetic-spec §1). 0-1,4 + the two derived
    // warm-concrete mids (2-3) are the neutral massing ramp; 5 gold is structure;
    // 6-9 are the saturated harbour/cinnabar accents, chroma-gated below so the
    // grey concrete city never mis-snaps to them. (Indices 2-3 are derived warm
    // mids between parchment and ink — not anchor colours — for smooth massing.)
    vec3 yok(int i) {
      if (i==0)  return vec3(0.953,0.906,0.812); // rice paper    F3E7CF
      if (i==1)  return vec3(0.851,0.773,0.612); // parchment     D9C59C
      if (i==2)  return vec3(0.639,0.561,0.380); // concrete mid  ~A38F61 (derived)
      if (i==3)  return vec3(0.369,0.322,0.220); // concrete shdw ~5E5238 (derived)
      if (i==4)  return vec3(0.102,0.102,0.090); // ink           1A1A17
      if (i==5)  return vec3(0.780,0.635,0.357); // antique gold  C7A25B
      if (i==6)  return vec3(0.051,0.239,0.275); // deep harbour  0D3D46 (accent)
      if (i==7)  return vec3(0.122,0.435,0.451); // harbour teal  1F6F73 (accent)
      if (i==8)  return vec3(0.180,0.549,0.490); // tram jade     2E8C7D (accent)
      return            vec3(0.714,0.278,0.204); // cinnabar      B64734 (accent)
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

  const stylise = new ShaderPass(SoftStyliseShader);
  stylise.uniforms.uResolution.value.set(width, height);
  composer.addPass(stylise);

  composer.addPass(new OutputPass());
  return composer;
}
