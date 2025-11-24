// @api-version 1.0
// Batch Wildcard Prompt Generator v1.7 — Context-bound UI callbacks

// --- Modes ---
const MODE_RANDOM     = 0;
const MODE_SEQUENTIAL = 1;
const MODE_CARTESIAN  = 2;
const MODE_TEST       = 3;

// --- Helpers ---
function extractWildcardGroups(text) {
  const groups = [];
  const regex = /\{([^{}]+)\}/g;
  let match;
  while ((match = regex.exec(text))) groups.push(match[1]);
  return groups;
}

function splitOptions(groupText) {
  return groupText.split('|').map(opt => opt.trim());
}

function getAllOptions(promptText) {
  return extractWildcardGroups(promptText).map(splitOptions);
}

function applyValuesToPrompt(promptText, values) {
  let idx = 0;
  return promptText.replace(/\{([^{}]+)\}/g, () => values[idx++] || '');
}

function computeCartesianProduct(lists) {
  let result = [[]];
  lists.forEach(opts => {
    const newRes = [];
    result.forEach(prev => opts.forEach(opt => newRes.push(prev.concat(opt))));
    result = newRes;
  });
  return result;
}

// --- Runner Wrapper ---
function runPrompt(promptText, cfg) {
  pipeline.run({ configuration: cfg, prompt: promptText });
}

// --- Mode Handlers ---
function handleRandomMode(promptText, count, cfg) {
  const regex = /\{([^{}]+)\}/g;
  for (let i = 0; i < count; i++) {
    const filled = promptText.replace(regex, (_, inner) => {
      const opts = splitOptions(inner);
      return opts[Math.floor(Math.random() * opts.length)];
    });
    runPrompt(filled, cfg);
  }
}

function handleSequentialMode(promptText, count, cfg) {
  const optsList = getAllOptions(promptText);
  for (let i = 0; i < count; i++) {
    const set = optsList.map(opts => opts[i % opts.length]);
    runPrompt(applyValuesToPrompt(promptText, set), cfg);
  }
}

function handleCartesianMode(promptText, count, cfg) {
  const optsList = getAllOptions(promptText);
  computeCartesianProduct(optsList)
    .slice(0, count)
    .forEach(combo => runPrompt(applyValuesToPrompt(promptText, combo), cfg));
}

function handleTestMode(cfg) {
  const sample = 'smoke {one|two}';
  const groups = extractWildcardGroups(sample);
  if (groups[0] !== 'one|two') throw new Error('extractWildcardGroups failed');
  const opts = splitOptions(groups[0]);
  if (opts[0] !== 'one' || opts[1] !== 'two') throw new Error('splitOptions failed');
  runPrompt(`TEST MODE SUCCESS: ${applyValuesToPrompt(sample, [opts[0]])}`, cfg);
}

// --- Main Function ---
function main() {
  const userInput = requestFromUser('Wildcards Batch', 'Run', function() {
    // `this` is the builder
    return [
      this.section('Prompt Settings', 'Enter your wildcard prompt and batch size:', [
        this.textField(pipeline.prompts.prompt, 'shape: {cube|sphere}', true, 240),
        this.slider(10, this.slider.fractional(0), 1, 100, 'Batch count'),
        this.segmented(0, ['Random', 'Sequential', 'Cartesian', 'Test']),
        this.plainText(
          'Max combos: ' + getAllOptions(pipeline.prompts.prompt).reduce((a, o) => a * o.length, 1)
        )
      ])
    ];
  });

  const promptText = userInput[0][0];
  const batchCount = userInput[0][1];
  const modeIndex  = userInput[0][2];
  const cfg        = { ...pipeline.configuration, seed: -1 };

  if (modeIndex !== MODE_TEST && promptText.indexOf('{') < 0) {
    return requestFromUser('No Wildcards', 'OK', function() {
      return [
        this.section('', '', [
          this.plainText('Please include at least one wildcard in `{}`.')
        ])
      ];
    });
  }

  switch (modeIndex) {
    case MODE_RANDOM:
      handleRandomMode(promptText, batchCount, cfg);
      break;
    case MODE_SEQUENTIAL:
      handleSequentialMode(promptText, batchCount, cfg);
      break;
    case MODE_CARTESIAN:
      handleCartesianMode(promptText, batchCount, cfg);
      break;
    case MODE_TEST:
      handleTestMode(cfg);
      break;
    default:
      handleRandomMode(promptText, batchCount, cfg);
  }

  requestFromUser('Done', 'OK', function() {
    return [
      this.section('', '', [
        this.plainText(
          modeIndex === MODE_TEST
            ? 'Test executed.'
            : `Generated ${batchCount} prompts.`
        )
      ])
    ];
  });
}

main();