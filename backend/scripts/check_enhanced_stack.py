import json
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.models_svc.stylesinger_wrapper import stylesinger_service


def run_check() -> dict:
    return stylesinger_service.get_enhanced_stack_status(force_refresh=True)


def main() -> int:
    status = run_check()
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if status.get("ready"):
        print("OK: enhanced stack is ready")
        return 0
    print("MISSING:", ", ".join(status.get("missing", [])))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
