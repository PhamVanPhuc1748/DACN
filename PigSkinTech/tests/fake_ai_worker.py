"""Tiny JSON-lines worker used to test process lifecycle without PyTorch."""

import json
import os
from pathlib import Path
import sys
import time


def write(message):
    print(json.dumps(message), flush=True)


def main():
    if sys.argv[1:] != ['--serve']:
        return 2
    time.sleep(float(os.environ.get('FAKE_WORKER_START_DELAY', '0')))
    write({'event': 'ready', 'ok': True, 'timings': {'fake_start_ms': 0.0}})
    for line in sys.stdin:
        request = json.loads(line)
        if request.get('command') == 'shutdown':
            write({'id': request.get('id'), 'ok': True, 'event': 'shutdown'})
            return 0
        path = Path(request['path'])
        if path.name == 'slow.jpg':
            time.sleep(float(os.environ.get('FAKE_WORKER_DELAY', '0.5')))
        if path.name == 'crash-once.jpg':
            marker = Path(os.environ['FAKE_WORKER_CRASH_MARKER'])
            if not marker.exists():
                marker.write_text('crashed', encoding='ascii')
                os._exit(7)
        write({'id': request['id'], 'ok': True, 'result': {
            'mode': 'ai', 'label': 'fake', 'confidence': 1.0, 'scores': [],
            'worker_pid': os.getpid(),
        }})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
