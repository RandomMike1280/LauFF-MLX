# LauFF

**A fruit-fly connectome simulation controlling a farming drone through Lau.**

LauFF connects a game's Lau scripts to a neural simulation running on an Apple
Silicon Mac. The drone observes its current tile and four neighbors. Artificial
taste and local food cues stimulate annotated fly neurons; neural responses
request harvesting or a single-tile movement. The game validates each request
before executing it.

The simulation uses the pinned
[drosophila-brain-mlx](https://github.com/Kisame76/drosophila-brain-mlx) engine and
[MaleCNS v1.0](https://male-cns.janelia.org/download/) connectome: **166,700 model
neurons and 24,469,412 directed connection edges**. This is a spiking model built
from measured fly wiring. Its sensory inputs and mapping to drone actions are
engineered interfaces, and every one-second trial resets neural state.

Experimental autonomous local foraging uses FC2 inputs and PFL3 activity to choose
cardinal movement. Sweet-taste inputs and MN9 activity control harvesting.
Calibration compares normal stimulation with zero-input and silenced controls;
live control requires passing held-out validation. Movement can produce `WAIT`
when the neural response is weak or ambiguous. There is no learned navigation,
route planner, or claim that this reproduces a complete living fly's behavior.

## How it fits together

```text
Game / Lau client                 Google Apps Script               Mac
local garden observations ──GET──▶ authenticated mailbox ◀──POST── neural worker
validated drone actions   ◀────── short expiring commands           │
                                                                  ▼
                                                       localhost brain viewer
```

The viewer shows local observations, neural requests, confirmed game outcomes,
and measured brain activity. Active spatial regions glow automatically; inactive
cells stay dim. It updates from completed one-second trials and fades stale
activity. It does not invent spikes between trials.

The current scope is movement and harvesting. Planting, trading, and other garden
operations are not implemented.

## Requirements

- An **Apple Silicon Mac with Metal**. The tested machine is an M1 Pro with 16 GB
  unified memory; performance will vary on other Macs.
- **Python 3.12** (the tested environment), Git, and several GB of free disk space.
  The MaleCNS source-table download is approximately 1.1 GB.
- Access to the game and its Lau editor with the documented drone, garden, player,
  and HTTP APIs.
- A Google account that can deploy an Apps Script web app accessible to anyone.
  The relay authenticates requests with separate game and worker tokens.

Run all terminal commands below from the project root. The supplied
[lau_language_guide.md](lau_language_guide.md) and [report.pdf](report.pdf) describe
Lau and version-specific game behavior. Real in-game probes are the final check.
The optional desktop Lau interpreter is a syntax/testing aid; it does not provide
the game's drone APIs. Its original introductory text is preserved in
[docs/LAU_DESKTOP_REFERENCE.md](docs/LAU_DESKTOP_REFERENCE.md).

## Install the local simulation

Download or clone this project, open a terminal in its folder, then run:

```sh
LAUFF_PYTHON=python3.12 bash scripts/setup.sh
```

The script creates `.venv`, installs the locked Python dependencies and editable
packages, checks Metal, downloads the simulator at the commit recorded in
`upstream.lock.json`, fetches the data, compiles and verifies the pack, and
calibrates the feeding circuit. It does not deploy a relay or run the game.

Calibrate the movement interface separately:

```sh
.venv/bin/python scripts/calibrate_navigation.py
```

Passing reports are written to `outputs/calibration.json` and
`outputs/navigation/calibration.json`. Keep these locally: the worker checks that
calibration belongs to its exact model. A fresh checkout must generate its own
reports. If calibration fails, inspect the evidence before enabling live control.

The activity layout is included with the project. To regenerate it from the
pinned annotations after installing the data:

```sh
.venv/bin/python scripts/build_brain_visual.py
```

On an already configured installation, keep the existing environment, data, and
calibration reports; use the run command below directly.

## Deploy and configure the relay

1. Create a project at [Google Apps Script](https://script.google.com/), paste
   [relay/Code.gs](relay/Code.gs) into `Code.gs`, and save.
2. Deploy it as a **Web app**, executing as **Me**, with access set to **Anyone**.
   Complete the owner's Google authorization and copy the URL ending in `/exec`.
3. Generate the local configuration and credentials:

   ```sh
   .venv/bin/lauff configure \
     --relay-url 'https://script.google.com/macros/s/YOUR_DEPLOYMENT/exec' \
     --unbounded
   ```

4. Open `.local/relay-properties.json` privately. In the Apps Script project's
   **Script Properties**, set `GAME_TOKEN` and `WORKER_TOKEN` to those values.
5. Copy `.local/LauFFConfig.laum` into the game's module editor as
   **LauFFConfig.laum**. Use the generated file; the example contains placeholders.

`--unbounded` removes our artificial garden rectangle. Game access restrictions
and unknown-tile checks still apply; transport coordinates retain the existing
±10,000 validation limit. To restrict movement to a rectangle instead, replace
`--unbounded` with `--bounds MIN_X MAX_X MIN_Z MAX_Z`.

Configuration starts unverified. Run the separate probes described in
[docs/SETUP.md](docs/SETUP.md): tile fields and growth scale, all four directions,
empty tiles, synchronous harvesting, and authenticated HTTP GET with redirects.
Stop the probe scripts when done. Only after those checks pass, rerun:

```sh
.venv/bin/lauff configure \
  --relay-url 'https://script.google.com/macros/s/YOUR_DEPLOYMENT/exec' \
  --unbounded --capabilities-verified
```

Replace the in-game configuration module with the newly generated version.
Reconfiguration preserves existing tokens. For relay code updates, use
**Deploy → Manage deployments → Edit → New version → Deploy**; saving the editor
alone does not update the deployed `/exec` endpoint.

## Install the five game files

The live installation is exactly **five files**, each strictly **under 5,000
bytes**:

| In-game filename | Local source |
| --- | --- |
| `client.lau` | `game/client.lau` |
| `LauFFNet.laum` | `game/LauFFNet.laum` |
| `LauFFGarden.laum` | `game/LauFFGarden.laum` |
| `LauFFActions.laum` | `game/LauFFActions.laum` |
| `LauFFConfig.laum` | `.local/LauFFConfig.laum` |

Run only `client.lau`. Modules are imported by the client. Remove standalone
probes and obsolete modules from the live in-game installation to stay within
its five-file limit. Probes can be kept locally and installed separately when
needed. Preserve multiline conditionals: the game rejects several compact forms
that the desktop Lau interpreter accepts. Runtime messages use `print` so they
remain readable in the game terminal.

## Run and stop

Start the Mac worker and local viewer together:

```sh
.venv/bin/lauff run --autonomous --output outputs/autonomous
```

Open **[http://127.0.0.1:8765/](http://127.0.0.1:8765/)**. Start `client.lau` in the
game, then send one of these chat commands:

| Command | Behavior |
| --- | --- |
| `fly auto` | Fresh session with neural movement and harvesting |
| `fly start` | Fresh session with manual movement and neural harvesting |
| `fly north`, `fly east`, `fly south`, `fly west` | Queue one manual step and switch out of autonomous mode |
| `fly pause` | Pause drone actions |

To stop, send **`fly pause`** in the game, then press **Ctrl-C** in the worker's
terminal. That stops both the brain worker and web server. A disconnection or
expired command also pauses the game client. Run only one worker and one client
against a relay at a time.

For manual movement with neural harvesting only, use `.venv/bin/lauff run`.
For a viewer without neural computation or a relay connection, use
`.venv/bin/lauff view`.

For the live circuit-silencing control, stop the normal worker, run:

```sh
.venv/bin/lauff run --autonomous --silenced --output outputs/autonomous-silenced
```

Then send `fly auto` for a fresh session. The intervention blocks outgoing
transmission from the stimulated sensory populations in their respective trials.
Compare neural requests and actual game outcomes with the normal condition.

## Troubleshooting and evidence

- **HTTP timeouts:** the game's HTTP limit remains about five seconds. The client
  logs operation, elapsed time, request size, and observation age. An observation
  upload timeout triggers a small receipt-check poll. Keep the two-attempt limit;
  extra retries cannot extend the 45-second lifetime. After a pause, use `fly auto`
  or `fly start` to create a fresh session.
- **`ERROR|AUTH`:** check that Script Properties, the local config, and the
  in-game module use the matching tokens.
- **`ERROR|SESSION` / expired command:** check the active deployment, network
  timing, and whether another client started a session; restart a fresh session.
- **No movement or a dim brain:** inspect `WAIT`, unknown tiles, capacity, and the
  age of the last neural trial. The visualization waits for measured activity.
- **Calibration mismatch:** use the pinned code/data and regenerate the matching
  calibration; do not bypass the validation gate.

Evidence is saved in the selected output folder's `events.jsonl`. The dashboard
separates a neural request from the game acknowledgement. `HARVEST_CONFIRMED`
means the ripe-state changed at the expected position; inventory item-type counts
are not interpreted as the number of fruits collected.

See [validation evidence](docs/VALIDATION.md),
[neural navigation](docs/NEURAL_NAVIGATION.md), and
[bridge protocol](docs/PROTOCOL.md) for details and experimental limits.

## Credentials and version control

`.gitignore` excludes `.local/`, **`LauFFConfig.laum` in any directory**, its backup
copies, relay credential-property files, `.env` files, outputs, downloaded data,
the virtual environment, and build/cache files. The placeholder
`game/LauFFConfig.example.laum` remains available to commit.

Never paste generated tokens or authenticated query URLs into issues or shared
screenshots. Ignore rules do not remove secrets that were already committed;
remove such files from tracking and rotate exposed tokens before sharing a repo.

## Development and attribution

```sh
.venv/bin/python -m pytest tests -q
node tests/relay.test.cjs
```

Node is needed for relay tests. Lau execution tests additionally require the
optional desktop `lau` command; they skip when it is unavailable. In-game probes
remain necessary even when local tests pass.

- [MaleCNS release](https://male-cns.janelia.org/download/): dataset attribution
  and CC BY 4.0 terms; credit the MaleCNS collaboration and FlyEM at HHMI Janelia
  and its collaborators.
- [drosophila-brain-mlx](https://github.com/Kisame76/drosophila-brain-mlx): upstream
  MIT-licensed simulation engine, pinned in `upstream.lock.json`.
- [Shiu et al., Nature (2024)](https://doi.org/10.1038/s41586-024-07763-9):
  computational feeding-circuit foundation.
- [FC2/PFL3 research](https://www.nature.com/articles/s41586-023-07006-3):
  navigation-circuit research informing the experimental interface.
