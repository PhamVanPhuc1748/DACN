"""Verified local inference for the trusted PigSkin handoff checkpoint."""

from __future__ import annotations

from datetime import datetime, timezone
import atexit
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

from PIL import Image, ImageOps, UnidentifiedImageError


ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / 'models' / 'best.pth'
CLASSES = ROOT / 'models' / 'classes.json'
MODEL_MANIFEST = ROOT / 'models' / 'model_manifest.json'
RUNTIME_CONFIG = ROOT / 'models' / 'runtime.json'
MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 24_000_000
WORKER_START_TIMEOUT = 45.0
WORKER_REQUEST_TIMEOUT = 60.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_image(path):
    p = Path(path)
    if not p.is_file() or p.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
        raise ValueError('Chọn ảnh JPG, PNG hoặc WEBP hợp lệ.')
    count = p.stat().st_size
    if not 0 < count <= MAX_BYTES:
        raise ValueError('Ảnh phải có dung lượng tối đa 10 MB.')
    try:
        with Image.open(p) as image:
            if image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise ValueError('Định dạng ảnh không hỗ trợ.')
            raw_width, raw_height = image.size
            if raw_width * raw_height > MAX_PIXELS:
                raise ValueError('Ảnh vượt quá 24 triệu pixel. Hãy chọn ảnh có độ phân giải nhỏ hơn.')
            image.verify()
        with Image.open(p) as image:
            width, height = ImageOps.exif_transpose(image).size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Không thể mở ảnh; file có thể đã bị hỏng.') from exc
    return {'name': p.name, 'path': str(p), 'bytes': count,
            'width': width, 'height': height}


def labels():
    raw = json.loads(CLASSES.read_text(encoding='utf-8'))
    if isinstance(raw, list):
        result = raw
    elif isinstance(raw, dict) and all(str(index) in raw for index in range(len(raw))):
        result = [raw[str(index)] for index in range(len(raw))]
    elif isinstance(raw, dict) and 'classes' in raw:
        result = raw['classes']
    else:
        raise ValueError('classes.json phải là danh sách nhãn theo index hoặc dict {"0": "..."}.')
    if not isinstance(result, list) or not result or not all(
            isinstance(item, str) and item for item in result):
        raise ValueError('Nhãn lớp không hợp lệ.')
    if len(result) != 10 or len(set(result)) != 10:
        raise ValueError('Checkpoint của dự án cần đúng 10 nhãn khác nhau theo thứ tự huấn luyện.')
    return result


def model_spec():
    raw = json.loads(MODEL_MANIFEST.read_text(encoding='utf-8'))
    required = {'run_id', 'architecture', 'checkpoint_sha256', 'manifest_sha256',
                'classes_sha256', 'preprocessing', 'validation'}
    if not isinstance(raw, dict) or not required.issubset(raw):
        raise ValueError('model_manifest.json thiếu metadata xác minh bắt buộc.')
    return raw


def _asset_error():
    missing = [str(path.relative_to(ROOT)) for path in
               (WEIGHTS, CLASSES, MODEL_MANIFEST) if not path.is_file()]
    if missing:
        return 'Cần bổ sung: ' + ', '.join(missing)
    try:
        names = labels()
        spec = model_spec()
        if _sha256(WEIGHTS) != str(spec['checkpoint_sha256']).lower():
            return 'SHA-256 checkpoint không khớp model_manifest.json.'
        if _sha256(CLASSES) != str(spec['classes_sha256']).lower():
            return 'SHA-256 classes.json không khớp model_manifest.json.'
        if spec.get('class_count') != len(names):
            return 'Số lớp trong model manifest không khớp classes.json.'
        preprocessing = spec['preprocessing']
        if preprocessing.get('resize') != [224, 224]:
            return 'Preprocessing đã xác minh phải là Resize((224, 224)).'
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
        return str(exc)
    return None


def model_ready():
    """True only when all model assets and their recorded hashes agree."""
    return _asset_error() is None


def _external_python():
    override = os.environ.get('PIGSKIN_AI_PYTHON', '').strip()
    if override:
        candidate = Path(override)
    elif RUNTIME_CONFIG.is_file():
        try:
            candidate = Path(json.loads(RUNTIME_CONFIG.read_text(
                encoding='utf-8')).get('python_executable', ''))
        except (OSError, json.JSONDecodeError, TypeError):
            return None
    else:
        return None
    return candidate if candidate.is_file() else None


_runtime_probe_cache = {}


def _probe_external_runtime(python_path: Path):
    signature = (str(python_path), python_path.stat().st_mtime_ns)
    if signature in _runtime_probe_cache:
        return _runtime_probe_cache[signature]
    try:
        result = subprocess.run([
            str(python_path), '-c',
            "import json,torch,torchvision; print(json.dumps({"
            "'torch':torch.__version__,'torchvision':torchvision.__version__}))"
        ], capture_output=True, text=True, timeout=30, check=False)
        if result.returncode != 0:
            value = (False, result.stderr.strip() or 'Runtime AI không khởi động được.')
        else:
            versions = json.loads(result.stdout.strip())
            value = (True, f"torch {versions['torch']} • torchvision {versions['torchvision']}")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, KeyError) as exc:
        value = (False, str(exc))
    _runtime_probe_cache.clear()
    _runtime_probe_cache[signature] = value
    return value


def model_status():
    """Describe readiness without blocking the Flet thread on PyTorch import."""
    asset_error = _asset_error()
    if asset_error:
        return {'available': False, 'missing': [], 'message': asset_error}
    if importlib.util.find_spec('torch') is not None and importlib.util.find_spec('torchvision') is not None:
        return {'available': True, 'missing': [],
                'message': 'Model và runtime đã xác minh; AI chỉ hỗ trợ chuyên gia.'}
    external = _external_python()
    if external is None:
        return {'available': False, 'missing': ['torch', 'torchvision'],
                'message': 'Model hợp lệ nhưng môi trường Studio thiếu torch/torchvision; '
                           'cấu hình PIGSKIN_AI_PYTHON hoặc models/runtime.json.'}
    worker = _worker_client
    if (worker is not None and worker.pid is not None
            and worker.startup_timings is not None):
        return {'available': True, 'missing': [],
                'message': 'Model đã xác minh • AI worker đã nạp model và sẵn sàng.'}
    return {'available': False, 'missing': [],
            'message': 'Model và runtime đã cấu hình • AI worker đang chờ prewarm.'}


_cached = None
_cached_signature = None
_cached_load_timings = None


def _build_model(torch, models, architecture, class_count):
    if architecture == 'mobilenet_v2':
        net = models.mobilenet_v2(weights=None)
        net.classifier[1] = torch.nn.Linear(net.last_channel, class_count)
        return net
    if architecture == 'efficientnet_b0':
        net = models.efficientnet_b0(weights=None)
        net.classifier[1] = torch.nn.Linear(net.classifier[1].in_features, class_count)
        return net
    raise ValueError(f'Kiến trúc checkpoint chưa được hỗ trợ: {architecture}')


def _ensure_local_model():
    """Load and verify the model once in the current process."""
    global _cached, _cached_signature, _cached_load_timings
    import_started = time.perf_counter()
    import torch
    from torchvision import models, transforms
    runtime_import_ms = (time.perf_counter() - import_started) * 1000

    names = labels()
    spec = model_spec()
    signature = (WEIGHTS.stat().st_mtime_ns, CLASSES.stat().st_mtime_ns,
                 MODEL_MANIFEST.stat().st_mtime_ns)
    if _cached is None or _cached_signature != signature:
        load_started = time.perf_counter()
        checkpoint = torch.load(str(WEIGHTS), map_location='cpu', weights_only=True)
        required = {'model', 'label_mode', 'classes', 'class_to_index', 'image_size',
                    'normalization', 'state_dict', 'best_epoch', 'val_metrics'}
        if not isinstance(checkpoint, dict) or not required.issubset(checkpoint):
            raise ValueError('Checkpoint không chứa schema metadata/state_dict đã xác minh.')
        if checkpoint['model'] != spec['architecture'] or checkpoint['classes'] != names:
            raise ValueError('Kiến trúc hoặc thứ tự lớp trong checkpoint không khớp manifest.')
        if checkpoint['label_mode'] != 'single':
            raise ValueError('Checkpoint phải là mô hình phân loại single-label.')
        preprocessing = spec['preprocessing']
        if checkpoint['image_size'] != preprocessing['resize'][0]:
            raise ValueError('Kích thước ảnh trong checkpoint không khớp preprocessing.')
        if checkpoint['normalization'] != preprocessing['normalization']:
            # JSON uses lists while the checkpoint uses tuples; compare numeric values.
            actual = checkpoint['normalization']
            expected = preprocessing['normalization']
            if list(actual['mean']) != expected['mean'] or list(actual['std']) != expected['std']:
                raise ValueError('Normalization trong checkpoint không khớp model manifest.')
        net = _build_model(torch, models, checkpoint['model'], len(names))
        net.load_state_dict(checkpoint['state_dict'], strict=True)
        net.eval()
        _cached = (net, checkpoint, names, spec, transforms, torch)
        _cached_signature = signature
        _cached_load_timings = {
            'runtime_import_ms': runtime_import_ms,
            'checkpoint_model_load_ms': (time.perf_counter() - load_started) * 1000,
        }
    return _cached, dict(_cached_load_timings or {
        'runtime_import_ms': runtime_import_ms,
        'checkpoint_model_load_ms': 0.0,
    })


def _predict_local(path):
    validation_started = time.perf_counter()
    info = inspect_image(path)
    image_validation_ms = (time.perf_counter() - validation_started) * 1000
    (net, checkpoint, names, spec, transforms, torch), load_timings = _ensure_local_model()
    normalization = checkpoint['normalization']
    size = checkpoint['image_size']
    pipeline = transforms.Compose([
        transforms.Resize((size, size)),
        transforms.ToTensor(),
        transforms.Normalize(normalization['mean'], normalization['std']),
    ])
    preprocessing_started = time.perf_counter()
    with Image.open(info['path']) as image:
        tensor = pipeline(ImageOps.exif_transpose(image).convert('RGB')).unsqueeze(0)
    preprocessing_ms = (time.perf_counter() - preprocessing_started) * 1000
    inference_started = time.perf_counter()
    with torch.inference_mode():
        probabilities = torch.softmax(net(tensor)[0], dim=0)
        values, indices = torch.topk(probabilities, k=len(names))
    inference_ms = (time.perf_counter() - inference_started) * 1000
    ranking = [{'label': names[int(index)], 'confidence': float(value)}
               for value, index in zip(values, indices)]
    return {
        'mode': 'ai',
        'label': ranking[0]['label'],
        'confidence': ranking[0]['confidence'],
        'scores': ranking,
        'model_info': (
            f"{spec['architecture']} • run {spec['run_id']} • "
            f"sha256={spec['checkpoint_sha256'][:12]} • "
            f"modified={datetime.fromtimestamp(WEIGHTS.stat().st_mtime, timezone.utc).isoformat(timespec='seconds')}"
        ),
        'message': 'Kết quả checkpoint thật; chỉ hỗ trợ nghiên cứu và phải được chuyên gia xác minh.',
        'runtime_timings': {
            **load_timings,
            'image_validation_ms': image_validation_ms,
            'preprocessing_ms': preprocessing_ms,
            'inference_ms': inference_ms,
        },
    }


class _WorkerExited(RuntimeError):
    pass


class AIWorkerClient:
    """Thread-safe persistent JSON-lines client for the isolated AI runtime."""

    def __init__(self, python_path: Path, start_timeout=WORKER_START_TIMEOUT,
                 request_timeout=WORKER_REQUEST_TIMEOUT,
                 worker_module='services.inference_worker', worker_environment=None):
        self.python_path = Path(python_path)
        self.start_timeout = float(start_timeout)
        self.request_timeout = float(request_timeout)
        self.worker_module = worker_module
        self.worker_environment = dict(worker_environment or {})
        self._lock = threading.RLock()
        self._process = None
        self._reader = None
        self._responses = queue.Queue()
        self._request_id = 0
        self.startup_timings = None

    @property
    def pid(self):
        return self._process.pid if self._process and self._process.poll() is None else None

    def _reader_loop(self, process, responses):
        try:
            for line in process.stdout:
                try:
                    responses.put(json.loads(line))
                except json.JSONDecodeError:
                    responses.put({'event': 'protocol_error', 'line': line[-500:]})
        finally:
            responses.put({'event': 'worker_exit', 'returncode': process.poll()})

    def _wait_message(self, timeout):
        try:
            message = self._responses.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError('AI worker không phản hồi đúng thời hạn.') from exc
        if message.get('event') == 'worker_exit':
            raise _WorkerExited(
                f"AI worker đã dừng bất ngờ (exit={message.get('returncode')}).")
        if message.get('event') == 'protocol_error':
            raise RuntimeError('AI worker trả dữ liệu protocol không hợp lệ.')
        return message

    def _start_locked(self):
        if self._process is not None and self._process.poll() is None:
            return
        self._stop_locked(graceful=False)
        self._responses = queue.Queue()
        environment = os.environ.copy()
        environment['PIGSKIN_AI_WORKER'] = '1'
        environment['PYTHONIOENCODING'] = 'utf-8'
        environment.update(self.worker_environment)
        command = [str(self.python_path), '-u', '-m',
                   self.worker_module, '--serve']
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        started = time.perf_counter()
        self._process = subprocess.Popen(
            command, cwd=str(ROOT), env=environment, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            encoding='utf-8', errors='replace', bufsize=1,
            creationflags=creationflags)
        self._reader = threading.Thread(
            target=self._reader_loop, args=(self._process, self._responses),
            name='pigskin-ai-worker-reader', daemon=True)
        self._reader.start()
        try:
            message = self._wait_message(self.start_timeout)
        except Exception:
            self._stop_locked(graceful=False)
            raise
        if message.get('event') != 'ready' or not message.get('ok'):
            self._stop_locked(graceful=False)
            raise RuntimeError(message.get('error') or 'AI worker không khởi tạo được.')
        self.startup_timings = dict(message.get('timings') or {})
        self.startup_timings['worker_start_total_ms'] = (
            time.perf_counter() - started) * 1000

    def predict(self, path):
        with self._lock:
            last_error = None
            for attempt in range(2):
                try:
                    self._start_locked()
                    self._request_id += 1
                    request_id = self._request_id
                    request = {'id': request_id, 'command': 'predict',
                               'path': str(Path(path).resolve())}
                    self._process.stdin.write(json.dumps(request) + '\n')
                    self._process.stdin.flush()
                    message = self._wait_message(self.request_timeout)
                    if message.get('id') != request_id:
                        raise RuntimeError('AI worker trả sai request ID.')
                    if not message.get('ok'):
                        raise RuntimeError(message.get('error') or 'AI worker dự đoán thất bại.')
                    result = message['result']
                    result.setdefault('worker_startup_timings', self.startup_timings)
                    return result
                except TimeoutError:
                    self._stop_locked(graceful=False)
                    raise
                except (_WorkerExited, BrokenPipeError, OSError) as exc:
                    last_error = exc
                    self._stop_locked(graceful=False)
                    if attempt == 0:
                        continue
            raise RuntimeError(f'AI worker không thể phục hồi: {last_error}')

    def start(self):
        with self._lock:
            self._start_locked()
            return dict(self.startup_timings or {})

    def _stop_locked(self, graceful=True):
        process = self._process
        self._process = None
        if process is None:
            return
        if graceful and process.poll() is None:
            try:
                process.stdin.write(json.dumps({'id': 0, 'command': 'shutdown'}) + '\n')
                process.stdin.flush()
                process.wait(timeout=5)
            except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for stream in (process.stdin, process.stdout):
            try:
                stream.close()
            except (AttributeError, OSError):
                pass

    def close(self):
        with self._lock:
            self._stop_locked(graceful=True)


_worker_client = None
_worker_client_lock = threading.Lock()


def _persistent_worker(python_path):
    global _worker_client
    with _worker_client_lock:
        if (_worker_client is None
                or _worker_client.python_path.resolve() != Path(python_path).resolve()):
            if _worker_client is not None:
                _worker_client.close()
            _worker_client = AIWorkerClient(python_path)
        return _worker_client


def shutdown_ai_worker():
    global _worker_client
    with _worker_client_lock:
        worker = _worker_client
        _worker_client = None
    if worker is not None:
        worker.close()


def prewarm_ai_worker():
    """Load the verified model off the UI thread before the first prediction."""
    if not model_ready():
        raise RuntimeError(_asset_error() or 'Model chưa sẵn sàng.')
    if importlib.util.find_spec('torch') is not None and importlib.util.find_spec('torchvision') is not None:
        _, timings = _ensure_local_model()
        return timings
    external = _external_python()
    if external is None:
        raise RuntimeError('Chưa cấu hình runtime PyTorch tách biệt.')
    return _persistent_worker(external).start()


atexit.register(shutdown_ai_worker)


def predict(path):
    """Return real top-k scores; never synthesize a disease prediction."""
    inspect_image(path)
    if not model_ready():
        return {'mode': 'unavailable', 'label': None, 'confidence': None, 'scores': [],
                'message': _asset_error() or 'Model chưa sẵn sàng.'}
    if importlib.util.find_spec('torch') is not None and importlib.util.find_spec('torchvision') is not None:
        return _predict_local(path)
    external = _external_python()
    if external is not None and os.environ.get('PIGSKIN_AI_WORKER') != '1':
        # Worker readiness performs a stricter check by loading the checkpoint;
        # avoid paying for a second torch/torchvision import before startup.
        return _persistent_worker(external).predict(path)
    raise RuntimeError('Thiếu PyTorch/torchvision cho môi trường suy luận AI.')
