//@api-1.0
// Minimal Apply — defensive: sets negative prompt + clarity only if fields exist.
// No rendering. Safe on builds with object-style configuration.

function logUI(m){ console.log(m); return canvas.notify?.(m); }
function isFn(x){ return typeof x === "function"; }

async function getCfg(){
  if (isFn(pipeline?.configuration)) {
    try { return { cfg: await pipeline.configuration(), kind: "fn" }; } catch {}
  }
  if (pipeline && typeof pipeline.configuration === "object") {
    return { cfg: { ...pipeline.configuration }, kind: "obj" };
  }
  return { cfg: {}, kind: "none" };
}

async function setCfg(newCfg, kind){
  if (isFn(pipeline?.setConfiguration)) {
    try { await pipeline.setConfiguration(newCfg); return "setConfiguration()"; } catch {}
  }
  if (kind === "obj" && pipeline && typeof pipeline.configuration === "object") {
    Object.assign(pipeline.configuration, newCfg);
    return "Object.assign(pipeline.configuration, …)";
  }
  return "no-op";
}

function chooseNegKey(cfg){
  const candidates = ["negativePrompt","negative_prompt","negPrompt"];
  return candidates.find(k => k in (cfg || {})) || candidates[0];
}

function applyClarityInPlace(cfg, mode){
  const stepsKey = "steps";
  const strengthKey = "strength";
  const shiftKey = "shift";

  const curSteps = Number.isFinite(cfg[stepsKey]) ? cfg[stepsKey] : 7;
  const curStrength = Number.isFinite(cfg[strengthKey]) ? cfg[strengthKey] : 0.40;
  const curShift = Number.isFinite(cfg[shiftKey]) ? cfg[shiftKey] : 6;

  let steps = curSteps, strength = curStrength, shift = curShift;
  if (mode === "mild"){ steps = Math.max(curSteps, 8); strength = Math.min(curStrength, 0.35); shift = Math.max(3, curShift - 1); }
  if (mode === "strong"){ steps = 10; strength = Math.min(curStrength, 0.30); shift = Math.min(Math.max(curShift >= 6 ? 5 : curShift, 4), 6); }

  if (stepsKey in cfg) cfg[stepsKey] = steps;
  if (strengthKey in cfg) cfg[strengthKey] = strength;
  if (shiftKey in cfg) cfg[shiftKey] = shift;

  return { steps, strength, shift };
}

async function main(){
  const { cfg, kind } = await getCfg();
  await logUI(`🔧 Config access kind: ${kind}`);

  // Ask user (kept minimal to avoid construction.call issues)
  const negPreset = "blurry, low quality, noise, artifacts, distorted, deformed, extra limbs, watermark, text, logo, frame borders";
  const clarityMode = "mild"; // change to "strong" if you want the stronger tweak

  const negKey = chooseNegKey(cfg);
  cfg[negKey] = negPreset;

  const applied = applyClarityInPlace(cfg, clarityMode);

  const how = await setCfg(cfg, kind);

  await logUI(
    `✅ Applied via ${how}\n` +
    `Neg key: ${negKey}\n` +
    `Steps=${applied.steps} Strength=${applied.strength.toFixed?.(2) ?? applied.strength} Shift=${applied.shift}`
  );

  // no pipeline.run() here; add later once we confirm runtime supports it
}

main();