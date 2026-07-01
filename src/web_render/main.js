import {
  TilesRenderer,
  WGS84_ELLIPSOID,
  GlobeControls,
  CameraTransitionManager,
  CAMERA_FRAME,
} from "3d-tiles-renderer";
import {
  GLTFExtensionsPlugin,
  TileCompressionPlugin,
} from "3d-tiles-renderer/plugins";
import {
  Matrix4,
  Scene,
  WebGLRenderer,
  PerspectiveCamera,
  OrthographicCamera,
  MathUtils,
  HemisphereLight,
  DirectionalLight,
} from "three";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { KTX2Loader } from "three/addons/loaders/KTX2Loader.js";
import { createSoftStyliseComposer } from "./softStylise.js";

import view from "../view.json";

// --- CONFIGURATION ---
// HK Lands Department 3D Spatial Data API key (open-data regime).
// Vite injects only VITE_-prefixed vars into the browser bundle.
const API_KEY = import.meta.env.VITE_HK_LANDSD_API_KEY;
console.log("HK API Key loaded:", API_KEY ? "Yes" : "No");

const urlParams = new URLSearchParams(window.location.search);
const EXPORT_MODE = urlParams.get("export") === "true";
// style=soft → deterministic soft-stylise post-process (no AI). Default off =
// RAW render (the input the optional AI restyle would consume). See softStylise.js.
const STYLE_MODE = urlParams.get("style") === "soft";
// Optional soft-stylise tuning (only used when STYLE_MODE). pixel = mosaic block
// in screen px (bigger = chunkier pixel-art read); palette = 0..1 snap strength
// to the 15-colour Yok palette. Null = use the shader defaults (4 / 0.85).
const PIXEL_SIZE = urlParams.has("pixel") ? parseFloat(urlParams.get("pixel")) : null;
const PALETTE_MIX = urlParams.has("palette") ? parseFloat(urlParams.get("palette")) : null;
// night=true → day↔night re-light (ignite neon accents on the same geometry).
const NIGHT = urlParams.get("night") === "true";
// vector=true → clean STYLIZED-VECTOR-ILLUSTRATION preset: flatter cel fills,
// hard palette flats, bold clean outline, no paper grain (graphic map look).
const VECTOR = urlParams.get("vector") === "true";
// scenario=golden|rain|typhoon → live weather/time axis (Phase B), the shader
// counterpart of weather_grade.py + the viewer's scenario switcher. night=true
// (above) remains the day↔night axis. Only applies under style=soft. The deployed
// DZI variants are baked seamlessly by weather_grade.py; this is the live path.
const SCENARIO = urlParams.get("scenario") || "";
const SCENARIO_ID = { golden: 1, rain: 3, typhoon: 4 }[SCENARIO] || 0;
// transparent=true → no sky fill; the alpha channel is preserved end-to-end so a
// tightly-framed landmark bakes as a game-ready PROP SPRITE (the jubuddy-HK
// identity layer). Screenshot with omit_background to keep the transparency.
const TRANSPARENT = urlParams.get("transparent") === "true";
// layer=building|infrastructure|visualisation → which HK Lands Dept 3D tileset.
// building (default) = 3dsd buildings only; visualisation = the f2 map that bundles
// terrain + waterbody + vegetation + infrastructure + buildings. See hk_lands_dept.py.
const LAYER = urlParams.get("layer") || "building";
const TILESET_PATHS = {
  building: "3dsd/WGS84/building",
  infrastructure: "3dsd/WGS84/infrastructure",
  visualisation: "3dtiles/f2",
};

// SEAMLESS MAP tiling (Output A). When tile_cols/tile_rows are present, the
// ortho camera covers the FULL map (lat/lon = map centre, view_height = the
// whole grid's view-plane height) and each tile is a setViewOffset window into
// that ONE shared projection — so tiles stitch perfectly and a tower straddling
// a boundary renders its top in the tile above + base below, aligned (no blend,
// no spacing calibration). Tile (tile_col,tile_row) is rendered; 0,0 = top-left.
const TILE_COLS = parseInt(urlParams.get("tile_cols")) || 1;
const TILE_ROWS = parseInt(urlParams.get("tile_rows")) || 1;
const TILE_COL = parseInt(urlParams.get("tile_col")) || 0;
const TILE_ROW = parseInt(urlParams.get("tile_row")) || 0;
const MAP_TILING = TILE_COLS > 1 || TILE_ROWS > 1;

// Configuration with URL param overrides
const CANVAS_WIDTH = parseInt(urlParams.get("width")) || view.width_px;
const CANVAS_HEIGHT = parseInt(urlParams.get("height")) || view.height_px;
const LAT = parseFloat(urlParams.get("lat")) || view.lat;
const LON = parseFloat(urlParams.get("lon")) || view.lon;
const CAMERA_AZIMUTH =
  parseFloat(urlParams.get("azimuth")) || view.camera_azimuth_degrees;
const CAMERA_ELEVATION =
  parseFloat(urlParams.get("elevation")) || view.camera_elevation_degrees;
const VIEW_HEIGHT_METERS =
  parseFloat(urlParams.get("view_height")) || view.view_height_meters || 200;

let scene, renderer, controls, tiles, transition;
let composer = null; // soft-stylise post-process chain when STYLE_MODE
let isOrthographic = true; // Start in orthographic (isometric) mode

// Debounced camera info logging
let logTimeout = null;
let lastCameraState = { az: 0, el: 0, height: 0, zoom: 1 };

// Tile loading tracking
let tilesStableStartTime = 0;
window.TILES_LOADED = false;
let cameraInitialized = false;

// Also, whitebox.py calculates positions relative to Z=0.
// However, buildings have height, and we probably want to look at the ground (Z=0).
// But wait! whitebox.py detected ground elevation:
// "Detected ground elevation: 10.00m" (typically around 10-15m for NYC)
// And then it textures the ground at calculated_ground_z.
// But the camera focal point is (0,0,0).
// The geometry in whitebox.py is shifted:
// x, y = pts[:, 0] - center_x, pts[:, 1] - center_y
// But Z values are preserved from the DB.
// So if the DB has ground at Z=10, the camera looking at Z=0 is looking 10m BELOW ground.

// In 3D Tiles (Google), the tiles are positioned on the WGS84 ellipsoid.
// When we ask for a frame at height=0, we get the ellipsoid surface.
// NYC ground level is indeed around 10-30m above the ellipsoid in some places,
// but Google 3D tiles usually match the ellipsoid roughly or have their own geoid.

// If whitebox.py is rendering geometry where Z=0 is "arbitrary zero", but actual geometry is at Z=10,
// and camera looks at Z=0, then the view is centered 10m below the buildings.

// In the web view, we are centering on the ellipsoid surface (height=0).
// If the visible Google 3D tiles are at height=10, then we are also looking 10m below the buildings.

// It seems they match in intent (looking at Z=0/Ellipsoid), but we might need to tweak the
// center point height to match exactly if there is a shift.

// For now, let's keep it at 0. If there is a vertical offset, we can adjust here.
// Example: Look at 15m elevation to center on "street level" if streets are elevated.

// Whitebox.py finds median ground Z around 10-15m for MSG.
// It then constructs the scene around that.
// Since its camera looks at (0,0,0), it is looking at Z=0 relative to the *PostGIS* coordinates.
// If PostGIS coordinates have ground at Z=10, then the camera is looking 10m below ground.
// We are doing the same here (looking at Z=0 on ellipsoid).

// HOWEVER, if we want them to align PIXEL-PERFECTLY:
// We need to account for any difference in how the "center" is defined.
// Whitebox centers on the *projected* coordinates of (LAT, LON).
// 3D Tiles Renderer centers on the *cartesian* coordinates of (LAT, LON, 0).

// There might be a small shift due to projection.
// But more likely, it's the Z-height of the "center of rotation".
// Let's try bumping the target height to match the ground elevation ~10m.
// Or, if the whitebox image is "higher" (building lower in frame), we need to look *lower* (smaller Z).

// Observation: The web view shows the building slightly "higher" in the frame than whitebox.
// This means the camera is looking *below* the point that whitebox is looking at.
// Or whitebox is looking *above* the point we are looking at.

// Whitebox look-at: (0,0,0). Ground is at Z~10. So it looks 10m below ground.
// Web look-at: Ellipsoid surface (Z=0).

// Let's try adjusting the target height to see if it aligns better.
// If we look at 15m, the camera moves up, and the scene moves DOWN in the frame.
// If the web view is too high, we need to look HIGHER (larger Z).
// HK ground sits ~+2 to +5m above the WGS84 ellipsoid in Central (Hong Kong
// Principal Datum). NYC's -31.3 geoid would sink the look-at ~36m below HK
// ground and frame sky. Start at +5, tune against output per docs/qa/verticality.
const TARGET_HEIGHT = 5;

init();
animate();

function init() {
  // Use fixed canvas dimensions for consistent rendering
  const aspect = CANVAS_WIDTH / CANVAS_HEIGHT;
  console.log(
    `🖥️ Fixed canvas: ${CANVAS_WIDTH}x${CANVAS_HEIGHT}, aspect: ${aspect.toFixed(
      3
    )}`
  );

  // Renderer - fixed size, no devicePixelRatio scaling for consistency
  renderer = new WebGLRenderer({ antialias: true, alpha: TRANSPARENT });
  if (TRANSPARENT) {
    renderer.setClearColor(0x000000, 0); // transparent → prop-sprite alpha
  } else if (LAYER === "visualisation") {
    // f2 sea / open areas carry no mesh → fall through to the clear colour. Use a
    // harbour tone (not sky-blue) so the empty sea blends with f2's real water
    // texture instead of leaving a cyan seam.
    renderer.setClearColor(0x35655c); // harbour teal-green (≈ f2 water)
  } else {
    renderer.setClearColor(0x87ceeb); // Sky blue
  }
  renderer.setPixelRatio(1); // Fixed 1:1 pixel ratio for consistent rendering
  renderer.setSize(CANVAS_WIDTH, CANVAS_HEIGHT);
  document.body.appendChild(renderer.domElement);

  // Scene
  scene = new Scene();

  // Lighting — HK b3dm tiles use PBR (MeshStandard) materials that render
  // BLACK without lights. Tuned per the "Soft-Stylised Dimetric HK" aesthetic
  // spec (docs/design/aesthetic-spec.md §3A): WARM key + lifted-but-not-flooded
  // ambient so HK's canyon creases stay dark ("soft in the gaps, flat on the
  // faces") and tower tops don't blow out. Earlier flat-bright/cool values
  // (hemi 2.0 + dir 2.5 white) washed out the density read.
  //   key:     warm #FFEAC4, intensity 1.9, upper-left (matches camera azimuth)
  //   ambient: warm sky #F0E2C9 / concrete ground #A89F90, intensity 1.35
  // (Soft AO in the creases is a documented follow-up — needs an EffectComposer
  //  SAO/SSAO pass; deferred to keep the deterministic bake simple.)
  const hemi = new HemisphereLight(0xf0e2c9, 0xa89f90, 1.35);
  scene.add(hemi);
  const sun = new DirectionalLight(0xffeac4, 1.9);
  sun.position.set(-1, 2, 1); // upper-left key
  scene.add(sun);

  // Camera transition manager (handles both perspective and orthographic)
  transition = new CameraTransitionManager(
    new PerspectiveCamera(60, aspect, 1, 160000000),
    new OrthographicCamera(-1, 1, 1, -1, 1, 160000000)
  );
  transition.autoSync = false;
  transition.orthographicPositionalZoom = false;

  // Handle camera changes
  transition.addEventListener("camera-change", ({ camera, prevCamera }) => {
    tiles.deleteCamera(prevCamera);
    tiles.setCamera(camera);
    controls.setCamera(camera);
  });

  // Initialize tiles — HK Lands Dept textured b3dm tileset (open-data 3dsd API).
  // No auth plugin: HK passes the key as a query param (browser-friendly, no
  // preflight). Endpoint mirrors hk_lands_dept.py / central_pilot_fetch.py.
  const HK_TILESET_URL =
    `https://data.map.gov.hk/api/3d-data/${TILESET_PATHS[LAYER] || TILESET_PATHS.building}/tileset.json?key=${API_KEY}`;
  tiles = new TilesRenderer(HK_TILESET_URL);
  tiles.registerPlugin(new TileCompressionPlugin());
  // HK b3dm textures are KTX2/BasisU-compressed — without a KTX2 loader every
  // tile throws "setKTX2Loader must be called before loading KTX2 textures" and
  // renders untextured/empty. detectSupport(renderer) picks the GPU's format.
  //
  // The basis transcoder is served LOCALLY from public/basis/ (copied from the
  // installed three@0.181.2) rather than a remote unpkg CDN. A bake renders many
  // tiles, each in a fresh browser context that re-fetches the transcoder; per-
  // context CDN round-trips are slow and a CDN hiccup can reject the transcode.
  // Local hosting = no network dependency, faster, offline, deterministic.
  // (Vite root is src/web_render; public/ serves at "/".)
  const ktxLoader = new KTX2Loader()
    .setTranscoderPath("/basis/")
    .detectSupport(renderer);
  // Pre-warm the transcoder so the first transcode is deterministic and an init
  // failure surfaces LOUDLY (window.KTX2_INIT_FAILED) instead of silently
  // emitting whiteboxes — the bake gate refuses to save on init failure.
  ktxLoader.init().catch((e) => {
    console.error("KTX2 transcoder failed to init:", e);
    window.KTX2_INIT_FAILED = true;
  });
  // DRACO decoder stays on the CDN path: the HK building tileset is NOT Draco-
  // compressed (b3dm extensionsUsed = ["KHR_texture_basisu"] only), so this
  // loader never actually fetches for these tiles — kept for format-completeness.
  const gltfOpts = {
    dracoLoader: new DRACOLoader().setDecoderPath(
      "https://unpkg.com/three@0.181.2/examples/jsm/libs/draco/gltf/"
    ),
  };
  // KTX2/BasisU textures for BOTH layers. f2 (visualisation) textures are also
  // image/ktx2 (its materials are KHR_materials_unlit → flat, lighting-independent)
  // and they carry the REAL water/terrain/vegetation/facade colour — exactly what we
  // want. They transcode async, so the bake gives f2 ample --settle-ms before capture.
  gltfOpts.ktxLoader = ktxLoader;
  // f2 (visualisation) textures are plain image/ktx2 bufferView images WITHOUT the
  // KHR_texture_basisu extension, so three.js GLTFLoader routes them to the DEFAULT
  // image loader (which can't decode ktx2) → "Couldn't load texture blob" and the
  // mesh renders untextured. This GLTFLoader plugin sends any image/ktx2 source to the
  // KTX2 loader so f2's REAL textures (vegetation, water, roads, terrain, facades)
  // actually decode. loadTexture returning a promise overrides the default; returning
  // null falls through, so the building layer's KHR_texture_basisu path is untouched.
  const ktx2MimeFallback = (parser) => ({
    name: "EXT_ktx2_mime_fallback",
    loadTexture(textureIndex) {
      const def = parser.json.textures[textureIndex];
      const src = parser.json.images[def.source];
      if (!src || (def.extensions && def.extensions.KHR_texture_basisu)) return null;
      const isKtx2 = src.mimeType === "image/ktx2" || (src.uri && /\.ktx2($|\?)/i.test(src.uri));
      if (!isKtx2 || !parser.options.ktx2Loader) return null;
      return parser.loadTextureImage(textureIndex, def.source, parser.options.ktx2Loader);
    },
  });
  gltfOpts.plugins = [ktx2MimeFallback];
  tiles.registerPlugin(new GLTFExtensionsPlugin(gltfOpts));

  // Rotate tiles so Z-up becomes Y-up (Three.js convention)
  tiles.group.rotation.x = -Math.PI / 2;
  scene.add(tiles.group);

  // Headless-debug hooks: let the bake/probe inspect texture state from the page.
  window.__tiles = tiles;
  window.__scene = scene;

  // Setup GlobeControls
  controls = new GlobeControls(
    scene,
    transition.camera,
    renderer.domElement,
    null
  );
  controls.enableDamping = true;
  controls.minZoom = 0.1; // Allow zooming out
  controls.maxZoom = 20.0; // Allow zooming in

  // Connect controls to the tiles ellipsoid and position camera
  tiles.addEventListener("load-tile-set", () => {
    controls.setEllipsoid(tiles.ellipsoid, tiles.group);

    // Delay camera positioning to ensure controls/transition are fully initialized
    // This fixes the "zoomed out on first load" issue
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (!cameraInitialized) {
          positionCamera();
          cameraInitialized = true;
        }
      });
    });
  });

  tiles.setCamera(transition.camera);
  tiles.setResolutionFromRenderer(transition.camera, renderer);

  // Handle resize
  window.addEventListener("resize", onWindowResize);

  // Add keyboard controls
  window.addEventListener("keydown", onKeyDown);

  // Soft-stylise post-process chain (deterministic, no AI) when style=soft.
  // Built with the current transition camera; the RenderPass camera is kept in
  // sync each frame in animate() since the perspective/ortho camera can swap.
  if (STYLE_MODE) {
    composer = createSoftStyliseComposer(
      renderer, scene, transition.camera, CANVAS_WIDTH, CANVAS_HEIGHT
    );
    // Find the SoftStyliseShader pass by its uniforms (its index shifts when the
    // optional SAO pass is inserted), then apply optional URL overrides.
    const stylisePass = composer.passes.find(
      (p) => p.uniforms && p.uniforms.uPixelSize
    );
    const styliseUniforms = stylisePass.uniforms;
    if (VECTOR) {
      // stylized-vector-illustration preset (flat graphic map look)
      styliseUniforms.uCelBands.value = 3.0;   // fewer tones → flatter regions
      styliseUniforms.uGrain.value = 0.0;      // clean, no paper grain
      styliseUniforms.uEdge.value = 1.7;       // bold clean vector outline
      styliseUniforms.uPaletteMix.value = 1.0; // hard flat colour flats
    }
    if (PIXEL_SIZE !== null) styliseUniforms.uPixelSize.value = PIXEL_SIZE;
    if (PALETTE_MIX !== null) styliseUniforms.uPaletteMix.value = PALETTE_MIX;
    if (NIGHT) styliseUniforms.uNight.value = 1.0;
    if (SCENARIO_ID) styliseUniforms.uScenario.value = SCENARIO_ID;
    if (LAYER === "visualisation") {
      // f2's open sea carries no mesh → falls through to the clear colour; paint it
      // a soft harbour tone.
      styliseUniforms.uSeaFill.value = 1.0;
      // f2 has no vivid colour of its own (muted/flat) — so FULL-snap it to the HK
      // Jubuddy palette: buildings → soft-stone/charcoal, terrain → parchment, hills
      // → peak-green, sea → harbour teal. The richer palette gives the snap distinct
      // targets so the render stops collapsing to a single parchment tone.
      styliseUniforms.uPaletteMix.value = 0.92;
    }
    console.log(
      `🎨 soft-stylise enabled (pixel=${styliseUniforms.uPixelSize.value}, ` +
      `palette=${styliseUniforms.uPaletteMix.value})`
    );
  }

  // Add UI instructions
  addUI();
}

function positionCamera() {
  const camera = transition.perspectiveCamera;

  // Use getObjectFrame to position camera with azimuth/elevation
  // Azimuth: 0=North, 90=East, 180=South, 270=West
  // For SimCity view from SW looking NE, we want azimuth ~210-225
  WGS84_ELLIPSOID.getObjectFrame(
    LAT * MathUtils.DEG2RAD,
    LON * MathUtils.DEG2RAD,
    TARGET_HEIGHT, // CENTER AT TARGET HEIGHT
    CAMERA_AZIMUTH * MathUtils.DEG2RAD,
    CAMERA_ELEVATION * MathUtils.DEG2RAD,
    0, // roll
    camera.matrixWorld,
    CAMERA_FRAME
  );

  // Move camera back 2000m along its own Z axis (viewing direction)
  // This matches whitebox.py's "dist = 2000" logic

  camera.matrixWorld.multiply(new Matrix4().makeTranslation(0, 0, 2000));

  // Apply tiles group transform
  camera.matrixWorld.premultiply(tiles.group.matrixWorld);
  camera.matrixWorld.decompose(
    camera.position,
    camera.quaternion,
    camera.scale
  );

  // Sync both cameras
  transition.syncCameras();
  controls.adjustCamera(transition.perspectiveCamera);
  controls.adjustCamera(transition.orthographicCamera);

  // Switch to orthographic mode by default
  // IMPORTANT: Do this BEFORE setting frustum, as toggle() may reset camera values
  if (isOrthographic && transition.mode === "perspective") {
    controls.getPivotPoint(transition.fixedPoint);
    transition.toggle();
  }

  // Calculate orthographic frustum to match whitebox.py's CAMERA_ZOOM
  // In VTK, parallel_scale = half the view height in world units
  // whitebox.py uses CAMERA_ZOOM = 100, so view height = 200m
  const ortho = transition.orthographicCamera;
  const aspect = CANVAS_WIDTH / CANVAS_HEIGHT;

  // Match whitebox.py visually
  // view.view_height_meters determines the vertical extent of the view in world units (meters)
  // NOTE: whitebox.py uses parallel_scale = VIEW_HEIGHT_METERS / 2
  // This means the total height of the view is VIEW_HEIGHT_METERS.
  // However, the camera is positioned at a significant height.
  // In whitebox.py, the camera is positioned so the focal point (0,0,0) is in the CENTER of the screen.
  // (0,0,0) corresponds to the lat/lon in view.json.

  // When tiling a seamless map, VIEW_HEIGHT_METERS is the FULL grid's view-plane
  // height and the frustum aspect is the FULL grid (cols×canvas)/(rows×canvas);
  // setViewOffset then crops to this one tile. Otherwise it's a single framed view.
  const frustumHeight = VIEW_HEIGHT_METERS;
  const halfHeight = frustumHeight / 2;
  const fullAspect = MAP_TILING
    ? (TILE_COLS * CANVAS_WIDTH) / (TILE_ROWS * CANVAS_HEIGHT)
    : aspect;
  const halfWidth = halfHeight * fullAspect;

  console.log(`📐 Frustum: height=${frustumHeight}m`);

  // Set frustum with calculated values
  ortho.top = halfHeight;
  ortho.bottom = -halfHeight;
  ortho.left = -halfWidth;
  ortho.right = halfWidth;

  // Reset zoom to 1.0 to ensure strict 1:1 scale with world units
  ortho.zoom = 1.0;
  if (MAP_TILING) {
    // Window into the shared full-map projection — seamless by construction.
    ortho.setViewOffset(
      TILE_COLS * CANVAS_WIDTH, TILE_ROWS * CANVAS_HEIGHT,
      TILE_COL * CANVAS_WIDTH, TILE_ROW * CANVAS_HEIGHT,
      CANVAS_WIDTH, CANVAS_HEIGHT
    );
    console.log(`🧩 setViewOffset tile (${TILE_COL},${TILE_ROW}) of ${TILE_COLS}×${TILE_ROWS}`);
  } else {
    ortho.clearViewOffset();
  }
  ortho.updateProjectionMatrix();

  // Shift the camera to center the target point
  // In 3d-tiles-renderer, the camera looks at the target point.
  // But if we are using getObjectFrame, the camera is positioned relative to the target point.
  // We want the target point to be in the center of the screen.
  // That is already what getObjectFrame does (looks at the origin of the frame).

  console.log(`Camera positioned at target height ${TARGET_HEIGHT}m`);
  console.log(`Azimuth: ${CAMERA_AZIMUTH}°, Elevation: ${CAMERA_ELEVATION}°`);
  console.log(`Mode: ${transition.mode}`);

  // Log camera info
  console.log(
    `📷 Ortho frustum: L=${ortho.left.toFixed(0)} R=${ortho.right.toFixed(
      0
    )} ` +
      `T=${ortho.top.toFixed(0)} B=${ortho.bottom.toFixed(
        0
      )} (aspect=${aspect.toFixed(2)})`
  );
}

function toggleOrthographic() {
  // Get current pivot point for smooth transition
  controls.getPivotPoint(transition.fixedPoint);

  if (!transition.animating) {
    transition.syncCameras();
    controls.adjustCamera(transition.perspectiveCamera);
    controls.adjustCamera(transition.orthographicCamera);
  }

  transition.toggle();
  isOrthographic = transition.mode === "orthographic";

  console.log(
    `Switched to ${
      isOrthographic ? "ORTHOGRAPHIC (isometric)" : "PERSPECTIVE"
    } camera`
  );
}

function onKeyDown(event) {
  if (event.key === "o" || event.key === "O") {
    toggleOrthographic();
  }
}

function addUI() {
  // Hide UI in export mode for clean screenshots
  if (EXPORT_MODE) return;

  const info = document.createElement("div");
  info.style.cssText = `
    position: fixed;
    top: 10px;
    left: 10px;
    background: rgba(0,0,0,0.7);
    color: white;
    padding: 10px 15px;
    font-family: monospace;
    font-size: 14px;
    border-radius: 5px;
    z-index: 1000;
  `;
  info.innerHTML = `
    <strong>Isometric NYC - Times Square</strong><br>
    <br>
    Scroll: Zoom<br>
    Left-drag: Rotate<br>
    Right-drag: Pan<br>
    <strong>O</strong>: Toggle Perspective/Ortho<br>
    <br>
  `;
  document.body.appendChild(info);
}

function onWindowResize() {
  // Canvas is fixed size - don't resize on window changes
  // This ensures consistent rendering regardless of window size
}

// Extract current camera azimuth, elevation, height from its world matrix
function getCameraInfo() {
  if (!tiles || !tiles.group) return null;

  const camera = transition.camera;
  const cartographicResult = {};

  // Get inverse of tiles group matrix to convert camera to local tile space
  const tilesMatInv = tiles.group.matrixWorld.clone().invert();
  const localCameraMat = camera.matrixWorld.clone().premultiply(tilesMatInv);

  // Extract cartographic position including orientation
  WGS84_ELLIPSOID.getCartographicFromObjectFrame(
    localCameraMat,
    cartographicResult,
    CAMERA_FRAME
  );

  return {
    lat: cartographicResult.lat * MathUtils.RAD2DEG,
    lon: cartographicResult.lon * MathUtils.RAD2DEG,
    height: cartographicResult.height,
    azimuth: cartographicResult.azimuth * MathUtils.RAD2DEG,
    elevation: cartographicResult.elevation * MathUtils.RAD2DEG,
    roll: cartographicResult.roll * MathUtils.RAD2DEG,
    zoom: camera.zoom,
  };
}

// Debounced logging of camera state
function logCameraState() {
  const info = getCameraInfo();
  if (!info) return;

  // Check if state has changed significantly
  const changed =
    Math.abs(info.azimuth - lastCameraState.az) > 0.5 ||
    Math.abs(info.elevation - lastCameraState.el) > 0.5 ||
    Math.abs(info.height - lastCameraState.height) > 1 ||
    Math.abs(info.zoom - lastCameraState.zoom) > 0.01;

  if (changed) {
    lastCameraState = {
      az: info.azimuth,
      el: info.elevation,
      height: info.height,
      zoom: info.zoom,
    };

    // Clear existing timeout
    if (logTimeout) clearTimeout(logTimeout);

    // Debounce: wait 200ms before logging
    logTimeout = setTimeout(() => {
      console.log(
        `📷 Camera: Az=${info.azimuth.toFixed(1)}° El=${info.elevation.toFixed(
          1
        )}° ` +
          `Height=${info.height.toFixed(0)}m Zoom=${info.zoom.toFixed(
            2
          )} | Lat=${info.lat.toFixed(4)}° Lon=${info.lon.toFixed(4)}°`
      );
    }, 200);
  }
}

function animate() {
  requestAnimationFrame(animate);

  controls.enabled = !transition.animating;
  controls.update();
  transition.update();

  // Update tiles with current camera
  const camera = transition.camera;
  camera.updateMatrixWorld();
  tiles.setCamera(camera);
  tiles.setResolutionFromRenderer(camera, renderer);
  tiles.update();

  // Check for tile loading stability
  // We consider tiles loaded if downloading and parsing count is 0 for at least 1 second
  if (tiles.stats.downloading === 0 && tiles.stats.parsing === 0) {
    if (tilesStableStartTime === 0) {
      tilesStableStartTime = performance.now();
    } else if (performance.now() - tilesStableStartTime > 1000) {
      if (!window.TILES_LOADED) {
        window.TILES_LOADED = true;
        console.log("✅ Tiles fully loaded and stable");
      }
    }
  } else {
    tilesStableStartTime = 0;
    window.TILES_LOADED = false;
  }

  // Log camera state (debounced)
  logCameraState();

  if (composer) {
    // Keep the RenderPass camera in sync (perspective↔ortho can swap), then
    // render through the soft-stylise chain.
    composer.passes[0].camera = camera;
    composer.render();
  } else {
    renderer.render(scene, camera);
  }
}
