"""Real MobileNetV2 inference: enabled only with matching trained weights and class map.

The optional torch/torchvision packages are intentionally not part of the lightweight UI install.
A checkpoint MUST match torchvision MobileNetV2 classifier architecture and dataset labels.
"""
from pathlib import Path
import json
from datetime import datetime, timezone
from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / 'models' / 'best.pth'
CLASSES = ROOT / 'models' / 'classes.json'
MAX_BYTES = 10 * 1024 * 1024


def inspect_image(path):
    p=Path(path)
    if not p.is_file() or p.suffix.lower() not in ('.jpg','.jpeg','.png','.webp'):
        raise ValueError('Chọn ảnh JPG, PNG hoặc WEBP hợp lệ.')
    count=p.stat().st_size
    if not 0 < count <= MAX_BYTES:
        raise ValueError('Ảnh phải có dung lượng tối đa 10 MB.')
    try:
        with Image.open(p) as im:
            if im.format not in ('JPEG','PNG','WEBP'):
                raise ValueError('Định dạng ảnh không hỗ trợ.')
            w,h=im.size
            im.verify()
    except (UnidentifiedImageError,OSError) as ex:
        raise ValueError('Không thể mở ảnh; file có thể đã bị hỏng.') from ex
    return {'name':p.name,'path':str(p),'bytes':count,'width':w,'height':h}


def labels():
    raw=json.loads(CLASSES.read_text(encoding='utf-8'))
    if isinstance(raw, list):
        result=raw
    elif isinstance(raw,dict) and all(str(i) in raw for i in range(len(raw))):
        result=[raw[str(i)] for i in range(len(raw))]
    elif isinstance(raw,dict) and 'classes' in raw:
        result=raw['classes']
    else:
        raise ValueError('classes.json phải là danh sách nhãn theo index hoặc dict {"0": "..."}.')
    if not result or not all(isinstance(x,str) and x for x in result):
        raise ValueError('Nhãn lớp không hợp lệ.')
    return result


def model_ready():
    return WEIGHTS.is_file() and CLASSES.is_file()

_cached=None
_cached_signature=None

def predict(path):
    """Return real top-k probabilities; NEVER fabricate disease predictions."""
    global _cached,_cached_signature
    info=inspect_image(path)
    if not model_ready():
        return {'mode':'unavailable','label':None,'confidence':None,'scores':[],
                'message':'Chưa có best.pth và classes.json phù hợp. Chỉ kiểm tra ảnh.'}
    try:
        import torch
        from torchvision.models import mobilenet_v2
        from torchvision import transforms
    except ImportError as ex:
        raise RuntimeError('Thiếu PyTorch/torchvision. Cài bản phù hợp Python và GPU/CPU.') from ex
    names=labels()
    signature=(WEIGHTS.stat().st_mtime_ns,CLASSES.stat().st_mtime_ns)
    if _cached is None or _cached_signature!=signature:
        # This loader intentionally accepts only state_dict-style weights.
        # Weights must be from the same MobileNetV2 architecture and class order.
        net=mobilenet_v2(weights=None)
        net.classifier[1]=torch.nn.Linear(net.last_channel,len(names))
        obj=torch.load(str(WEIGHTS),map_location='cpu',weights_only=True)
        if isinstance(obj,dict) and 'model_state_dict' in obj:
            obj=obj['model_state_dict']
        elif isinstance(obj,dict) and 'state_dict' in obj:
            obj=obj['state_dict']
        if not isinstance(obj,dict):
            raise ValueError('Checkpoint không chứa state_dict hợp lệ.')
        net.load_state_dict(obj,strict=True)
        net.eval()
        _cached=net
        _cached_signature=signature
    # IMPORTANT: replace transforms if the actual training pipeline used different normalization/resize.
    pipeline=transforms.Compose([
        transforms.Resize(256),transforms.CenterCrop(224),
        transforms.ToTensor(),transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])
    ])
    with Image.open(info['path']) as img:
        tensor=pipeline(img.convert('RGB')).unsqueeze(0)
    with torch.inference_mode():
        scores=torch.softmax(_cached(tensor)[0],dim=0)
        values,indices=torch.topk(scores,k=min(5,len(names)))
    ranking=[{'label':names[int(i)],'confidence':float(v)} for v,i in zip(values,indices)]
    return {'mode':'ai','label':ranking[0]['label'],'confidence':ranking[0]['confidence'],
            'scores':ranking,
            'model_info':f"MobileNetV2 | {WEIGHTS.name} | modified={datetime.fromtimestamp(WEIGHTS.stat().st_mtime, timezone.utc).isoformat(timespec='seconds')}",
            'message':'Kết quả suy luận từ checkpoint cục bộ; chỉ hỗ trợ nghiên cứu.'}
