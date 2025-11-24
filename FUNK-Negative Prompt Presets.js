//@api-1.0
// DT Safe-Mode v3: negatives + clarity + optional sampler/frames + PROGRESS LOGGING.
// Compatible with builds where pipeline.configuration is an OBJECT (your setup).

// ---------- EDIT THESE ----------
const NEGATIVE_PRESET = [
  "blurry","low quality","noise","artifacts","distorted","deformed",
  "extra limbs","watermark","text","logo","frame borders"
].join(", ");
const CLARITY_MODE = "mild";       // "none" | "mild" | "strong"
const FORCE_SAMPLER_ID = null;     // e.g. 10 for DDIM Trailing, or null to keep current
const AUTO_RENDER = true;          // start render automatically after applying
const OPTIONAL_PATCH = {
  numFrames: null,  // e.g., 33 or 81 (null = leave unchanged)
  width:     null,  // e.g., 384
  height:    null   // e.g., 704
};
// Logging cadence
const LOG_INTERVAL_MS = 500;       // progress tick frequency
// --------------------------------

function logUI(msg){ console.log(msg); return canvas.notify?.(msg); }
function clamp(n, lo, hi){ return Math.max(lo, Math.min(hi, n)); }
function toList(s){ return (s||"").split(",").map(x=>x.trim()).filter(Boolean); }
function mergeNegatives(a,b){ return Array.from(new Set([...toList(a),...toList(b)])).join(", "); }
const sleep = ms => new Promise(r => setTimeout(r, ms));

// Apply clarity in place (only if keys exist)
function applyClarityInPlace(cfg, mode){
  const has = k => Object.prototype.hasOwnProperty.call(cfg, k);
  const cur = (k, d) => (has(k) && Number.isFinite(cfg[k]) ? cfg[k] : d);

  const curSteps = cur("steps", 7);
  const curStrength = cur("strength", 0.40);
  const curShift = cur("shift", 6);

  let steps = curSteps, strength = curStrength, shift = curShift;

  if (mode === "mild"){
    steps    = Math.max(curSteps, 8);
    strength = Math.min(curStrength, 0.35);
    shift    = clamp(curShift - 1, 3, 12);
  } else if (mode === "strong"){
    steps    = 10;
    strength = Math.min(curStrength, 0.30);
    const target = curShift >= 6 ? 5 : curShift;
    shift    = clamp(target, 4, 6);
  } // "none": leave as-is

  if (has("steps"))    cfg.steps    = steps;
  if (has("strength")) cfg.strength = strength;
  if (has("shift"))    cfg.shift    = shift;

  return { steps, strength, shift };
}

// Try multiple progress sources; return number in [0,1] or null if unavailable
function readProgress(){
  try{
    if (typeof pipeline?.getProgress === "function") {
      const v = pipeline.getProgress();
      if (Number.isFinite(v)) return clamp(v, 0, 1);
    }
    const p1 = pipeline?.progress;
    if (Number.isFinite(p1)) return clamp(p1, 0, 1);

    const st = pipeline?.status || pipeline?.state;
    const p2 = st?.progress ?? st?.pct ?? st?.ratio;
    if (Number.isFinite(p2)) {
      // Heuristics: if >1, assume percent
      return p2 > 1 ? clamp(p2/100, 0, 1) : clamp(p2, 0, 1);
    }
  } catch {}
  return null;
}

// Optional: try to read a human-readable stage if present
function readStage(){
  try{
    const st = pipeline?.status || pipeline?.state;
    return st?.stage || st?.phase || st?.message || "";
  } catch { return ""; }
}

function formatEta(ms){
  if (!Number.isFinite(ms) || ms <= 0) return "";
  const s = Math.round(ms/1000);
  const m = Math.floor(s/60);
  const sec = s % 60;
  return m ? `${m}m${sec}s` : `${sec}s`;
}

async function logProgressLoop(ctx){
  const t0 = Date.now();
  const { steps, frames } = ctx;
  const totalUnits = (Number.isFinite(steps) ? steps : 0) * (Number.isFinite(frames) ? frames : 0);

  while (ctx.running){
    const p = readProgress();
    const stage = readStage();

    let etaText = "";
    if (p !== null) {
      const elapsed = Date.now() - t0;
      const eta = p > 0 ? (elapsed * (1 - p)) / p : NaN;
      etaText = formatEta(eta);
    } else if (totalUnits > 0 && Number.isFinite(ctx.unitsDone)) {
      const elapsed = Date.now() - t0;
      const perUnit = ctx.unitsDone ? elapsed / ctx.unitsDone : NaN;
      const eta = Number.isFinite(perUnit) ? perUnit * (totalUnits - ctx.unitsDone) : NaN;
      etaText = formatEta(eta);
    }

    const pct = p !== null ? Math.round(p * 100) : null;
    const line = `🧪 Progress${stage ? ` [${stage}]` : ""}: ${pct !== null ? pct+"%" : "n/a"}${etaText ? ` | ETA ${etaText}` : ""}`;
    console.log(line);
    canvas.notify?.(line);

    await sleep(LOG_INTERVAL_MS);
  }
}

async function main(){
  try{
    if (!pipeline || !pipeline.configuration || typeof pipeline.configuration !== "object"){
      await logUI("❌ pipeline.configuration (object) not available.");
      return;
    }

    // Snapshot + plan
    const cfg = { ...pipeline.configuration };
    const before = {
      steps: cfg.steps, strength: cfg.strength, shift: cfg.shift,
      sampler: cfg.sampler, frames: cfg.numFrames, size: `${cfg.width}x${cfg.height}`
    };

    // 1) Negative prompt (confirmed key: negativePrompt)
    const finalNeg = mergeNegatives(NEGATIVE_PRESET, "");
    const newCfg = { ...cfg, negativePrompt: finalNeg };

    // 2) Optional sampler/frames/res
    if (typeof FORCE_SAMPLER_ID === "number") newCfg.sampler = FORCE_SAMPLER_ID;
    if (Number.isFinite(OPTIONAL_PATCH.numFrames)) newCfg.numFrames = OPTIONAL_PATCH.numFrames;
    if (Number.isFinite(OPTIONAL_PATCH.width))     newCfg.width     = OPTIONAL_PATCH.width;
    if (Number.isFinite(OPTIONAL_PATCH.height))    newCfg.height    = OPTIONAL_PATCH.height;

    // 3) Clarity
    const applied = applyClarityInPlace(newCfg, CLARITY_MODE);

    // 4) Write back
    Object.assign(pipeline.configuration, newCfg);

    const after = {
      steps: pipeline.configuration.steps,
      strength: pipeline.configuration.strength,
      shift: pipeline.configuration.shift,
      sampler: pipeline.configuration.sampler,
      frames: pipeline.configuration.numFrames,
      size: `${pipeline.configuration.width}x${pipeline.configuration.height}`
    };

    await logUI(
      "✅ Applied (safe-mode v3)\n" +
      `Neg: ${finalNeg || "(none)"}\n` +
      `Before: ${JSON.stringify(before)}\n` +
      `After:  ${JSON.stringify(after)}\n` +
      `Clarity: ${CLARITY_MODE}${FORCE_SAMPLER_ID!=null ? ` | SamplerID=${FORCE_SAMPLER_ID}`:""}\n` +
      `${AUTO_RENDER ? "Render: starting…" : "Render: not started"}`
    );

    // 5) Optional render + progress logging
    if (AUTO_RENDER && typeof pipeline.run === "function"){
      const ctx = {
        running: true,
        steps: pipeline.configuration.steps,
        frames: pipeline.configuration.numFrames,
        unitsDone: 0 // left here in case your build exposes unit counters later
      };
      // Start progress loop (fire-and-forget)
      logProgressLoop(ctx);
      try{
        await pipeline.run();
      } finally {
        ctx.running = false;
        await logUI("✅ Render finished.");
      }
    }
  } catch(err){
    console.log("Safe-mode v3 error:", err);
    await logUI(`💥 Error: ${String(err)}`);
  }
}

main();