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
    uDesat: { value: 1.0 },         // pull toward the 24-40 colour discipline
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
    uniform float uCelBands, uWarm, uGrain, uEdge, uDesat;
    varying vec2 vUv;

    float luma(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }
    float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

    void main() {
      vec4 src = texture2D(tDiffuse, vUv);
      vec3 col = src.rgb;
      float lum = luma(col);

      // 1. Cel posterize — band luminance into flat faces, but LIFT into a
      // warm-concrete range so shadow faces read as concrete (#8A8378), never
      // pure black (aesthetic-spec §1A base palette: light→mid→shadow grey).
      float bands = uCelBands;
      float banded = floor(lum * bands + 0.5) / bands;   // 0..1 in steps
      float lifted = 0.40 + 0.60 * banded;               // floor at 0.40 — no black
      col *= lifted / max(lum, 1e-3);

      // 2. Warm rice-paper grade (aesthetic-spec §1A/§3 warm key)
      vec3 warm = mix(vec3(1.0), vec3(1.06, 1.01, 0.92), uWarm);
      col *= warm;

      // 3. Soft-graffiti contour — gently darken where luminance steps (one
      // soft ink line, not heavy outline). Reduced from 0.4 → 0.18 so it reads
      // as a contour hint, not noir.
      vec2 px = 1.0 / uResolution;
      float lr = luma(texture2D(tDiffuse, vUv + vec2(px.x, 0.0)).rgb);
      float ld = luma(texture2D(tDiffuse, vUv + vec2(0.0, px.y)).rgb);
      float edge = clamp((abs(lum - lr) + abs(lum - ld)) * 3.0, 0.0, 1.0);
      col *= 1.0 - 0.18 * edge * uEdge;

      // 4. Rice-paper grain — subtle multiplicative fibre, screen-keyed (stable)
      float g = hash(floor(vUv * uResolution / 2.0));
      col *= mix(1.0, 0.97 + 0.03 * g, uGrain);

      // 5. Pull toward limited-palette discipline (slight desaturate)
      float l2 = luma(col);
      col = mix(col, mix(vec3(l2), col, 0.88), uDesat);

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
