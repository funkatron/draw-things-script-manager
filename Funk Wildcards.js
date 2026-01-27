// @api-version 1.0
// Batch Wildcard Prompt Generator v2.0 — Refactored for better usability

// ============================================================================
// Constants
// ============================================================================

const MODE_RANDOM     = 0;
const MODE_SEQUENTIAL = 1;
const MODE_CARTESIAN  = 2;
const MODE_TEST       = 3;

const MAX_BATCH_COUNT = 250;
const PREVIEW_COUNT = 3;

const PREVIEW_EXAMPLES = {
  random: ['red | cat', 'blue | cat', 'red | dog'],
  sequential: ['red | cat', 'blue | dog', 'red | cat'],
  cartesian: ['red | cat', 'red | dog', 'blue | cat']
};

// ============================================================================
// Wildcard Parsing Functions
// ============================================================================

/**
 * Extracts all wildcard groups from text.
 * @param {string} text - Text containing wildcards like {option1|option2}
 * @returns {string[]} Array of wildcard group contents (without braces)
 */
function extractWildcardGroups(text) {
  const groups = [];
  const regex = /\{([^{}]+)\}/g;
  let match;
  while ((match = regex.exec(text))) {
    groups.push(match[1]);
  }
  return groups;
}

/**
 * Splits a wildcard group into individual options.
 * @param {string} groupText - Text like "option1|option2|option3"
 * @returns {string[]} Array of trimmed options
 */
function splitOptions(groupText) {
  return groupText.split('|').map(opt => opt.trim()).filter(opt => opt.length > 0);
}

/**
 * Gets all options for each wildcard group in the prompt.
 * @param {string} promptText - Prompt containing wildcards
 * @returns {string[][]} Array of option arrays, one per wildcard group
 */
function getAllOptions(promptText) {
  return extractWildcardGroups(promptText).map(splitOptions);
}

/**
 * Replaces wildcards in prompt with provided values.
 * @param {string} promptText - Prompt with wildcards
 * @param {string[]} values - Values to substitute (one per wildcard)
 * @returns {string} Prompt with wildcards replaced
 */
function applyValuesToPrompt(promptText, values) {
  let idx = 0;
  return promptText.replace(/\{([^{}]+)\}/g, () => values[idx++] || '');
}

/**
 * Computes Cartesian product of multiple option arrays.
 * @param {string[][]} lists - Array of option arrays
 * @returns {string[][]} All possible combinations
 */
function computeCartesianProduct(lists) {
  if (lists.length === 0) return [[]];

  let result = [[]];
  for (const opts of lists) {
    const newResult = [];
    for (const prev of result) {
      for (const opt of opts) {
        newResult.push([...prev, opt]);
      }
    }
    result = newResult;
  }
  return result;
}

/**
 * Computes the first N combinations without full expansion.
 * @param {string[][]} lists - Array of option arrays
 * @param {number} limit - Max combinations to return
 * @returns {string[][]} First combinations up to limit
 */
function computeCartesianPreview(lists, limit) {
  if (lists.length === 0) return [[]];
  const result = [];
  const indices = new Array(lists.length).fill(0);
  const totalCombos = lists.reduce((total, opts) => total * opts.length, 1);
  const maxCount = Math.min(limit, totalCombos);

  for (let count = 0; count < maxCount; count++) {
    const combo = indices.map((idx, listIndex) => lists[listIndex][idx] || '');
    result.push(combo);

    for (let i = indices.length - 1; i >= 0; i--) {
      indices[i] += 1;
      if (indices[i] < lists[i].length) {
        break;
      }
      indices[i] = 0;
    }
  }

  return result;
}

/**
 * Calculates the maximum number of possible combinations.
 * @param {string} promptText - Prompt with wildcards
 * @returns {number} Total possible combinations
 */
function calculateMaxCombinations(promptText) {
  const optionsList = getAllOptions(promptText);
  if (optionsList.length === 0) return 0;
  return optionsList.reduce((total, opts) => total * opts.length, 1);
}

// ============================================================================
// Generation Functions
// ============================================================================

/**
 * Runs a single generation with the given prompt and configuration.
 * @param {string} promptText - Final prompt (wildcards already replaced)
 * @param {object} config - Generation configuration
 */
function runGeneration(promptText, config) {
  pipeline.run({
    configuration: config,
    prompt: promptText
  });
}

/**
 * Logs substitutions used for a generation.
 * @param {string[]} values - Substitution values in wildcard order
 * @param {number} index - Zero-based generation index
 * @param {number} total - Total generation count
 * @param {string} modeName - Mode name for context
 * @param {boolean} debugEnabled - Whether debug logging is enabled
 * @param {string[][]} [optionsList] - Optional options list for debug
 */
function logSubstitutions(values, index, total, modeName, debugEnabled, optionsList) {
  const displayValues = values.map(value => value || '');
  console.log(`[${index + 1}/${total}] ${modeName} substitutions: ${displayValues.join(' | ')}`);

  if (debugEnabled) {
    console.log(`[DEBUG] Mode: ${modeName}`);
    console.log(`[DEBUG] Substitution count: ${displayValues.length}`);
    if (optionsList && optionsList.length > 0) {
      const optionSizes = optionsList.map(opts => opts.length);
      console.log(`[DEBUG] Wildcard groups: ${optionSizes.join(', ')}`);
    }
  }
}

/**
 * Generates prompts in Random mode.
 * Each wildcard is randomly replaced for each generation.
 */
function generateRandom(promptText, count, config, debugEnabled) {
  const optionsList = getAllOptions(promptText);

  for (let i = 0; i < count; i++) {
    const selectedValues = optionsList.map(opts => {
      if (opts.length === 0) return '';
      const randomIndex = Math.floor(Math.random() * opts.length);
      return opts[randomIndex];
    });
    const filledPrompt = applyValuesToPrompt(promptText, selectedValues);

    console.log(`[${i + 1}/${count}] Random: ${filledPrompt}`);
    logSubstitutions(selectedValues, i, count, 'Random', debugEnabled, optionsList);
    runGeneration(filledPrompt, config);
  }
}

/**
 * Generates prompts in Sequential mode.
 * Cycles through options sequentially, wrapping around.
 */
function generateSequential(promptText, count, config, debugEnabled) {
  const optionsList = getAllOptions(promptText);

  for (let i = 0; i < count; i++) {
    const selectedValues = optionsList.map(opts => {
      const index = i % opts.length;
      return opts[index];
    });

    const filledPrompt = applyValuesToPrompt(promptText, selectedValues);
    console.log(`[${i + 1}/${count}] Sequential: ${filledPrompt}`);
    logSubstitutions(selectedValues, i, count, 'Sequential', debugEnabled, optionsList);
    runGeneration(filledPrompt, config);
  }
}

/**
 * Generates prompts in Cartesian mode.
 * Generates all possible combinations (up to count limit).
 */
function generateCartesian(promptText, count, config, debugEnabled) {
  const optionsList = getAllOptions(promptText);
  const totalPossible = calculateMaxCombinations(promptText);
  const limitedCombinations = computeCartesianPreview(optionsList, count);
  if (totalPossible > count) {
    console.log(`Note: ${totalPossible} combinations possible, generating first ${count}`);
  }

  limitedCombinations.forEach((combo, index) => {
    const filledPrompt = applyValuesToPrompt(promptText, combo);
    console.log(`[${index + 1}/${limitedCombinations.length}] Cartesian: ${filledPrompt}`);
    logSubstitutions(combo, index, limitedCombinations.length, 'Cartesian', debugEnabled, optionsList);
    runGeneration(filledPrompt, config);
  });
}

/**
 * Runs test mode to validate wildcard parsing.
 */
function runTestMode(config) {
  const testPrompt = 'smoke {one|two}';
  const multiPrompt = 'a {red|blue} {cat|dog|fox}';
  console.log('Running test mode...');

  try {
    const groups = extractWildcardGroups(testPrompt);
    if (groups.length !== 1 || groups[0] !== 'one|two') {
      throw new Error('extractWildcardGroups failed');
    }

    const options = splitOptions(groups[0]);
    if (options.length !== 2 || options[0] !== 'one' || options[1] !== 'two') {
      throw new Error('splitOptions failed');
    }

    const result = applyValuesToPrompt(testPrompt, [options[0]]);
    const successMessage = `TEST MODE SUCCESS: ${result}`;
    console.log(successMessage);
    runGeneration(successMessage, config);

    const multiGroups = extractWildcardGroups(multiPrompt);
    if (multiGroups.length !== 2) {
      throw new Error('extractWildcardGroups (multi) failed');
    }

    const multiOptions = getAllOptions(multiPrompt);
    const expectedCombos = multiOptions.reduce((total, opts) => total * opts.length, 1);
    const actualCombos = calculateMaxCombinations(multiPrompt);
    if (actualCombos !== expectedCombos) {
      throw new Error(`calculateMaxCombinations failed: ${actualCombos}`);
    }

    const combos = computeCartesianProduct(multiOptions);
    if (combos.length !== expectedCombos) {
      throw new Error(`computeCartesianProduct failed: ${combos.length}`);
    }

    const previewCombos = computeCartesianPreview(multiOptions, PREVIEW_COUNT);
    if (previewCombos.length !== PREVIEW_COUNT) {
      throw new Error(`computeCartesianPreview failed: ${previewCombos.length}`);
    }

    if (MAX_BATCH_COUNT < 1) {
      throw new Error('MAX_BATCH_COUNT must be >= 1');
    }
  } catch (error) {
    console.error('Test mode failed:', error.message);
    throw error;
  }
}

// ============================================================================
// UI Functions
// ============================================================================

/**
 * Creates and displays the main user interface.
 * @returns {Array} User input array: [promptText, batchCount, modeIndex]
 */
function showMainUI() {
  const currentPrompt = pipeline.prompts.prompt || '';
  const maxCombos = calculateMaxCombinations(currentPrompt);
  const hasWildcards = currentPrompt.includes('{') && currentPrompt.includes('}');

  const wildcardHint = hasWildcards
    ? `Found wildcards! Max combinations: ${maxCombos.toLocaleString()}`
    : 'Enter a prompt with wildcards like: {option1|option2|option3}';
  const cappedMaxCombos = Math.min(maxCombos, MAX_BATCH_COUNT);
  const maxCountHint = maxCombos > 0
    ? `Max combinations for current prompt: ${cappedMaxCombos}${maxCombos > MAX_BATCH_COUNT ? ' (capped)' : ''}`
    : 'Max combinations unavailable until prompt has wildcards.';
  return requestFromUser('Wildcard Batch Generator', 'Generate', function() {
    return [
      this.section('Prompt', 'Use {option1|option2|option3} syntax for wildcards:', [
        this.textField(
          currentPrompt,
          'Example: a {red|blue|green} {cat|dog} in a {park|beach|forest}',
          true,
          200
        ),
        this.plainText(wildcardHint)
      ]),

      this.section('Batch Settings', 'Configure how many images to generate:', [
        this.slider(10, this.slider.fractional(0), 1, MAX_BATCH_COUNT, 'Number of images'),
        this.switch(false, `Create max (<=${MAX_BATCH_COUNT})`),
        this.switch(false, 'Use same seed for every generation'),
        this.switch(false, 'Debug logging'),
        this.plainText(maxCountHint),
        this.plainText('Each image will use different wildcard combinations')
      ]),

      this.section('Generation Mode', 'Choose how wildcards are processed:', [
        this.segmented(0, ['Random', 'Sequential', 'Cartesian', 'Test']),
        this.plainText('Mode descriptions (static):'),
        this.plainText('Random: Picks options randomly; may repeat'),
        this.plainText('Sequential: Cycles per wildcard index (0,1,2...)'),
        this.plainText('Cartesian: Enumerates all combinations (ordered)'),
        this.plainText('Test: Validate parsing')
      ]),

      this.section('Preview (values only)', 'Static examples (not computed):', (function() {
        const previewElements = [];
        previewElements.push(this.plainText('Example: {red|blue} {cat|dog}'));
        previewElements.push(this.plainText('Random example (may repeat):'));
        PREVIEW_EXAMPLES.random.slice(0, PREVIEW_COUNT).forEach((line, index) => {
          previewElements.push(this.plainText(`${index + 1}) ${line}`));
        });
        previewElements.push(this.plainText(`Sequential example (first ${PREVIEW_COUNT}):`));
        PREVIEW_EXAMPLES.sequential.slice(0, PREVIEW_COUNT).forEach((line, index) => {
          previewElements.push(this.plainText(`${index + 1}) ${line}`));
        });
        previewElements.push(this.plainText(`Cartesian example (first ${PREVIEW_COUNT}):`));
        PREVIEW_EXAMPLES.cartesian.slice(0, PREVIEW_COUNT).forEach((line, index) => {
          previewElements.push(this.plainText(`${index + 1}) ${line}`));
        });
        return previewElements;
      }).call(this))
    ];
  });
}

/**
 * Shows an error dialog when no wildcards are found.
 */
function showNoWildcardsError() {
  return requestFromUser('No Wildcards Found', 'OK', function() {
    return [
      this.section('Error', '', [
        this.plainText('Please include at least one wildcard in your prompt.'),
        this.plainText(''),
        this.plainText('Example format:'),
        this.plainText('a {red|blue|green} {cat|dog}'),
        this.plainText(''),
        this.plainText('Use curly braces {} and separate options with |')
      ])
    ];
  });
}

/**
 * Shows completion dialog with summary.
 */
function showCompletionDialog(modeIndex, batchCount, actualCount) {
  const modeNames = ['Random', 'Sequential', 'Cartesian', 'Test'];
  const modeName = modeNames[modeIndex] || 'Unknown';

  let message = '';
  if (modeIndex === MODE_TEST) {
    message = 'Test mode completed successfully!';
  } else if (modeIndex === MODE_CARTESIAN && actualCount !== batchCount) {
    message = `Generated ${actualCount} of ${batchCount} requested images.\n(Cartesian mode limited by available combinations)`;
  } else {
    message = `Successfully generated ${actualCount} image${actualCount !== 1 ? 's' : ''} using ${modeName} mode.`;
  }

  return requestFromUser('Generation Complete', 'OK', function() {
    return [
      this.section('Summary', '', [
        this.plainText(message),
        this.plainText(''),
        this.plainText('Check the console for detailed logs.')
      ])
    ];
  });
}

// ============================================================================
// Main Function
// ============================================================================

function main() {
  try {
    // Get user input
    const userInput = showMainUI();
    const promptText = userInput[0][0].trim();
    let batchCount = Math.floor(userInput[1][0]);
    const useMaxCount = userInput[1][1];
    const useSameSeed = userInput[1][2];
    const debugEnabled = userInput[1][3];
    const modeIndex = userInput[2][0];
    const maxCombosForPrompt = calculateMaxCombinations(promptText);

    // Validate input
    if (!promptText) {
      showNoWildcardsError();
      return;
    }

    if (modeIndex !== MODE_TEST && !promptText.includes('{')) {
      showNoWildcardsError();
      return;
    }

    if (useMaxCount && maxCombosForPrompt > 0 && maxCombosForPrompt <= MAX_BATCH_COUNT) {
      batchCount = maxCombosForPrompt;
    }

    if (batchCount > MAX_BATCH_COUNT) {
      console.warn(`Batch count capped at ${MAX_BATCH_COUNT} (was ${batchCount})`);
      batchCount = MAX_BATCH_COUNT;
    }

    if (useMaxCount && debugEnabled) {
      console.log(`[DEBUG] Create max enabled: using ${batchCount}`);
    }

    if (batchCount < 1 || batchCount > MAX_BATCH_COUNT) {
      console.error('Invalid batch count:', batchCount);
      return;
    }

    const modeName = ['Random', 'Sequential', 'Cartesian', 'Test'][modeIndex];

    // Prepare configuration (use random seed for variety unless same-seed enabled)
    const config = { ...pipeline.configuration };
    if (!useSameSeed) {
      config.seed = -1;
    }

    // Log start
    console.log('\n=== Wildcard Batch Generator ===');
    console.log(`Mode: ${modeName}`);
    console.log(`Batch count: ${batchCount}`);
    console.log(`Original prompt: ${promptText}`);
    console.log('');
    if (debugEnabled) {
      console.log(`[DEBUG] Max combinations for prompt: ${maxCombosForPrompt}`);
      console.log(`[DEBUG] Use same seed: ${useSameSeed}`);
    }

    // Generate based on mode
    let actualCount = batchCount;

    switch (modeIndex) {
      case MODE_RANDOM:
        generateRandom(promptText, batchCount, config, debugEnabled);
        break;

      case MODE_SEQUENTIAL:
        generateSequential(promptText, batchCount, config, debugEnabled);
        break;

      case MODE_CARTESIAN:
        actualCount = Math.min(batchCount, maxCombosForPrompt);
        generateCartesian(promptText, batchCount, config, debugEnabled);
        break;

      case MODE_TEST:
        runTestMode(config);
        actualCount = 1;
        break;

      default:
        console.warn('Unknown mode, using Random');
        generateRandom(promptText, batchCount, config);
    }

    console.log('\n=== Generation Complete ===\n');

    // Show completion dialog
    showCompletionDialog(modeIndex, batchCount, actualCount);

  } catch (error) {
    console.error('Error in wildcard generator:', error);
    requestFromUser('Error', 'OK', function() {
      return [
        this.section('Error', '', [
          this.plainText(`An error occurred: ${error.message || String(error)}`),
          this.plainText(''),
          this.plainText('Check the console for details.')
        ])
      ];
    });
  }
}

// Run the script
main();