# LauFF-MLX

A fruit-fly connectome simulation controlling a farming drone through **Lau**.

This fork combines the original MLX neural engine with **LauFF**, an experimental
bridge between a game's garden observations and a MaleCNS connectome simulation
running on an Apple Silicon Mac. Neural activity requests single-tile movement
and fruit harvesting; the game validates those requests before executing them.
A local viewer shows measured activity lighting up the brain's spatial regions.

## Get started

The complete introduction, requirements, relay deployment, game installation,
commands, and credential handling are in **[lauff/README.md](lauff/README.md)**.

```sh
git clone https://github.com/RandomMike1280/LauFF-MLX.git
cd LauFF-MLX/lauff
LAUFF_PYTHON=python3.12 bash scripts/setup.sh
.venv/bin/python scripts/calibrate_navigation.py
```

Then deploy the Google Apps Script relay, generate private credentials, and
verify the in-game probes as described in the guide. Once configured:

```sh
.venv/bin/lauff run --autonomous --output outputs/autonomous
```

Open [the local viewer](http://127.0.0.1:8765/), run the five-file Lau client in the
game, and send `fly auto`. To stop, send `fly pause` and press Ctrl-C in the Mac
worker terminal.

## Repository layout

- **`lauff/`** — game scripts, authenticated Apps Script relay, Mac worker, live
  activity viewer, calibration, tests, and LauFF documentation.
- **`src/lif/`, `tools/`, `bench/`, `tests/`, `docs/`** — original neural engine
  and its research/development tooling, preserved from the upstream repository.
- **[README-engine.md](README-engine.md)** — original engine introduction and
  usage instructions.
- **[ATTRIBUTION.md](ATTRIBUTION.md)** and **[LICENSE](LICENSE)** — upstream
  attribution and code license. MaleCNS data retains its CC BY 4.0 terms.

LauFF uses the pinned upstream revision recorded in `lauff/upstream.lock.json`.
Its isolated environment installs the engine from that pinned checkout under
`lauff/vendor/`, so app installation and calibration do not modify the retained
engine source in this fork.

This is a simplified spiking model derived from measured fly wiring. Artificial
food inputs, direction conventions, and action decoding are engineered
interfaces. Each trial resets neural state; the project does not demonstrate
learning or complete natural fly behavior. See the app's validation notes for
the evidence and limitations.

Local credentials, generated **`LauFFConfig.laum`** modules, virtual environments,
downloaded data, and experimental outputs are excluded from version control.
The placeholder example module remains in the source tree.
