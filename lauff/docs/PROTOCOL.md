# Relay protocol v1

One relay deployment serves one garden and one active worker. Worker operations use HTTPS POST JSON to the deployed `/exec` URL. Game operations use HTTPS GET with a percent-encoded JSON `q` parameter and a changing `n` parameter to avoid cached poll replies. Authentication is a `token` inside that JSON payload. GET is restricted to probe/start/observe/poll/ack/cancel; worker operations are POST-only. Game tokens therefore appear in request URLs and may be retained in infrastructure logs; never print full URLs, credentials, or raw network exceptions. The client limits URLs to 8,000 characters and fails closed on non-ASCII JSON. Operations prefixed `worker_` require WORKER_TOKEN; game operations require GAME_TOKEN. No credentials appear in returned state.

| Operation | Fields beyond token/op | Response |
|---|---|---|
| `probe` | none | `PONG\|1` without changing state |
| `start` | none | `SESSION\|<UUID>`; invalidates previous session |
| `observe` | session, observation | `PENDING`; retries cannot extend expiry |
| `poll` | session, seq | `PENDING` or command text |
| `ack` | session, seq, outcome | `OK`; saves last game outcome and clears pending |
| `cancel` | session | `OK`; discards pending observation and result |
| `worker_poll` | none | JSON containing session, pending observation, and last ack |
| `worker_result` | session, seq, action | `OK` if still valid |

Game command format:

```text
C|session|sequence|expectedX|expectedZ|remainingMilliseconds|HARVEST
C|session|sequence|expectedX|expectedZ|remainingMilliseconds|WAIT
```

An observation is a JSON object with `v:1`, `session`, integer `seq`, integer `x/z`, boolean `can_harvest`, numeric `fruit_count/fruit_capacity`, `previous_outcome`, and exactly five `tiles` in current/N/E/S/W order. Each tile contains integer `x/z`, boolean `known`, string `plant`, boolean `has_fruit`, and numeric `fruit_percent` (raw value, -1 if unavailable). Unknown and empty tiles are distinct. Neuron IDs are never sent to Lau.

Relay state holds only the latest observation, command, and acknowledgement. The cache entry is kept for 300 seconds, but the original observation expires after 45 seconds; polling never extends the observation deadline. Cache eviction requires a fresh session. There is no queue of past actions to replay.

A request with the same sequence and identical observation is idempotent. Altered content under that sequence is rejected. New observations cannot replace an unexpired outstanding one without cancellation. An identical worker result can be retried, but a conflicting action is rejected. Commands are repeatable reads until acknowledged; the game records the sequence as handled before executing and never executes it twice.

The game also checks local observation age, response round-trip duration, exact identity/position, manual movement and pause flags, capacity, and current harvestability. Server time is not compared with the Mac's wall clock; expiry is authoritative at the relay and conservative local timing guards delivery. A completed harvest is never retried after an uncertain acknowledgement.

Outcomes: `HARVEST_CONFIRMED`, `HARVEST_UNCONFIRMED`, `WAIT`, `REJECTED`, `PAUSED`, `MOVED`, `CAPACITY`, `ERROR`; `NONE` is allowed only as an initial previous outcome. Manual movement and capacity pauses also appear in subsequent observations.

Apps Script must return promptly. It never runs neural computation or waits for the Mac. The Mac and game each space request starts by at least three seconds. The worker computes each pending observation once per process and retries only its cached result; a worker restart can recompute a still-pending observation, but the relay prevents conflicting replacement and the game prevents duplicate execution.

## Evidence

`outputs/calibration.json` records the upstream revision, full pack manifest digest, selected neuron IDs as strings, constants, package versions, training and held-out seeds, input hashes, firing rates, time and memory. Partial calibration evidence has `passed:false`; live control requires verified complete evidence for the exact model fingerprint.

`outputs/live/events.jsonl` records worker startup/provenance, neural decisions, relay errors, and observed game acknowledgements. Logs are append-only. The relay retains only the last acknowledgement: this is a single-consumer experiment, not a durable distributed event stream. A disconnected worker may miss an outcome; absence of an acknowledgement must never be interpreted as success.


## Optional autonomous movement

Observation `autonomous` is a boolean; omitted means false for older clients. Commands additionally support MOVE_NORTH, MOVE_EAST, MOVE_SOUTH, MOVE_WEST. Expected x/z remain the source position; the destination is exactly one adjacent tile in that direction. The relay rejects movement unless autonomous=true, current can_harvest=false, capacity is available, and the corresponding destination tile is known. The game independently rechecks mode, bounds, sampled destination knowledge, current position, capacity, harvestability, queued overrides, and lifetime. It reports MOVED only after verifying exact destination coordinates, otherwise MOVE_UNCONFIRMED and pauses. Duplicate observation IDs are never recomputed by a running worker. Manual and autonomous mode changes start fresh sessions through fly start and fly auto respectively.
