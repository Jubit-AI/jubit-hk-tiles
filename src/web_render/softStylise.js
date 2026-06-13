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
    uPixelSize: { value: 4.0 },     // mosaic block in screen px (pixel-art read)
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

    // The 15-colour Yok palette (aesthetic-spec §1). Indices 12-14 are the
    // high-chroma accents (teal/pink/cinnabar) — chroma-gated below so the
    // concrete city never mis-snaps to them.
    vec3 yok(int i) {
      if (i==0)  return vec3(0.965,0.945,0.910); // rice-paper  F6F1E8
      if (i==1)  return vec3(0.937,0.906,0.847); // off-white   EFE7D8
      if (i==2)  return vec3(0.788,0.761,0.714); // concrete lt C9C2B6
      if (i==3)  return vec3(0.659,0.624,0.565); // concrete md A89F90
      if (i==4)  return vec3(0.541,0.514,0.471); // concrete sh 8A8378
      if (i==5)  return vec3(0.122,0.102,0.090); // ink         1F1A17
      if (i==6)  return vec3(0.941,0.886,0.788); // cream       F0E2C9
      if (i==7)  return vec3(0.784,0.639,0.416); // copper      C8A36A
      if (i==8)  return vec3(0.780,0.635,0.357); // antique gold C7A25B
      if (i==9)  return vec3(0.890,0.839,0.745); // sky         E3D6BE
      if (i==10) return vec3(0.659,0.722,0.639); // water jade  A8B8A3
      if (i==11) return vec3(0.486,0.612,0.557); // jade        7C9C8E
      if (i==12) return vec3(0.078,0.722,0.651); // JUBIT TEAL  14B8A6 (accent)
      if (i==13) return vec3(0.925,0.282,0.600); // JUBIT PINK  EC4899 (accent)
      return            vec3(0.902,0.224,0.275); // cinnabar    E63946 (accent)
    }

    // Snap to nearest Yok colour. Accents (12-14) get a penalty scaled by how
    // GREY the source is, so only genuinely-colourful pixels reach teal/pink.
    vec3 snapYok(vec3 c) {
      float srcCh = chroma(c);
      float best = 1e9; vec3 bestc = c;
      for (int i = 0; i < 15; i++) {
        vec3 p = yok(i);
        float d = distance(c, p);
        if (i >= 12) d += (1.0 - srcCh) * 0.6; // chroma-gate the brand accents
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
      // Floor 0.33 keeps shadow faces as deep concrete (not black) while giving
      // the massing more tonal punch than a 0.40 floor (which washed pale).
      float bands = uCelBands;
      float banded = floor(lum * bands + 0.5) / bands;
      float lifted = 0.33 + 0.67 * banded;
      col *= lifted / max(lum, 1e-3);

      // 2. Warm rice-paper grade.
      col *= mix(vec3(1.0), vec3(1.06, 1.01, 0.92), uWarm);

      // 3. Soft contour — tap at the mosaic step so the ink line is pixel-aligned.
      vec2 step = uPixelSize / uResolution;
      float lr = luma(texture2D(tDiffuse, puv + vec2(step.x, 0.0)).rgb);
      float ld = luma(texture2D(tDiffuse, puv + vec2(0.0, step.y)).rgb);
      float edge = clamp((abs(lum - lr) + abs(lum - ld)) * 3.0, 0.0, 1.0);
      col *= 1.0 - 0.24 * edge * uEdge;

      // 4. Rice-paper grain, per mosaic cell (stable).
      float g = hash(floor(vUv * grid));
      col *= mix(1.0, 0.96 + 0.04 * g, uGrain);

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
