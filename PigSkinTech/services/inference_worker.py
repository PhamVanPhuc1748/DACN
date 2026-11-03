"""JSON subprocess bridge for an isolated PyTorch runtime."""

import json
import sys
import time

from services.inference import _ensure_local_model, _predict_local


def _write(message):
    print(json.dumps(message, ensure_ascii=True), flush=True)


def serve() -> int:
    started = time.perf_counter()
    try:
        _, load_timings = _ensure_local_model()
    except Exception as exc:
        _write({'event': 'ready', 'ok': False,
                'error': f'{type(exc).__name__}: {exc}'})
        return 1
    _write({'event': 'ready', 'ok': True, 'timings': {
        **load_timings,
        'worker_initialization_ms': (time.perf_counter() - started) * 1000,
    }})
    for line in sys.stdin:
        request = None
        try:
            request = json.loads(line)
            request_id = request.get('id')
            command = request.get('command')
            if command == 'shutdown':
                _write({'id': request_id, 'ok': True, 'event': 'shutdown'})
                return 0
            if command != 'predict' or not isinstance(request.get('path'), str):
                raise ValueError('Yêu cầu AI worker không hợp lệ.')
            requested = time.perf_counter()
            result = _predict_local(request['path'])
            result['runtime_timings']['worker_request_total_ms'] = (
                time.perf_counter() - requested) * 1000
            _write({'id': request_id, 'ok': True, 'result': result})
        except Exception as exc:
            _write({'id': request.get('id') if isinstance(request, dict) else None,
                    'ok': False, 'error': f'{type(exc).__name__}: {exc}'})
    return 0


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == '--serve':
        return serve()
    if len(sys.argv) != 2:
        print('Usage: python -m services.inference_worker IMAGE|--serve', file=sys.stderr)
        return 2
    try:
        result = _predict_local(sys.argv[1])
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    _write(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
