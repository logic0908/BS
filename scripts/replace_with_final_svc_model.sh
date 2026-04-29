#!/usr/bin/env bash
set -u

PROJECT_ROOT="/home/featurize/work/BS"
PRESET_ID="final_primary"
REPORT_DIR="$PROJECT_ROOT/runtime/model_search"
FINAL_REPORT="$REPORT_DIR/final_model_install_report.md"

mkdir -p "$REPORT_DIR"

cd "$PROJECT_ROOT" || exit 1

echo "[1/3] Searching public So-VITS-SVC candidate models..."
python scripts/find_sovits_candidate_models.py
SEARCH_RC=$?
if [[ $SEARCH_RC -ne 0 ]]; then
  echo "Model search did not find an accepted candidate." >&2
  exit $SEARCH_RC
fi

ACCEPTED_COUNT="$(python - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("runtime/model_search/candidates.json").read_text(encoding="utf-8"))
print(sum(1 for c in payload.get("candidates", []) if not c.get("rejection_reason")))
PY
)"

if [[ "$ACCEPTED_COUNT" == "0" ]]; then
  echo "No accepted candidates after filtering." >&2
  exit 1
fi

RANK=1
while [[ $RANK -le $ACCEPTED_COUNT ]]; do
  echo "[2/3] Installing candidate rank $RANK as $PRESET_ID..."
  python scripts/install_final_svc_model.py --preset-id "$PRESET_ID" --candidate-rank "$RANK"
  INSTALL_RC=$?
  if [[ $INSTALL_RC -ne 0 ]]; then
    echo "Install failed for candidate rank $RANK; trying next candidate." >&2
    RANK=$((RANK + 1))
    continue
  fi

  echo "[3/3] Running CUDA smoke test for $PRESET_ID..."
  bash scripts/smoke_test_final_svc_model.sh --preset-id "$PRESET_ID"
  SMOKE_RC=$?
  if [[ $SMOKE_RC -eq 0 ]]; then
    python - "$PRESET_ID" <<'PY'
import json
import sys
from pathlib import Path

preset_id = sys.argv[1]
path = Path("backend/app/config/svc_model_presets.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["active_preset_id"] = preset_id
payload.setdefault("fallback_preset_id", "tech_villager")
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
    python - "$FINAL_REPORT" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
candidates = json.loads(Path("runtime/model_search/candidates.json").read_text(encoding="utf-8"))
install = json.loads(Path("local_models/sovits-final/final_primary/install_report.json").read_text(encoding="utf-8"))
smoke = json.loads(Path("runtime/model_search/final_model_smoke_test.json").read_text(encoding="utf-8"))
presets = json.loads(Path("backend/app/config/svc_model_presets.json").read_text(encoding="utf-8"))
accepted = [c for c in candidates.get("candidates", []) if not c.get("rejection_reason")]
lines = [
    "# Final So-VITS-SVC Model Install Report",
    "",
    f"- active_preset_id: `{presets.get('active_preset_id')}`",
    f"- selected_repo: `{install.get('repo_id')}`",
    f"- model_path: `{install.get('model_path')}`",
    f"- config_path: `{install.get('config_path')}`",
    f"- speaker: `{install.get('speaker')}`",
    f"- speech_encoder: `{install.get('speech_encoder')}`",
    f"- sampling_rate: `{install.get('sampling_rate')}`",
    f"- license: `{install.get('license')}`",
    f"- smoke_success: `{smoke.get('success')}`",
    "",
    "## Accepted Candidates",
    "",
]
for item in accepted[:10]:
    lines.append(f"- `{item.get('repo_id')}` score={item.get('final_score')} speaker={','.join(item.get('speaker_candidates') or [])}")
report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
    echo "Final model replacement succeeded. Report: $FINAL_REPORT"
    exit 0
  fi

  echo "Smoke test failed for candidate rank $RANK; active preset was not changed. Trying next candidate." >&2
  RANK=$((RANK + 1))
done

python - "$FINAL_REPORT" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
candidates = json.loads(Path("runtime/model_search/candidates.json").read_text(encoding="utf-8"))
presets = json.loads(Path("backend/app/config/svc_model_presets.json").read_text(encoding="utf-8"))
smoke_path = Path("runtime/model_search/final_model_smoke_test.json")
smoke = json.loads(smoke_path.read_text(encoding="utf-8")) if smoke_path.exists() else {}
lines = [
    "# Final So-VITS-SVC Model Install Report",
    "",
    "All accepted candidates failed install or CUDA smoke test.",
    "",
    f"- active_preset_id: `{presets.get('active_preset_id')}`",
    f"- last_smoke_success: `{smoke.get('success')}`",
    "",
    "## Candidates",
    "",
]
for item in candidates.get("candidates", [])[:15]:
    lines.append(f"- `{item.get('repo_id')}` score={item.get('final_score')} rejection={item.get('rejection_reason') or 'accepted'}")
report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
echo "No final model passed smoke test. Report: $FINAL_REPORT" >&2
exit 1
