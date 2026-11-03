"""Print a privacy-safe, read-only readiness report for the current LocalDB."""

import json

from services.readiness import run_readonly_audit


if __name__ == '__main__':
    print(json.dumps(run_readonly_audit(), ensure_ascii=False, indent=2))
