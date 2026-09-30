# Setup and first live experiment

## 1. Local model

The implementation was prepared on an M1 Pro with 16 GB RAM and Metal. Use Python 3.12 or 3.13 for the pinned environment. The data download is about 1.1 GB; allow several GB of disk for packages and compiled arrays. In a regular terminal from this folder:

```sh
LAUFF_PYTHON=python3.12 bash scripts/setup.sh
```

If Python 3.12 has another path, set `LAUFF_PYTHON` to that path. Setup installs only inside `.venv`, checks Metal, downloads the pinned source/data, compiles and verifies the pack, then runs calibration. Keep the Mac awake. GPU calls from a restricted sandbox may require permission or a regular terminal. If calibration fails, inspect its saved evidence; do not bypass it.

On this workspace the environment and downloads may already be present. Consult `docs/VALIDATION.md`; do not repeat completed downloads unnecessarily.

## 2. Deploy the relay in your Google account

1. Open https://script.google.com and create a new project named **LauFF relay**.
2. Replace `Code.gs` with this project's `relay/Code.gs`. No spreadsheet is needed.
3. Choose **Deploy → New deployment → Web app**. Execute as **Me**, access **Anyone** (the app authenticates requests with separate long random tokens). Complete Google's owner authorization if prompted. Copy the URL ending `/exec`, not the editor URL or `/dev` test URL. If account policy prevents anonymous web apps, this relay path is unavailable; do not mark the probe passed.
4. Generate credentials and an initial, unverified module locally. Supply a conservative rectangle of owned tiles around your starting location:

```sh
.venv/bin/lauff configure \
  --relay-url 'https://script.google.com/macros/s/YOUR_DEPLOYMENT/exec' \
  --bounds -1 1 -1 1
```

5. Open `.local/relay-properties.json` locally. In Apps Script **Project Settings → Script Properties**, add `GAME_TOKEN` and `WORKER_TOKEN` with their respective generated values. Keep these out of shared screenshots and chat. Tokens are generated once and preserved on reconfiguration.
6. Put `.local/LauFFConfig.laum` into the game's module editor under the exact name `LauFFConfig.laum`.

The relay uses only Script Cache for short-lived mailbox state, Script Properties for credentials, and a script lock for updates. It does not call your Mac. The game makes outbound HTTPS GET requests with authenticated JSON query payloads; the Mac worker uses POST. Game-token URLs may be retained in infrastructure logs, so keep them private. Google redirects replies from `script.google.com` to `script.googleusercontent.com`; the game must support this. A successful local HTTP request alone does not establish game compatibility.

## 3. Probe the real game

Run `game/probe.lau` by itself. Record its output. Confirm:

- Position and the owned bounds you entered are correct; do not assume every plot is a square.
- Current and neighbor tile reads return the documented fields. Test an empty tile and an unripe and ripe fruit-bearing tile. Record whether fruit percentages span 0–1 or 0–100; the client preserves raw values and never infers harvestability from them.
- Run `game/probe_http.lau` separately: authenticated GET returns `PONG|1` in less than the game's five-second timeout; text parsing returns `C`, `2`, and `123`.
- From an interior owned tile, explicitly send `probe north`, `probe east`, `probe south`, `probe west`. Check that North decreases Z, East increases X, South increases Z and West decreases X. Each command moves one tile and prints before/after state. Avoid sending these at a boundary.
- On a ripe tree, `probe harvest` explicitly harvests once. Confirm command completion and the subsequent `canHarvest()` result. This probe action is manual and is not neural evidence.
- The reported inventory count and capacity are meaningful in your game version.

If any assumption fails, preserve the output and adapt the client before enabling it. Stop the probe before starting the main client. Re-run configure with the same URL, verified bounds, and `--capabilities-verified`; then replace the game module with the updated `.local/LauFFConfig.laum`. No token rotation occurs.

## 4. Run the experiment

```sh
.venv/bin/lauff run
```

Open http://127.0.0.1:8765. Create these auxiliary modules in the game using their exact filenames and the corresponding files from `game/`:

- `LauFFNet.laum` — authenticated GET and shared failure handling.
- `LauFFGarden.laum` — local tile observations, optional bounds, and chat callbacks.
- `LauFFActions.laum` — command validation and synchronous movement/harvesting.

Keep the generated `LauFFConfig.laum` module from `.local/`. The live installation is exactly five files including the main client and config; each must be strictly below 5,000 bytes. Remove the obsolete `LauFFInput.laum` and standalone probes from the in-game installation before adding the live files. Keep probes locally for separate diagnostic runs. Replace the main script with `game/client.lau`; run only this main script, not the modules. No relay redeployment is needed for this split.

Run `game/client.lau`. It starts paused. Send `fly start`, then single-step with `fly north/east/south/west`. Movement is manual; ripe fruit under the drone stimulates the neural feeding circuit. The viewer separates the neural request from the subsequent game-reported result.

Use `fly pause` to stop issuing actions. Pause before stopping the worker. To run the silencing control, stop the normal worker and start:

```sh
.venv/bin/lauff run --silenced --output outputs/silenced
```

Send `fly start` again for a new session. On a comparable ripe tile, MN9 should remain below the calibrated threshold and the response should be `WAIT`. Record both sessions. Do not run two workers against one relay; a deployment represents one garden and one active worker.

## Troubleshooting

- `ERROR|AUTH`: mismatched Script Properties and local/game credentials.
- `ERROR|SESSION`: the cache expired/was evicted or another client started; use `fly start`.
- `ERROR|EXPIRED` / worker deadline: inspect simulation and network timing; the system has not harvested on a late command.
- HTML instead of `PONG|1`: wrong deployment URL or access setting, a login page, or blocked redirects.
- Unknown local tiles: inspect the probe output; neighbor API errors are displayed as unknown, never fabricated as empty food-free space.
- Calibration mismatch: the pack, engine, neuron selection or parameters changed. Reverify and recalibrate.

No live game or Google deployment is created by running the unit tests or opening the viewer.

### Upgrade the existing deployment for game GET support

Real-game testing found GET succeeds (~1.50 seconds), `http.post` fails with HTTP 405, and explicit JSON POST times out (~5.33 seconds). The v2 relay therefore supports authenticated game GET while keeping worker POST and all mailbox checks intact.

1. Replace the Apps Script editor's `Code.gs` with `relay/Code.gs` from this folder and save.
2. Choose **Deploy → Manage deployments → Edit (pencil) → Version: New version → Deploy** for the existing web app. Saving the editor alone does not update `/exec`.
3. Keep the same deployment URL and both Script Properties. No configuration module changes are needed.
4. Run the updated `game/probe_http.lau` by itself in the game. Expected: `Authenticated GET PONG|1 elapsed ...` within five seconds. Send the printed result, without sharing the token or URL query.
5. Use the updated `game/client.lau` only after remaining capability checks pass. The local capability flag remains false.

The encoding probe includes spaces and reserved URL punctuation. Its encoder is regression-tested against Python's percent encoder across printable ASCII. This still requires real-game verification; the desktop Lau interpreter is only a preliminary check. Original POST failure semantics are not assumed to be fully diagnosed by the timeout.

### In-game parser constraint

Keep `then`, each statement, and `end` on separate lines. The real game rejects compact branches such as `if condition then fail(message) return end`, even though the desktop syntax checker accepts them. All shipped game files use multiline conditionals. Do not compress them to meet the size limit; split modules instead.


## Enable experimental neural movement

The worker requires a passing `outputs/navigation/calibration.json` for the exact FC2/PFL3 interface. It is already calibrated on this Mac; see NEURAL_NAVIGATION.md for evidence and limits.

1. Stop the in-game script.
2. Replace Apps Script `Code.gs` with `relay/Code.gs`, then **Deploy → Manage deployments → Edit → New version → Deploy**. Keep the existing URL and Script Properties. Version 3 adds authenticated movement commands; merely saving the editor does not update `/exec`.
3. Replace `client.lau`, `LauFFGarden.laum`, and `LauFFActions.laum` in-game. Keep `LauFFNet.laum` and the current `LauFFConfig.laum`. Exactly five files remain.
4. Start the Mac worker with `.venv/bin/lauff run --autonomous --output outputs/autonomous` if not already running. Never run a second worker on the same relay.
5. Run the main client, then send `fly auto`. The worker independently runs neural trials and issues validated moves or harvests.

`fly pause` stops activity. `fly start` starts a fresh session with manual movement and neural harvesting. A manual direction command also turns autonomous mode off. Autonomous moves require matching source coordinates/session/sequence and a known adjacent destination within the configured rectangle (when enabled); game-reported outcomes distinguish confirmed movement from MOVE_UNCONFIRMED, which pauses the client.

The dashboard shows whether the game requested autonomous mode, four PFL3 response rates, the requested action, and the last game acknowledgement. Updated PFL3 and descending-neuron activity is also visible in the brain view when navigation trials arrive. No movement means the circuit may be producing WAIT; inspect the telemetry instead of bypassing its gate.

### Remove the artificial movement boundary

Run `lauff configure` with the same `--relay-url`, `--unbounded`, and
`--capabilities-verified` after successful probes. This preserves credentials.
Replace **LauFFConfig.laum** with `.local/LauFFConfig.laum` and **LauFFGarden.laum**
with `game/LauFFGarden.laum`, restart the client, then send `fly auto`. No relay
redeployment or worker restart is needed. These remain part of the same five files.

Config slot 8 enables unbounded mode when true; false or missing retains the
rectangle in slots 4–7. Both observations and movement checks use this setting,
so neighbors beyond the old rectangle now reach the neural simulation.
The game still controls accessible land. Unknown tile responses remain excluded
from autonomous movement; position, capacity, and command-expiry checks remain.
Transport coordinates still have the existing ±10,000 numeric validation limit.
Use `--bounds MIN_X MAX_X MIN_Z MAX_Z` to restore a rectangle.

### Intermittent game HTTP failures

The client logs the operation, attempt number, elapsed HTTP time, and a redacted
error category in the terminal. A failed GET gets one retry after at least three
seconds, with no drone action during recovery. After an observation upload times
out, the second request is a small poll for that same session and sequence,
not another upload. This can recover a lost response when the relay already
received the observation. If it never arrived, the relay rejects the poll and
the client pauses. A ready command goes through the normal position, capacity,
and lifetime checks. Acknowledgements retry only the acknowledgement,
never the drone action. Pause/restart events cancel the old request's result, and
expired observations cannot be retried into a new lifetime. Relay errors are not
retried. Two network failures pause the client; use `fly auto` (autonomous) or
`fly start` (manual) for a fresh session. A transport failure no longer also prints
“observation rejected.” The game HTTP timeout itself is unchanged.

Request byte count, preparation time (including rate-limit waiting), and observation
age are logged after an upload failure. Keep the shipped two-attempt limit: more
retries cannot extend the 45-second observation lifetime. These changes need only
the updated `client.lau` and `LauFFNet.laum`; no relay redeployment is required.
