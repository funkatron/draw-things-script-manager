//@api-1.0
// Waveform Generator for Draw Things
// Generates animated values using common waveforms: sine, saw, square, ramp, gaussian
// Can modify zcfg (shift), cropping, strength, guidance, and other config values
// Supports frame-by-frame animation for creating animated sequences

// ============================================================================
// Waveform Generators
// ============================================================================

/**
 * Sine wave generator
 * @param {number} t - Time/phase (0-1 or radians)
 * @param {number} min - Minimum value
 * @param {number} max - Maximum value
 * @param {number} phase - Phase offset (0-1)
 * @returns {number} Value between min and max
 */
function sineWave(t, min = 0, max = 1, phase = 0) {
  const normalized = (Math.sin((t + phase) * Math.PI * 2) + 1) / 2;
  return min + (max - min) * normalized;
}

/**
 * Sawtooth wave generator (ramp up, then reset)
 * @param {number} t - Time/phase (0-1)
 * @param {number} min - Minimum value
 * @param {number} max - Maximum value
 * @param {number} phase - Phase offset (0-1)
 * @returns {number} Value between min and max
 */
function sawWave(t, min = 0, max = 1, phase = 0) {
  const normalized = ((t + phase) % 1);
  return min + (max - min) * normalized;
}

/**
 * Square wave generator
 * @param {number} t - Time/phase (0-1)
 * @param {number} min - Minimum value
 * @param {number} max - Maximum value
 * @param {number} phase - Phase offset (0-1)
 * @param {number} dutyCycle - Duty cycle (0-1, default 0.5)
 * @returns {number} Value between min and max
 */
function squareWave(t, min = 0, max = 1, phase = 0, dutyCycle = 0.5) {
  const normalized = ((t + phase) % 1) < dutyCycle ? 1 : 0;
  return min + (max - min) * normalized;
}

/**
 * Ramp wave generator (linear increase)
 * @param {number} t - Time/phase (0-1)
 * @param {number} min - Minimum value
 * @param {number} max - Maximum value
 * @param {number} phase - Phase offset (0-1)
 * @returns {number} Value between min and max
 */
function rampWave(t, min = 0, max = 1, phase = 0) {
  // Same as sawtooth, but can be extended for different behavior
  return sawWave(t, min, max, phase);
}

/**
 * Gaussian (normal distribution) wave generator
 * @param {number} t - Time/phase (0-1)
 * @param {number} min - Minimum value
 * @param {number} max - Maximum value
 * @param {number} center - Center point (0-1, where peak occurs)
 * @param {number} width - Width of the curve (0-1, smaller = narrower)
 * @returns {number} Value between min and max
 */
function gaussianWave(t, min = 0, max = 1, center = 0.5, width = 0.2) {
  // Map t to a value that cycles through the gaussian curve
  // We'll use a periodic gaussian by mapping t to a position relative to center
  const distance = Math.abs((t - center + 0.5) % 1 - 0.5) * 2;
  const normalized = Math.exp(-Math.pow(distance / width, 2));
  return min + (max - min) * normalized;
}

// ============================================================================
// Configuration Value Modifiers
// ============================================================================

/**
 * Apply waveform to a configuration value
 * @param {Object} config - Pipeline configuration object
 * @param {string} key - Configuration key to modify
 * @param {Function} waveFunc - Waveform function
 * @param {number} frame - Current frame number (0-based)
 * @param {number} totalFrames - Total number of frames
 * @param {number} min - Minimum value
 * @param {number} max - Maximum value
 * @param {number} phase - Phase offset (0-1)
 */
function applyWaveform(config, key, waveFunc, frame, totalFrames, min, max, phase = 0) {
  const t = frame / totalFrames;
  const value = waveFunc(t, min, max, phase);
  config[key] = value;
  return value;
}

/**
 * Apply waveform to zcfg (shift) value
 */
function applyZcfgWaveform(config, waveFunc, frame, totalFrames, min = 1, max = 10, phase = 0) {
  return applyWaveform(config, 'shift', waveFunc, frame, totalFrames, min, max, phase);
}

/**
 * Apply waveform to cropping values
 */
function applyCroppingWaveform(config, waveFunc, frame, totalFrames, min = 0, max = 0.5, phase = 0) {
  const t = frame / totalFrames;
  const value = waveFunc(t, min, max, phase);

  // Apply to all crop values or specific ones
  if (config.cropLeft !== undefined) config.cropLeft = value;
  if (config.cropTop !== undefined) config.cropTop = value;
  if (config.cropRight !== undefined) config.cropRight = value;
  if (config.cropBottom !== undefined) config.cropBottom = value;

  return value;
}

/**
 * Apply waveform to strength
 */
function applyStrengthWaveform(config, waveFunc, frame, totalFrames, min = 0.1, max = 1.0, phase = 0) {
  return applyWaveform(config, 'strength', waveFunc, frame, totalFrames, min, max, phase);
}

/**
 * Apply waveform to guidance scale
 */
function applyGuidanceWaveform(config, waveFunc, frame, totalFrames, min = 1.0, max = 20.0, phase = 0) {
  return applyWaveform(config, 'guidanceScale', waveFunc, frame, totalFrames, min, max, phase);
}

// ============================================================================
// Main Script
// ============================================================================

async function main() {
  const userSelection = requestFromUser("Waveform Generator", "Apply", function() {
    return [
      this.section("Target Value", "What configuration value to modify:", [
        this.segmented(0, ["zcfg (shift)", "Cropping", "Strength", "Guidance Scale", "Custom"])
      ]),
      this.section("Waveform Type", "Select waveform:", [
        this.segmented(0, ["Sine", "Sawtooth", "Square", "Ramp", "Gaussian"])
      ]),
      this.section("Value Range", "Min and max values:", [
        this.slider(1, this.slider.fractional(0), 0, 10, "Min Value"),
        this.slider(10, this.slider.fractional(0), 0, 10, "Max Value")
      ]),
      this.section("Animation", "Frame settings:", [
        this.slider(10, this.slider.integer(1), 1, 100, "Total Frames"),
        this.slider(0, this.slider.fractional(2), 0, 1, "Phase Offset (0-1)")
      ]),
      this.section("Options", "", [
        this.switch(false, "Preview values only (don't apply)"),
        this.switch(false, "Generate animation (frame-by-frame)")
      ])
    ];
  });

  const targetType = userSelection[0][0];
  const waveformType = userSelection[1][0];
  const minValue = userSelection[2][0];
  const maxValue = userSelection[2][1];
  const totalFrames = Math.floor(userSelection[3][0]);
  const phaseOffset = userSelection[3][1];
  const previewOnly = userSelection[4][0];
  const generateAnimation = userSelection[4][1];

  // Select waveform function
  let waveFunc;
  switch (waveformType) {
    case 0: waveFunc = sineWave; break;
    case 1: waveFunc = sawWave; break;
    case 2: waveFunc = squareWave; break;
    case 3: waveFunc = rampWave; break;
    case 4: waveFunc = gaussianWave; break;
    default: waveFunc = sineWave;
  }

  // Get configuration
  const config = { ...pipeline.configuration };
  const values = [];

  if (previewOnly) {
    // Just show what values would be generated
    let preview = "Waveform Preview:\n\n";
    for (let frame = 0; frame < totalFrames; frame++) {
      const t = frame / totalFrames;
      let value;

      switch (targetType) {
        case 0: // zcfg (shift)
          value = waveFunc(t, minValue, maxValue, phaseOffset);
          preview += `Frame ${frame}: shift = ${value.toFixed(3)}\n`;
          break;
        case 1: // Cropping
          value = waveFunc(t, minValue, maxValue, phaseOffset);
          preview += `Frame ${frame}: crop = ${value.toFixed(3)}\n`;
          break;
        case 2: // Strength
          value = waveFunc(t, minValue, maxValue, phaseOffset);
          preview += `Frame ${frame}: strength = ${value.toFixed(3)}\n`;
          break;
        case 3: // Guidance Scale
          value = waveFunc(t, minValue, maxValue, phaseOffset);
          preview += `Frame ${frame}: guidanceScale = ${value.toFixed(3)}\n`;
          break;
      }

      if (frame >= 9) { // Show first 10 frames
        preview += `... (${totalFrames - 10} more frames)\n`;
        break;
      }
    }

    canvas.notify?.(preview);
    return;
  }

  // Helper function to apply waveform to config
  function applyWaveformToConfig(frameConfig, frame, totalFrames) {
    switch (targetType) {
      case 0: // zcfg (shift)
        return applyZcfgWaveform(frameConfig, waveFunc, frame, totalFrames, minValue, maxValue, phaseOffset);
      case 1: // Cropping
        return applyCroppingWaveform(frameConfig, waveFunc, frame, totalFrames, minValue, maxValue, phaseOffset);
      case 2: // Strength
        return applyStrengthWaveform(frameConfig, waveFunc, frame, totalFrames, minValue, maxValue, phaseOffset);
      case 3: // Guidance Scale
        return applyGuidanceWaveform(frameConfig, waveFunc, frame, totalFrames, minValue, maxValue, phaseOffset);
      default:
        return 0;
    }
  }

  // Apply waveform
  if (generateAnimation) {
    // Frame-by-frame animation
    const waveformNames = ["Sine", "Sawtooth", "Square", "Ramp", "Gaussian"];
    const targetNames = ["zcfg (shift)", "Cropping", "Strength", "Guidance Scale"];

    canvas.notify?.(`🎬 Starting frame-by-frame animation...\n${totalFrames} frames with ${waveformNames[waveformType]} waveform`);

    // Store original prompt
    const originalPrompt = pipeline.prompts?.prompt || "";
    const originalNegativePrompt = pipeline.prompts?.negativePrompt || "";

    // Generate frames sequentially
    for (let frame = 0; frame < totalFrames; frame++) {
      // Create config for this frame
      const frameConfig = { ...config };

      // Apply waveform value for this frame
      const value = applyWaveformToConfig(frameConfig, frame, totalFrames);

      // Ensure batch settings
      frameConfig.batchSize = 1;
      frameConfig.batchCount = 1;

      // Update progress
      const progress = ((frame + 1) / totalFrames * 100).toFixed(1);
      canvas.notify?.(`Frame ${frame + 1}/${totalFrames} (${progress}%)\n${targetNames[targetType]}: ${value.toFixed(3)}`);

      // Render this frame
      try {
        pipeline.run({
          configuration: frameConfig,
          prompt: originalPrompt,
          negativePrompt: originalNegativePrompt
        });

        // Small delay to allow rendering to complete
        // Adjust timing based on your needs
        if (frame < totalFrames - 1) {
          await new Promise(resolve => setTimeout(resolve, 200));
        }
      } catch (error) {
        canvas.notify?.(`❌ Error rendering frame ${frame + 1}: ${error.message}`);
        break;
      }
    }

    canvas.notify?.(
      `✅ Animation complete!\n` +
      `Generated ${totalFrames} frames\n` +
      `Waveform: ${waveformNames[waveformType]}\n` +
      `Target: ${targetNames[targetType]}\n` +
      `Range: ${minValue} - ${maxValue}`
    );
  } else {
    // Apply to current frame only
    const currentFrame = 0;
    let value = applyWaveformToConfig(config, currentFrame, totalFrames);

    Object.assign(pipeline.configuration, config);

    const waveformNames = ["Sine", "Sawtooth", "Square", "Ramp", "Gaussian"];
    const targetNames = ["zcfg (shift)", "Cropping", "Strength", "Guidance Scale"];

    canvas.notify?.(
      `✅ Applied ${waveformNames[waveformType]} waveform\n` +
      `Target: ${targetNames[targetType]}\n` +
      `Value: ${value.toFixed(3)} (range: ${minValue} - ${maxValue})\n` +
      `Frame: ${currentFrame + 1}/${totalFrames}\n\n` +
      `💡 Enable "Generate batch" to create ${totalFrames} animated frames`
    );
  }
}

main();

