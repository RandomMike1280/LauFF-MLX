#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo 'The selected neural backend requires Apple Silicon macOS.' >&2; exit 1
fi
LAUFF_PYTHON="${LAUFF_PYTHON:-python3}"
"$LAUFF_PYTHON" -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
sysctl -n hw.memsize
df -h .
if [ ! -d vendor/drosophila-brain-mlx/.git ]; then
  git clone https://github.com/Kisame76/drosophila-brain-mlx.git vendor/drosophila-brain-mlx
fi
PIN=e417b33616513ef350b1b1c3cdf2b5b7a1799c8e
git -C vendor/drosophila-brain-mlx checkout --detach "$PIN"
"$LAUFF_PYTHON" -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install -e vendor/drosophila-brain-mlx -e .
.venv/bin/python -c 'import mlx.core as mx; print(mx.device_info())'
bash vendor/drosophila-brain-mlx/tools/fetch_male_cns.sh
.venv/bin/python -m lif.compile_pack_malecns
.venv/bin/python -m lif.verify_pack --pack vendor/drosophila-brain-mlx/data/pack/male_cns_v1
.venv/bin/lauff calibrate
