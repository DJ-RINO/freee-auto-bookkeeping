import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from rapidfuzz.distance import JaroWinkler

from ocr_models import ReceiptRecord, MatchCandidate


def _normalize_name(text: str) -> str:
    if not text:
        return ""
    s = text
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("株式会社", "").replace("(株)", "").replace("㈱", "")
    s = re.sub(r"\s+", "", s)
    s = s.upper()
    return s


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return JaroWinkler.normalized_similarity(a, b)


def _within_amount(a: int, b: int, tol: int) -> bool:
    return abs(a - b) <= tol


def _within_date(d1: datetime, d2: datetime, tol_days: int) -> bool:
    return abs((d1.date() - d2.date()).days) <= tol_days


def score_match(ocr: ReceiptRecord, tx: Dict, cfg: Dict) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    weights = cfg.get("weights", {"amount": 0.4, "date": 0.25, "name": 0.3, "tax_rate": 0.05})
    tol = cfg.get("tolerances", {"amount_jpy": 1, "days": 3})

    # amount
    amount_score = 100 if _within_amount(ocr.amount, abs(tx.get("amount", 0)), tol["amount_jpy"]) else 0
    if amount_score == 100:
        reasons.append("amount≈")

    # date
    issued_at = tx.get("date") or tx.get("record_date") or tx.get("due_date")
    try:
        tx_date = datetime.strptime(issued_at, "%Y-%m-%d") if issued_at else None
    except Exception:
        tx_date = None
    date_score = 100 if (tx_date and _within_date(datetime.combine(ocr.date, datetime.min.time()), tx_date, tol["days"])) else 0
    if date_score == 100:
        reasons.append("date≈")

    # name
    o = _normalize_name(ocr.vendor)
    d = _normalize_name(tx.get("description", "") or tx.get("partner_name", ""))
    sim = _similarity(o, d)
    name_score = int(sim * 100)
    reasons.append(f"name~{name_score}")

    # tax rate (optional)
    tax_score = 100 if (ocr.tax_rate is not None and int(round((ocr.tax_rate or 0) * 100)) == tx.get("tax_rate", -1)) else 0
    if tax_score == 100:
        reasons.append("tax=")

    total = int(
        amount_score * weights.get("amount", 0.4)
        + date_score * weights.get("date", 0.25)
        + name_score * weights.get("name", 0.3)
        + tax_score * weights.get("tax_rate", 0.05)
    )
    return max(0, min(100, total)), reasons


def match_candidates(ocr_receipt: ReceiptRecord, tx_list: List[Dict], cfg: Dict) -> List[Dict]:
    min_sim = cfg.get("similarity", {}).get("min_candidate", 0.6)
    candidates: List[Dict] = []
    for tx in tx_list:
        # quick prefilter
        if _similarity(_normalize_name(ocr_receipt.vendor), _normalize_name(tx.get("description", "") or tx.get("partner_name", ""))) < min_sim:
            continue
        score, reasons = score_match(ocr_receipt, tx, cfg)
        deltas = {
            "amount": abs(ocr_receipt.amount - abs(tx.get("amount", 0))),
            "date": tx.get("date"),
            "name": tx.get("description") or tx.get("partner_name"),
        }
        candidates.append({"tx_id": str(tx.get("id")), "score": score, "reasons": reasons, "deltas": deltas})

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:3]


