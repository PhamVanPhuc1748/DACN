"""Load the integrated checkpoint and run one isolated real inference."""

import json
from pathlib import Path
import subprocess
import tempfile
import time

from PIL import Image

from services.inference import (ROOT, _external_python, model_ready, model_status,
    predict, shutdown_ai_worker)


def main() -> int:
    if not model_ready():
        raise RuntimeError('Integrated model assets failed hash/metadata validation.')
    with tempfile.TemporaryDirectory(prefix='pigskin-model-smoke-') as root:
        image_path = Path(root) / 'synthetic-runtime-check.png'
        Image.new('RGB', (320, 240), (128, 96, 80)).save(image_path)
        python_path = _external_python()
        reference_started = time.perf_counter()
        reference_process = subprocess.run(
            [str(python_path), '-m', 'services.inference_worker', str(image_path)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60, check=True)
        reference = json.loads(reference_process.stdout)
        one_shot_ms = (time.perf_counter() - reference_started) * 1000
        started = time.perf_counter()
        first = predict(image_path)
        cold_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        second = predict(image_path)
        warm_ms = (time.perf_counter() - started) * 1000
        status = model_status()
        if not status['available']:
            raise RuntimeError(status['message'])
    shutdown_ai_worker()
    if first['mode'] != 'ai' or len(first['scores']) != 10:
        raise RuntimeError('Inference did not return the expected ten-class result.')
    total = sum(item['confidence'] for item in first['scores'])
    if abs(total - 1.0) > 1e-5:
        raise RuntimeError('Softmax scores do not sum to one.')
    if first['label'] != second['label'] or first['scores'] != second['scores']:
        raise RuntimeError('Persistent worker changed the prediction between requests.')
    if first['label'] != reference['label']:
        raise RuntimeError('Persistent worker differs from one-shot inference label.')
    for persistent_score, reference_score in zip(first['scores'], reference['scores']):
        if (persistent_score['label'] != reference_score['label']
                or abs(persistent_score['confidence'] - reference_score['confidence']) > 1e-7):
            raise RuntimeError('Persistent worker differs from one-shot inference scores.')
    print(json.dumps({
        'status': 'MODEL_RUNTIME_SMOKE_OK',
        'model_info': first['model_info'],
        'output_classes': len(first['scores']),
        'cold_ms': cold_ms,
        'warm_ms': warm_ms,
        'one_shot_reference_ms': one_shot_ms,
        'one_shot_equivalent': True,
        'worker_startup_timings': first.get('worker_startup_timings'),
        'warm_runtime_timings': second.get('runtime_timings'),
    }, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
