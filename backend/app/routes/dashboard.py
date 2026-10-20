"""Màn hình 5 — Dashboard dịch tễ & cảnh báo sớm."""
from fastapi import APIRouter, Depends

from ..auth import require
from ..db import get_db, get_settings, rows

router = APIRouter(prefix="/api/dashboard")

# Nhãn hiệu lực: kết luận bác sĩ nếu đã thẩm định, nếu chưa thì dự đoán AI.
EFFECTIVE = "COALESCE(p.final_class_id, p.predicted_class_id)"


@router.get("")
def dashboard(days: int = 7, user=Depends(require("FARM_OWNER", "VET", "ADMIN")), db=Depends(get_db)):
    s = get_settings(db)
    since = f"-{max(1, min(days, 365))} days"
    k = db.execute(f"""
        SELECT
          SUM(date(p.created_at) = date('now','localtime')) AS today,
          SUM(p.created_at >= datetime('now','localtime', ?)) AS period,
          SUM(p.created_at >= datetime('now','localtime', ?) AND c.code = 'HEALTHY') AS healthy,
          SUM(p.review_status = 'PENDING') AS pending,
          SUM(p.review_status = 'PENDING' AND p.confidence < ?) AS low_conf
        FROM predictions p JOIN disease_classes c ON c.id = {EFFECTIVE}""",
                   (since, since, float(s["review_threshold"]))).fetchone()
    period = k["period"] or 0
    healthy_pct = round(100 * (k["healthy"] or 0) / period, 1) if period else 0

    alerts = rows(db.execute(f"""
        SELECT p.pen, c.code, c.name, COUNT(*) AS count, MAX(p.created_at) AS last_seen
        FROM predictions p JOIN disease_classes c ON c.id = {EFFECTIVE}
        WHERE c.is_dangerous = 1 AND p.created_at >= datetime('now','localtime', ?)
        GROUP BY p.pen, c.code HAVING COUNT(*) >= ? ORDER BY count DESC""",
                         (f"-{s['outbreak_window_days']} days", int(s["outbreak_threshold"]))))

    distribution = rows(db.execute(f"""
        SELECT c.code, c.name, c.color, COUNT(*) AS count FROM predictions p
        JOIN disease_classes c ON c.id = {EFFECTIVE}
        WHERE p.created_at >= datetime('now','localtime', ?) GROUP BY c.code ORDER BY count DESC""", (since,)))

    weekly = rows(db.execute(f"""
        SELECT strftime('%Y-W%W', p.created_at) AS week, COUNT(*) AS total,
               SUM(c.code != 'HEALTHY') AS abnormal, SUM(c.is_dangerous) AS dangerous
        FROM predictions p JOIN disease_classes c ON c.id = {EFFECTIVE}
        WHERE p.created_at >= datetime('now','localtime','-56 days') GROUP BY week ORDER BY week"""))

    by_pen = rows(db.execute(f"""
        SELECT p.pen, COUNT(*) AS total, SUM(c.code != 'HEALTHY') AS abnormal FROM predictions p
        JOIN disease_classes c ON c.id = {EFFECTIVE}
        WHERE p.created_at >= datetime('now','localtime', ?) AND p.pen != '' GROUP BY p.pen ORDER BY p.pen""",
                         (since,)))

    return {"kpi": {"today": k["today"] or 0, "period": period, "healthy_pct": healthy_pct,
                    "abnormal_pct": round(100 - healthy_pct, 1) if period else 0,
                    "pending": k["pending"] or 0, "low_conf": k["low_conf"] or 0},
            "alerts": alerts, "distribution": distribution, "weekly": weekly, "by_pen": by_pen,
            "settings": {k2: s[k2] for k2 in ("outbreak_threshold", "outbreak_window_days")}}
