# Draw Things JavaScript API Reference

> **For AI Agents**: This document describes the non-standard JavaScript environment used by Draw Things scripts. This is NOT Node.js or browser JavaScript.

## Overview

Draw Things is an AI image generation app for macOS/iOS. Scripts extend its functionality using a sandboxed JavaScript environment with custom APIs for image generation, canvas manipulation, and user interaction.

**Official Resources:**
- Wiki: https://wiki.drawthings.ai/wiki/Scripting_Basics
- Community Scripts: https://github.com/drawthingsai/community-scripts

---

## Script Structure

Scripts must declare their API version at the top:

```javascript
//@api-1.0
```

Scripts typically follow this pattern:

```javascript
//@api-1.0

// 1. Get user input (optional)
const userSelection = requestFromUser("Title", "Run", function() {
  return [/* UI elements */];
});

// 2. Get/modify configuration
const config = { ...pipeline.configuration };

// 3. Run generation
pipeline.run({
  configuration: config,
  prompt: "your prompt",
  negativePrompt: "negative prompt"
});
```

---

## Global Objects

### `pipeline` — Generation Engine

The core object for running image generation.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `pipeline.configuration` | Object | Mutable configuration object (see Configuration Properties) |
| `pipeline.prompts.prompt` | String | Current positive prompt from UI |
| `pipeline.prompts.negativePrompt` | String | Current negative prompt from UI |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `pipeline.run(options)` | void | Execute generation (blocking call) |
| `pipeline.downloadBuiltins(names[])` | void | Download built-in models/LoRAs |
| `pipeline.findLoRAByName(displayName)` | `{file: string}` | Resolve LoRA display name to filename |
| `pipeline.findControlByName(displayName)` | Control | Find ControlNet by display name |

#### `pipeline.run(options)`

```javascript
pipeline.run({
  configuration: configObject,     // Required: generation settings
  prompt: "positive prompt",       // Required: what to generate
  negativePrompt: "negative",      // Optional: what to avoid
  mask: maskObject                 // Optional: for inpainting
});
```

**Important:** `pipeline.run()` is **blocking** — it waits for generation to complete before returning.

---

### Configuration Properties

The `pipeline.configuration` object contains all generation settings:

```javascript
{
  // === Dimensions ===
  width: 1024,              // Must be multiple of 64
  height: 1024,             // Must be multiple of 64

  // === Generation Parameters ===
  steps: 20,                // Number of inference steps
  strength: 0.75,           // Denoising strength (0-1, for img2img)
  seed: -1,                 // -1 for random, or specific seed
  guidanceScale: 7.5,       // CFG scale / text guidance
  shift: 3.0,               // zcfg / shift value (model-dependent)
  clipSkip: 1,              // CLIP skip layers
  sharpness: 0,             // Output sharpening

  // === Sampler ===
  sampler: 0,               // SamplerType enum value (see below)
  stochasticSamplingGamma: 0.3,  // For stochastic samplers

  // === Batch Settings ===
  batchSize: 1,             // Images per batch
  batchCount: 1,            // Number of batches

  // === Models ===
  model: "model_name.ckpt",           // Base model filename
  loras: [                            // LoRA array
    { file: "lora.ckpt", weight: 0.8 }
  ],
  controls: [controlObject],          // ControlNet array
  upscaler: "4x UltraSharp",          // Upscaler name or null
  refinerModel: null,                 // SDXL refiner or null
  faceRestoration: null,              // Face restoration or null

  // === Tiled Processing (for large images) ===
  tiledDecoding: false,
  decodingTileWidth: 1024,
  decodingTileHeight: 1024,
  decodingTileOverlap: 128,
  tiledDiffusion: false,
  diffusionTileWidth: 1024,
  diffusionTileHeight: 1024,
  diffusionTileOverlap: 128,

  // === Inpainting ===
  maskBlur: 8,
  maskBlurOutset: 0,
  preserveOriginalAfterInpaint: true,

  // === Hi-Res Fix ===
  hiresFix: false,

  // === Advanced ===
  zeroNegativePrompt: false,
  resolutionDependentShift: true,
  clipLText: "",                      // CLIP-L text (for dual-encoder models)

  // === Video/Animation ===
  numFrames: 16,                      // For video models

  // === Cropping (for some models) ===
  cropLeft: 0,
  cropTop: 0,
  cropRight: 0,
  cropBottom: 0
}
```

#### SamplerType Enum

```javascript
SamplerType = {
  DPMPP_2M_KARRAS: 0,
  EULER_A: 1,
  DDIM: 2,
  PLMS: 3,
  DPMPP_SDE_KARRAS: 4,
  UNI_PC: 5,
  LCM: 6,
  EULER_A_SUBSTEP: 7,
  DPMPP_SDE_SUBSTEP: 8,
  TCD: 9,
  EULER_A_TRAILING: 10,
  DPMPP_SDE_TRAILING: 11,
  DPMPP_2M_AYS: 12,
  EULER_A_AYS: 13,
  DPMPP_SDE_AYS: 14,
  DPMPP_2M_TRAILING: 15,
  DDIM_TRAILING: 16
}
```

Use integer values in configuration:
```javascript
configuration.sampler = 9;  // TCD sampler
// OR
configuration.sampler = SamplerType.TCD;
```

---

### `canvas` — Canvas Operations

Manages the infinite canvas where images are displayed.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `canvas.boundingBox` | `{x, y, width, height}` | Current image bounds |
| `canvas.canvasZoom` | Number | Current zoom level (get/set) |
| `canvas.foregroundMask` | Mask | Mask object for inpainting |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `canvas.clear()` | void | Remove all images from canvas |
| `canvas.updateCanvasSize(config)` | void | Resize to config's width/height |
| `canvas.moveCanvas(x, y)` | void | Pan canvas to coordinates |
| `canvas.saveImage(path, overwrite?)` | void | Save canvas to file |
| `canvas.saveImageSrc(asPng?)` | DataSrc | Get image as data source |
| `canvas.loadImage(path)` | void | Load image from file path |
| `canvas.loadCustomLayerFromSrc(src)` | void | Load from data source |
| `canvas.detectFaces()` | Face[] | Detect faces in current image |
| `canvas.notify?.(message)` | void | Show toast notification |

#### Face Detection

```javascript
const faces = canvas.detectFaces();
// Returns array of:
// {
//   origin: { x: number, y: number },
//   size: { width: number, height: number }
// }

// Sort by size (largest first)
faces.sort((a, b) =>
  (b.size.width * b.size.height) - (a.size.width * a.size.height)
);
```

#### Mask Operations

```javascript
const mask = canvas.foregroundMask;
mask.fillRectangle(x, y, width, height, value);
// value: 0 = transparent (don't generate), 1 = fill (generate)
```

#### Notifications

Use optional chaining — `notify` may not exist in all builds:

```javascript
canvas.notify?.("✅ Operation complete!");
canvas.notify?.(`Processing frame ${i} of ${total}`);
```

---

### `filesystem` — File System Access

Limited file system access within the Pictures directory.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `filesystem.pictures.path` | String | Absolute path to Pictures folder |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `filesystem.pictures.readEntries(subdir)` | String[] | List files in subdirectory |

#### Example

```javascript
const picturesPath = filesystem.pictures.path;
const files = filesystem.pictures.readEntries("DrawThings/MyFolder");

// Filter out system files
const images = files.filter(f => !f.endsWith(".DS_Store"));

// Save to Pictures
canvas.saveImage(`${picturesPath}/DrawThings/output.png`, true);
```

---

### `requestFromUser()` — UI Dialogs

Creates interactive dialogs for user input.

#### Syntax

```javascript
const result = requestFromUser(title, buttonLabel, function() {
  return [
    this.section(title, description, [elements])
  ];
});
```

#### UI Elements

| Element | Syntax | Returns |
|---------|--------|---------|
| Section | `this.section(title, desc, [children])` | Array of child values |
| Segmented | `this.segmented(defaultIndex, ["A", "B", "C"])` | Selected index (0-based) |
| Slider (float) | `this.slider(default, this.slider.fractional(decimals), min, max, "Label")` | Number |
| Slider (int) | `this.slider(default, this.slider.integer(step), min, max, "Label")` | Number |
| Switch | `this.switch(defaultBool, "Label")` | Boolean |
| Text Field | `this.textField(default, placeholder, multiline?, height?)` | String |
| Directory | `this.directory(defaultPath)` | String (selected path) |
| Plain Text | `this.plainText("Static text")` | — |

#### Example

```javascript
const result = requestFromUser("Settings", "Apply", function() {
  return [
    this.section("Generation", "Configure output:", [
      this.segmented(0, ["Low", "Medium", "High"]),
      this.slider(20, this.slider.integer(1), 1, 50, "Steps"),
      this.slider(7.5, this.slider.fractional(1), 1, 20, "CFG Scale"),
      this.switch(false, "Enable Hi-Res Fix"),
      this.textField("", "Custom prompt suffix", false, 40)
    ]),
    this.section("Output", "", [
      this.directory(filesystem.pictures.path)
    ])
  ];
});

// Access results (nested arrays matching structure)
const quality = result[0][0];      // 0, 1, or 2
const steps = result[0][1];        // number
const cfgScale = result[0][2];     // number
const hiResFix = result[0][3];     // boolean
const suffix = result[0][4];       // string
const outputDir = result[1][0];    // string
```

---

## Utility Functions

### Built-in

| Function | Description |
|----------|-------------|
| `console.log(msg)` | Log to Draw Things console |
| `console.warn(msg)` | Warning log |
| `console.error(msg)` | Error log |
| `__dtSleep(seconds)` | Blocking sleep (Draw Things specific) |

### Standard JavaScript

These work as expected:
- `Date.now()`, `new Date()`
- `Math.*` functions
- `JSON.stringify()`, `JSON.parse()`
- `setTimeout()`, `Promise`, `async/await`
- Array methods, Object methods
- Template literals, destructuring, spread operator
- Classes, generators (`function*`, `yield`)

---

## Common Patterns

### 1. Copy Configuration Before Modifying

```javascript
// GOOD: Create a copy
const config = { ...pipeline.configuration };
config.steps = 30;
pipeline.run({ configuration: config, prompt: "..." });

// ALSO GOOD: Mutate in place for persistent changes
Object.assign(pipeline.configuration, { steps: 30 });
```

### 2. Frame-by-Frame Animation

```javascript
const originalPrompt = pipeline.prompts.prompt;

for (let frame = 0; frame < totalFrames; frame++) {
  const frameConfig = { ...pipeline.configuration };
  frameConfig.batchSize = 1;
  frameConfig.batchCount = 1;

  // Modify per-frame values
  frameConfig.shift = calculateValue(frame, totalFrames);

  canvas.notify?.(`Frame ${frame + 1}/${totalFrames}`);

  pipeline.run({
    configuration: frameConfig,
    prompt: originalPrompt
  });
}
```

### 3. Error Handling

```javascript
try {
  pipeline.run({ configuration: config, prompt: prompt });
} catch (error) {
  const msg = error?.message || String(error);
  console.error("Generation failed:", msg);
  canvas.notify?.(`❌ Error: ${msg}`);
}
```

### 4. Defensive API Access

Some builds have different API shapes:

```javascript
// Check if configuration is function or object
if (typeof pipeline.configuration === "function") {
  const cfg = await pipeline.configuration();
} else {
  const cfg = { ...pipeline.configuration };
}

// Optional chaining for uncertain methods
canvas.notify?.("Message");
const progress = pipeline.getProgress?.() ?? null;
```

### 5. LoRA Resolution

```javascript
// LoRAs can be specified by display name or filename
const loras = [
  { file: "my_lora_f16.ckpt", weight: 0.8 },  // Direct filename
  { file: pipeline.findLoRAByName("My LoRA").file, weight: 0.5 }  // Resolved
];
config.loras = loras;
```

### 6. Downloading Models

```javascript
// Download before use
pipeline.downloadBuiltins([
  "juggernaut_reborn_q6p_q8p.ckpt",
  "controlnet_tile_1.x_v1.1_f16.ckpt"
]);
```

---

## What's NOT Available

This is a sandboxed environment. These do NOT exist:

- `window`, `document`, `DOM`
- `fetch`, `XMLHttpRequest`
- `require`, `import` (ES modules)
- `process`, `Buffer` (Node.js)
- `localStorage`, `sessionStorage`
- Network access
- Arbitrary file system access (only Pictures folder)

---

## Debugging Tips

1. **Use console.log liberally** — Output appears in Draw Things console
2. **Use canvas.notify for user feedback** — Shows toast messages
3. **Check API availability** — Use optional chaining (`?.`) for uncertain APIs
4. **Test incrementally** — Run small pieces before full scripts
5. **Log configuration** — `console.log(JSON.stringify(pipeline.configuration))` to see all settings

---

## Script Metadata

Scripts are registered in `custom_scripts.json`:

```json
{
  "name": "Display Name",
  "file": "script-filename.js",
  "description": "What this script does",
  "author": "Author Name",
  "tags": ["image-to-image", "text-to-image"],
  "baseColor": "#FF5500",
  "favicon": "data:image/png;base64,..."
}
```

Use `script_manager.py` to manage this file.
