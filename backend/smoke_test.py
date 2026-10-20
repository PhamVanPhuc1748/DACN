"""Smoke test toàn bộ API (cần server đang chạy): python smoke_test.py [base_url]"""
import io
import json
import sys
import urllib.error
import urllib.request
import uuid

from PIL import Image

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def call(method, path, token=None, body=None, files=None, form=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    data = None
    if files is not None:
        b = uuid.uuid4().hex
        parts = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in (form or {}).items()]
        for name, (fname, content) in files:
            parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{name}"; filename="{fname}"\r\n'
                         f'Content-Type: image/png\r\n\r\n'.encode() + content + b"\r\n")
        data = b"".join(parts) + f"--{b}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={b}"
    elif body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return r.status, json.loads(raw) if r.headers.get_content_type() == "application/json" else raw
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def login(u):
    s, r = call("POST", "/api/auth/login", body={"username": u, "password": "demo123"})
    assert s == 200, r
    return r["token"]


png = io.BytesIO()
Image.new("RGB", (64, 48), (220, 120, 120)).save(png, "PNG")
png = png.getvalue()

admin, eng, vet, owner = (login(u) for u in ("admin", "engineer", "vet", "owner"))
assert call("POST", "/api/auth/login", body={"username": "vet", "password": "x"})[0] == 401
assert call("GET", "/api/cases")[0] == 401

# 1. Chẩn đoán
s, res = call("POST", "/api/predict", owner, files=[("files", ("a.png", png))], form={"pen": "Khu A1"})
assert s == 200 and res[0]["status"] in ("HEALTHY", "ABNORMAL") and len(res[0]["top3"]) == 3, res
assert call("POST", "/api/predict", owner, files=[("files", ("a.png", b"not an image"))])[0] == 400
s, cmp = call("POST", "/api/predict/compare", eng, files=[("file", ("a.png", png))], form={"model_ids": "2,5"})
assert s == 200 and len(cmp) == 2
assert call("POST", "/api/predict/compare", owner, files=[("file", ("a.png", png))], form={"model_ids": "2"})[0] == 403

# 2. Ca bệnh + thẩm định
s, cases = call("GET", "/api/cases?low_conf=true&status=PENDING", owner)
assert s == 200 and all(c["review_status"] == "PENDING" for c in cases["items"])
cid = res[0]["prediction_id"]
assert call("POST", f"/api/cases/{cid}/review", owner, body={})[0] == 403
assert call("POST", f"/api/cases/{cid}/review", vet, body={"class_code": "ENV_SUN"})[0] == 400  # thiếu ghi chú
s, r = call("POST", f"/api/cases/{cid}/review", vet, body={"class_code": "ENV_SUN", "note": "Vùng lưng, nắng gắt"})
assert s == 200 and r["review_status"] in ("CONFIRMED", "CORRECTED")
s, csv = call("GET", "/api/cases/export.csv", vet)
assert s == 200 and csv.startswith("\ufeff".encode())

# 3. Dataset
s, ds = call("GET", "/api/datasets", eng)
assert s == 200 and ds[0]["leaked_stems"] == 0 and ds[0]["total_stems"] == 1064, ds[0]["total_stems"]
assert call("GET", "/api/datasets", owner)[0] == 403
call("POST", "/api/datasets/unlabeled/pseudo-label", eng, body={})
s, q = call("GET", "/api/datasets/unlabeled", vet)
assert s == 200 and q["items"] and q["items"][0]["label_id"]
assert call("POST", f"/api/datasets/labels/{q['items'][0]['label_id']}/review", vet, body={"action": "approve"})[0] == 200

# 4. Models
s, models = call("GET", "/api/models", eng)
assert s == 200 and sum(m["is_default"] for m in models) == 1
assert call("POST", "/api/models/2/default", vet)[0] == 403

# 5. Dashboard
s, d = call("GET", "/api/dashboard", owner)
assert s == 200 and any(a["code"] == "VIRA_FMD" for a in d["alerts"]), d["alerts"]
assert call("GET", "/api/dashboard", eng)[0] == 403

# 6. Admin
assert len(call("GET", "/api/diseases", owner)[1]) == 10
assert call("GET", "/api/admin/users", vet)[0] == 403
assert call("PUT", "/api/settings", admin, body={"review_threshold": 1.5})[0] == 400
assert call("PATCH", "/api/admin/users/1", admin, body={"is_active": False})[0] == 400  # tự khóa
print("ALL OK")
