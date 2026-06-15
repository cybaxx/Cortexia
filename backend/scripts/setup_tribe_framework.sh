#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$BACKEND_DIR/.venv"
DATA_DIR="${TRIBE_DATA_DIR:-$BACKEND_DIR/tribe_data}"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating backend virtualenv at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r "$BACKEND_DIR/requirements.txt"

PYTHON_VERSION="$("$VENV_DIR/bin/python" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"

if [[ "$PYTHON_VERSION" != "3.11" && "$PYTHON_VERSION" != "3.12" ]]; then
  echo "ERROR: TRIBE framework setup requires Python 3.11 or 3.12. Current venv is $PYTHON_VERSION." >&2
  exit 1
fi

# Install a constrained set first to avoid pip backtracking across the whole TRIBE stack.
python -m pip install \
  "numpy==2.2.6" \
  "pandas==2.2.3" \
  "scipy==1.15.3" \
  "torch==2.6.0" \
  "torchvision==0.21.0" \
  "transformers==4.46.1" \
  "tokenizers==0.20.3" \
  "huggingface_hub==0.26.2" \
  "nibabel==5.3.2" \
  "nilearn==0.10.4" \
  "nimare==0.5.5" \
  "nltools==0.5.1" \
  "whisperx==3.8.5" \
  "edge-tts==7.2.8" \
  "matplotlib==3.10.0" \
  "pyarrow==18.1.0" \
  "mne==1.10.1" \
  "mne_bids==0.16.0" \
  "pyprep==0.5.0" \
  "torchmetrics==1.6.1" \
  "x_transformers==1.27.20" \
  "moviepy==2.1.2" \
  "gtts==2.5.4" \
  "spacy==3.8.2" \
  "soundfile==0.12.1" \
  "Levenshtein==0.26.1" \
  "julius==0.2.7" \
  "einops==0.8.0"

# Then install tribev2 itself without re-solving all transitive dependencies.
python -m pip install --no-deps "git+https://github.com/facebookresearch/tribev2.git"

mkdir -p "$DATA_DIR"

cat <<EOF

TRIBE framework dependencies installed.

Device auto-detected at runtime (cuda > mps > cpu).
On Apple Silicon Macs, MPS GPU acceleration is used automatically.

Next steps:
1. Export your Hugging Face token:
   export HF_TOKEN=hf_your_token_here
2. Optionally set:
   export TRIBE_DATA_DIR=$DATA_DIR
3. Start Cortexia backend and run:
   $BACKEND_DIR/scripts/run_case.sh $BACKEND_DIR/examples/political_case.json

EOF
