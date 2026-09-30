# Neural navigation research

Experimental autonomous local foraging is implemented behind a passing neural calibration gate and the in-game `fly auto` command. The user chose neural direction decisions, rather than a scripted garden route. The live installation remains five files, each below 5,000 bytes. Updating the deployed relay and in-game client is required before live movement can be demonstrated. The first sections below document the earlier DNa02 steering research; the implemented cardinal interface is described at the end.

## Circuit candidate

Westeinde et al. describe PFL3 populations driving left/right steering through descending neurons; their model reads steering as DNa02_R minus DNa02_L activity. It requires heading and goal representations. PFL2 modulates steering gain; it is not a validated forward-speed output for this project. [Primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10881397/). The [2025 correction](https://pmc.ncbi.nlm.nih.gov/articles/PMC11946882/) addresses fly genotypes and a figure label.

Our retained MaleCNS pack has 24 PFL3 cells, two DNa02 cells, and two DNa03 cells. PFL3 instance labels contain anatomical L/R and column identifiers; those L/R labels do **not** identify the side of motor output. The structural audit partitions cells by actual direct excitatory contacts onto DNa02: 12 project to each side. All selected cells have positive signed contact counts to one DNa02 side and zero direct contacts to the other. This grouping is fixed before functional trials. Ambiguous connectivity fails the assay instead of being assigned arbitrarily.

## Implemented experiment

`src/lauff/steering.py` uses the same verified full connectome, constants, and fused engine as the feeding experiment. It directly stimulates one PFL3 projection population at 100 Hz for one simulated second. DNa02 cells receive no direct artificial input. Five conditions use matched random seeds:

- Zero input.
- Left-projecting PFL3 stimulation.
- Right-projecting PFL3 stimulation.
- Left stimulation with outgoing transmission from both PFL3 populations blocked.
- Right stimulation with the same transmission block.

Ten seeds per condition train a signed-response threshold; ten different seeds per condition validate it, for 100 trials total. Right-minus-left DNa02 activity must be positive for right stimulation, negative for left stimulation, and below threshold in magnitude for every control. The threshold is fixed from training only. Every trial resets neural state. The output records IDs, model fingerprint, stimulus hash, parameters, seeds, readouts, and timings. Interrupted or failed runs never have a passing report.

Run from the project root on the Mac with Metal available:

```sh
.venv/bin/python scripts/validate_steering.py
```

Evidence: `outputs/navigation/steering-validation.json`, `steering-validation.log`, and `structural-audit.json`. This script makes no relay requests and issues no game commands. Unit tests exercise rejection of reversed responses, noncausal controls, and held-out failure; these tests are separate from the real neural trials.

## Results on this Mac

All 100 real-connectome trials completed; the held-out gate passed with a training-derived absolute threshold of 26.5 Hz.

| Condition | Training R−L (Hz) | Held-out R−L (Hz) |
|---|---:|---:|
| Zero input | 0 | 0 |
| Left PFL3 input | −70 to −54 | −80 to −57 |
| Right PFL3 input | +53 to +71 | +55 to +69 |
| Left input, transmission blocked | 0 | 0 |
| Right input, transmission blocked | 0 | 0 |

Median wall time was 1.017 seconds per one-second neural trial in this run. These are this Mac's measurements, excluding game and relay latency. No parameters were retuned after held-out evaluation. Passing this assay leaves `autonomous_navigation_enabled` false.

## What a pass establishes

A pass demonstrates causal, side-specific transmission from artificially stimulated PFL3 cells to the DNa02 readout **in this simplified model**. It does not establish that the brain can find garden food. Directly injecting a chosen turn into PFL3 would place that choice in our input encoder, so this assay must not be presented as autonomous decision-making.

## Required before autonomous movement

1. Define and test an artificial local-food input and heading representation upstream of the steering decision. Present all local cues; do not select a destination in code and then inject the desired turn. Verify anatomical column/heading mappings against the literature and dataset annotations.
2. Test cue rotations, equal cues, absent food, unknown tiles, and ambiguous goals across held-out seeds. Require corresponding neural-output changes and loss of the effect under relevant connection silencing. Inspect residual left/right bias.
3. Identify and validate a movement-initiation/forward component. A left/right signal alone cannot distinguish forward travel, stopping, and a turn-around. Do not treat silence as automatic permission to move forward.
4. Use a declared virtual body heading: the documented game API exposes cardinal tile moves and position, but no body-heading sensor. Update it only from confirmed moves. Validate the conversion from neural motor signals to cardinal steps offline before enabling it in-game.
5. Extend command handling with matched source position, bounded adjacent destination, expiry, duplicate rejection, pause override, and a confirmed movement outcome. Safety vetoes may reject movement but must not silently choose another direction. Preserve exactly five game files, each below 5,000 bytes, and multiline conditionals.
6. Demonstrate closed-loop normal movement versus silenced withholding of movement on the same observations, then validate interaction with the feeding circuit. Keep planting, trading, and other previously excluded actions out of scope.

The current configured movement area is X/Z = −1…1 (a local 3×3 area). Expanding exploration requires verified traversable bounds. Full plot dimensions are not inferred from land level 12.


## Implemented cardinal goal decoder (September 30)

The drone API supplies cardinal tile steps rather than body rotation. Instead of claiming a complete FC2/EPG/heading/DNa02 walking model, this version decodes the upstream PFL3 goal-related response directly into a cardinal request. It does not use the earlier DNa02 left/right threshold as a surrogate for forward motion. This is an explicitly engineered neural-to-actuator interface, not a claim of natural fly locomotion. [FC2/PFL3 research basis](https://www.nature.com/articles/s41586-023-07006-3).

All four observations are encoded simultaneously, with no preselected destination. The 92 FC2A/B/C neurons are assigned by annotated column to four artificial world-direction channels: C1–2 north, C3–4 east, C5–6 south, C7–9 west. The cardinal labels are arbitrary interface conventions, not innate fly directions. Each of 24 PFL3 readout neurons is assigned to the FC2 channel with the strongest direct summed signed contacts; this selection is fixed from anatomy before calibration.

Known neighboring tiles contribute a 0.2 tonic cue plus up to 0.8 from raw fruit growth normalized over 0–100 when fruit exists. Unknown/outside tiles contribute zero. These are artificial food cues, not biological smell or vision. All FC2 cells are listed as stimulus targets, including zero-rate channels, consistently across trials. Stimulus scale is 100 Hz and every trial resets for one simulated second.

Population mean PFL3 activity is normalized by training-only single-cue response gains. The uniquely strongest channel requests a step only above a calibrated activity threshold and fixed separation margin. Silence and ties produce WAIT. There is no nearest-food selector, path planner, raster route, or random-direction fallback. Boundary and unknown-tile checks can veto a request but never choose a replacement. Current harvestability takes precedence through the separately validated MN9 feeding experiment; two independent reset trials can occur in one observation.

Validation completed: 156 real-connectome trials, 78 training and 78 held-out. The 26 conditions per seed cover four single directions, ripe-food contrast against background, competing weaker cues, each direction with FC2 outgoing transmission blocked, all six equal-cue pairs, zero input, empty background, equal four-way cues, and silenced four-way input. All classifications passed. Each split has three matched seeds per condition and the splits are disjoint. The decoder gains are [77.1667, 60.3333, 59.0556, 61.1667] Hz, normalized threshold 0.0365746, and winner margin 0.03. Full precision and provenance are in outputs/navigation/calibration.json.

Closed-loop rehearsal used actual neural trials in a synthetic garden: four one-neighbor episodes each moved in the appropriate direction and harvested; an eight-fruit 3×3 garden was collected in 16 actions; a silenced run stayed at WAIT. This is offline evidence, not a live game result. See outputs/navigation/closed-loop.json and closed-loop.log.

Limitations: local observations only, no persistent neural memory or learning, possible directional bias under ambiguous input, and no guarantee of exploration when nearby food cues are absent or output is ambiguous. A WAIT is a legitimate neural result. Dataset weights are unchanged. This does not implement planting, buying, selling, or full-farm planning.

### Reproduce and run

```sh
.venv/bin/python scripts/calibrate_navigation.py
.venv/bin/python scripts/rehearse_navigation.py
.venv/bin/lauff run --autonomous --output outputs/autonomous
```

For a live silencing control, stop the normal worker and use `run --autonomous --silenced --output outputs/autonomous-silenced`; start a fresh game session using `fly auto`. Both FC2 and sweet-input outgoing connections are silenced in their respective trials.
