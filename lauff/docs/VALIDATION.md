# Validation performed on September 29, 2026

Implementation, local neural validation, and authenticated in-game GET are verified. The Google relay is deployed. A live neural harvest demonstration is still pending; direction, owned-bound, and harvest-completion probes remain required. Historical results below record the progression of validation.

## This computer

- Apple M1 Pro, 14 GPU cores, Metal available, 16 GB unified memory.
- Isolated Python 3.12.14 environment in `.venv`; exact installed dependencies in `requirements.lock.txt`.
- Upstream revision `e417b33616513ef350b1b1c3cdf2b5b7a1799c8e`.
- Metal was inaccessible inside the execution sandbox and worked through approved unsandboxed local execution. No system security settings were changed.

## Data and numerical checks

Downloaded all three MaleCNS source tables. The compiler's checks and the independent pack verifier passed for **166,700 neurons and 24,469,412 directed edges**. An edge aggregates synaptic contacts; these counts must not be called 24 million individual synapses.

The optimized fused engine was compared against the independent naive engine on the full retained graph for 100 ms of simulated time, using matched sweet-input draws and seed 77. Normal and outgoing-sweet-synapse-silenced cases both matched exactly for spike counts, final membrane voltage and final conductance. Normal case: 1,391 total spikes; silenced case: 172 input-cell spikes with transmission blocked. Those spike totals are for the numerical test, not the one-second calibration.

Evidence:

- `outputs/compile-pack.log`
- `outputs/verify-pack.log`
- `outputs/engine-parity.json` and `outputs/engine-parity.log`
- `outputs/upstream-tests.log`: selected upstream compiler/annotation/stimulus/verifier tests passed; one data-dependent annotation test initially skipped before the pack existed.
- `outputs/annotation-tests.log`: all 7 annotation tests then passed with the compiled pack.

## Feeding-circuit calibration

60 independent, one-second trials: 10 per condition in training and 10 per condition in a disjoint held-out set. The 17 annotated right-labellum sweet neurons were driven at 100 Hz in the sweet conditions. Score: larger of the left/right MN9 population mean rates.

| Condition | Training MN9 score | Held-out MN9 score |
|---|---:|---:|
| Zero input | 0 Hz | 0 Hz |
| Sweet input | 38–67 Hz | 42–77 Hz |
| Sweet input, outgoing sensory synapses silenced | 0 Hz | 0 Hz |

The training-derived threshold is **19 Hz**. All 30 held-out classifications passed without adjusting the threshold. This verifies the specified computational circuit response under these conditions, not biological realism or autonomous farming ability.

Median held-out sweet trial elapsed time was **0.695 seconds per simulated second** on this Mac, including adapter work. Zero-input and silenced medians were about 0.63 seconds. Maximum reported MLX peak allocation was approximately 437 MB; this is not a measurement of total process/system RAM. Game statement billing and relay latency are additional and remain unmeasured.

Model fingerprint:

```text
118fb858a6d59102f344b6ce9607ca2a4415364ae0b1cd700d1ae9ff661a49e3
```

Detailed neuron IDs, package versions, parameters, seeds, input hashes and per-trial outcomes are recorded in `outputs/calibration.json`. `outputs/calibration.log` is the human-readable run log.

## Integration and user interface

- **11 local Python tests passed, with 19 subtests.** Includes actual desktop-Lau execution of the client command handler against game stubs, strict protocol validation, calibration rejection, credential configuration and worker retry/acknowledgement flow.
- JavaScript relay tests passed: normal lifecycle, authentication separation, duplicates, conflicting results, cancellation, expiry, old sessions and cache eviction.
- Both Lau scripts passed the installed desktop interpreter's syntax checker.
- Real-neural offline rehearsal passed using synthetic garden observations and seed 2,000,000: sweet → 55 Hz → `HARVEST`; zero input → 0 Hz → `WAIT`; silenced sweet input → 0 Hz → `WAIT`. **No real game actions occurred.** See `outputs/offline-rehearsal.json`.
- Local browser verification confirmed the viewer renders, polls state, displays the 19 Hz threshold and held-out calibration ranges, and labels itself as viewer-only without game observations or acknowledgements.

## Still required in the actual game

Follow `docs/SETUP.md`: deploy the relay, configure its two tokens, test redirect/timeout behavior, verify garden field shapes and coordinate directions, verify owned bounds and harvest completion, then enable the client. Compare a normal live harvest against the silenced condition. Do not treat the desktop replica, offline observations, or a successful browser preview as proof of those live checks.

## Relay deployment follow-up

The supplied deployment URL was configured locally. A GET reached the LauFF relay through the expected `script.googleusercontent.com` redirect in 1.783 seconds. An authenticated POST probe returned `ERROR|AUTH` in 1.438 seconds: generated local credentials still need to be installed as the deployment's Script Properties. These desktop timings do not verify in-game HTTP behavior. See `outputs/relay-check.json`. The generated Lau module remains disabled, with placeholder bounds of -1 to 1 on each axis pending the actual game probes.

After the user installed both Script Properties, authentication and the deployed relay lifecycle passed: `probe → PONG|1`, worker polling, new session, synthetic observation submission, worker `WAIT` result, game-side command polling, acknowledgement, and confirmed pending-state clearance. Nine requests took approximately 1.43–2.53 seconds each, including Google's redirect. No game actions were executed. Recorded evidence: `outputs/relay-auth-check.json`. Actual game HTTP behavior and garden probes remain unverified; the client remains disabled.

## Actual-game probe findings and correction

The user's first in-game probe reported position (0,0), land level 12, 13 fruit item types out of capacity 200, and current harvestability true. All five local plant calls succeeded. Unlike the flat structure initially assumed, each returned a coordinate-keyed wrapper such as `{["0,0"] = {PlantName="LemonTree", HasFruit=true, FruitPercent=100, ...}}`. The client now unwraps the exact requested coordinate, retains flat-response compatibility, and treats unrecognized structures as unknown. Six response-shape regression cases execute the actual Lau tile reader. Current suite: 12 tests and 25 subtests passed.

In-game `http.post` failed with HTTP 405 after about 1.78 seconds. The text primitives returned the expected C, 2 and 123. A desktop probe that deliberately preserved POST across redirects reproduced HTTP 405 at `script.googleusercontent.com`; this supports a redirect-method incompatibility hypothesis but does not establish the game's internal implementation. `game/probe_http.lau` now tests anonymous GET and authenticated explicit JSON POST through `http.request`, without moving the drone or changing relay state. Transport remains unverified in-game; capabilities remain disabled. Neither the owned bounds nor direction/harvest tests have been confirmed yet.


## Game transport follow-up: GET succeeds, explicit POST times out

User-reported public GET returned the old relay banner in 1.4999 seconds. Explicit JSON POST timed out after 5.3331 seconds. This establishes a working GET response path, not authenticated mailbox compatibility.

Implemented a game-only authenticated GET adapter with URL-encoded JSON and cache-busting nonce, retaining worker POST and the shared mailbox state machine. GET cannot submit worker results. The client avoids logging credential-bearing URLs or raw HTTP exceptions. Existing credentials and deployment URL are preserved; capability verification remains false.

Validation: 13 Python/Lau tests and 25 subtests passed; relay tests passed including game GET authentication, rejected worker operations, malformed/oversized requests, and a GET game → POST worker → GET command/ack cycle. All three Lau scripts pass desktop syntax checks. The shared client/probe encoder matches Python percent encoding for every printable ASCII character. Real deployment update and authenticated in-game GET are still pending. No neural harvest has occurred in-game.


## Authenticated in-game GET verified

The user ran the updated transport probe against the deployed v2 relay and reported `Authenticated GET PONG|1 elapsed 2.1496345410123467`. This verifies authenticated game GET through the redirect within the five-second HTTP limit. It is a single probe round trip, not end-to-end neural harvest latency or a sustained reliability measurement. No configuration or token changes are needed.

Next: run the capability probe at (0,0), one command at a time: north, south, east, west (returning to origin between axes), then a manual harvest on a ripe tile. Capture before/after coordinates, harvestability, and the post-action tile record. Keep the experiment restricted to the verified local region; land level alone does not establish full owned bounds. Empty-tile behavior still needs a real example.


## Direction and manual harvest verified in-game

User-reported movement: (0,0) → (0,-1) → (0,0) → (1,0) → (0,0), confirming North=-Z, South=+Z, East=+X, West=-X. A synchronous manual harvest at (0,0) returned at the same position with canHarvest=false. The tile retained LemonTree and HasFruit=false, omitting FruitPercent; the client correctly retains -1 (unknown) for the absent percentage. Added this exact post-harvest shape to the tile-reader regression. This manual harvest is not neural evidence.

The first live experiment is restricted to the two actually visited tiles (0,0) and (1,0), with bounds [0,1,0,0]. Capability enablement applies to that restricted experiment: full plot bounds, empty tiles, intermediate growth, and sustained network behavior remain unverified. Unknown tiles remain unknown and harvesting uses canHarvest, never growth percentages. The next demonstration must show normal neural HARVEST with a confirmed game outcome and the silenced circuit withholding harvest on ripe fruit.


## Game file-size limit and modular client

The user established that each game file must be below 5,000 bytes. Split the client using documented req imports and positional module exports. Factories receive the same mutable state and API references, so pause flags, sequence handling, and request spacing remain shared across modules.

Sizes: client.lau 4,581 bytes; LauFFNet.laum 2,598; LauFFGarden.laum 1,168; LauFFActions.laum 2,978. Config and both probes are also below the limit. All four client files pass desktop syntax checking. Regression tests now import the real auxiliary modules; 14 tests and 33 subtests pass, including a file-size guard. In-game module loading and the live neural demonstration remain to be verified.


## Real-game multiline conditional correction

Expanded every inline conditional in the client, auxiliary modules, and probes, with each assignment, call, return, and end on its own line. Moved chat callbacks into LauFFInput.laum to keep every game file below 5,000 bytes; client.lau is now 4,531 bytes. Updated tests load the revised modules and reject inline conditional bodies. All 15 tests pass, and all game files pass desktop syntax checks; the latter do not establish real-game parser compatibility.

## Five-file game limit

Merged chat callbacks into LauFFActions.laum and removed LauFFInput.laum. Live imports now total exactly five files: client (4,489 bytes), actions (3,938), network (2,662), garden (1,272), and private configuration (212). Multiline conditionals are preserved. Import-graph regression enforces the five-file limit alongside the existing per-file size checks. All 16 tests pass; all game files pass desktop syntax checks. Standalone probes remain local diagnostics and should not occupy live game file slots.


## Neural steering research gate

At the user's request, investigated neural movement rather than scripted navigation. Added a research-only PFL3→DNa02 adapter and offline validation script. The same verified full MaleCNS graph passed 100 independent one-second trials: 10 matched seeds × 5 conditions × training/held-out splits. Training-derived signed threshold: ±26.5 Hz. Held-out left input R−L: −80 to −57 Hz; right: +55 to +69 Hz; zero input and both outgoing-PFL3-silenced controls: 0 Hz. Median wall time 1.017 seconds per trial. Full IDs, parameters, hashes and seeds are in outputs/navigation/steering-validation.json.

This is direct stimulation of central neurons, not a validated food-to-navigation pathway. Autonomous movement remains disabled; no movement command was added to the relay or client. The full research scope, primary sources, and remaining gates are in docs/NEURAL_NAVIGATION.md. All 19 local tests pass, including steering gate failure controls and the five-file/size checks.


## Manual movement boundary correction

The two-tile demonstration configuration [0,1,0,0] caused north/south commands to be silently vetoed. At the user's request, expanded the local configured rectangle to [-1,1,-1,1] and added an explicit boundary alert. All four neighbors of (0,0) were observed in the earlier game probe; the four diagonal corner tiles have not yet been probed. This is a local 3×3 movement area, not a verified full-plot boundary. The user must replace the in-game configuration module and main client, then restart the script for the new bounds to apply. Neural autonomy is unaffected.

## Brain visualization

Added the dashboard's connectome explorer with a deterministic 6,000-point sample of real MaleCNS somaLocation coordinates (139,662 retained neurons have locations). Circuit views contain 62 annotated neurons and 637 actual directed signed-weight edges: 17 sweet inputs, 15 two-step feeding intermediates, two MN9 outputs, and 28 steering neurons. No coordinates are invented for cells with missing soma locations; circuit diagrams use explicitly schematic layouts.

Activity halos use existing per-trial feeding-population averages only; no individual spike timing or unmeasured intermediary activity is fabricated. Steering is explicitly topology-only. The builder is scripts/build_brain_visual.py and embeds a bounded export in the existing HTML, avoiding a live-worker restart. Verified anatomical rendering, both circuit tabs, and neuron inspection in the local browser; all 20 tests pass. JavaScript syntax checks pass. In-game files and relay are unaffected.


## Autonomous local foraging implementation

The experimental FC2→PFL3 cardinal interface passed 156 real MaleCNS trials (78 training, 78 held-out), with separate anatomical grouping and calibrated readout gains. It differs from the earlier DNa02 body-relative steering assay: the game uses discrete cardinal actuators, and all four artificial food cues are presented before a downstream neural response is decoded. See docs/NEURAL_NAVIGATION.md for the exact engineered mapping and its limitations.

Real-neural closed-loop simulation passed four directional move/harvest episodes and an eight-fruit 3×3 garden in 16 actions; the silenced controller stayed at WAIT. No live autonomous move has yet been verified. The relay/client movement path is implemented with bounds, mode, expiry, duplicate, position, capacity, and manual override checks. Exactly five game files remain below 5,000 bytes with multiline branches. Deployment update and replacement of three game files are required.

The autonomous-capable worker was started successfully with navigation_enabled=true and a passing navigation calibration, and confirmed waiting for game input with no connection error. Local validation includes 24 passing tests in the full suite plus the subsequently added passing autonomous-worker integration test (duplicate observations reuse one neural decision). The updated browser shows the FC2→PFL3 movement mode and awaits autonomous observations. No live autonomous move is claimed before the relay/game update.

## Measured activity visualization

The local viewer now receives actual full-model spike counts after each feeding
and navigation trial. All 166,700 neurons contribute to the active-cell count.
The 139,662 cells with annotated soma positions contribute to 48 spatial bins;
6,000 deterministic soma samples form the displayed outline. These bins describe
positions, not named neuropils, and no activity is inferred for missing coordinates.

Brightness scales with measured firing rate; each bin includes its inactive cells
when calculating mean rate and active fraction. Selected circuit cells now use
individual counts instead of a taste-population average. The viewer polls once
a second and smoothly transitions brightness. Trial activity begins fading after
20 seconds and reaches darkness after 45 seconds without a new measurement.
Disconnecting the viewer also dims activity. These are one-second trial snapshots,
not reconstructed individual spike times or a continuously running brain.

A real Metal sweet-input trial at seed 5,000,001 yielded 2,873 active model cells
and 44 nonzero spatial bins; a matched zero-input trial yielded zero active cells
and zero nonzero bins. Saved counts are in `outputs/visualization/sweet-trial.json`
and `zero-trial.json`. The model fingerprint, action decoder, and game files are
unchanged. Visualization telemetry is read-only.
