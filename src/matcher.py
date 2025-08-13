import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from rapidfuzz.distance import JaroWinkler

from ocr_models import ReceiptRecord, MatchCandidate
from vendor_mapping_learner import VendorMappingLearner


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
    # 日付の重要度を下げ、金額と名前に重点を置く
    weights = cfg.get("weights", {"amount": 0.5, "date": 0.1, "name": 0.35, "tax_rate": 0.05})
    # 実用的な許容範囲に調整
    default_tolerances = {
        "amount_jpy": max(1000, int(ocr.amount * 0.05)),  # 1000円または5%の大きい方
        "days": 45  # 1.5ヶ月の許容範囲
    }
    tol = cfg.get("tolerances", default_tolerances)

    # amount
    tx_amount = abs(tx.get("amount", 0))
    amount_diff = abs(ocr.amount - tx_amount)
    amount_score = 100 if _within_amount(ocr.amount, tx_amount, tol["amount_jpy"]) else 0
    if amount_score == 100:
        reasons.append("amount≈")
    else:
        reasons.append(f"amount_diff={amount_diff}(tol={tol['amount_jpy']})")

    # date
    issued_at = tx.get("date") or tx.get("record_date") or tx.get("due_date")
    try:
        tx_date = datetime.strptime(issued_at, "%Y-%m-%d") if issued_at else None
    except Exception:
        tx_date = None
    
    if tx_date:
        date_diff = abs((ocr.date - tx_date.date()).days)
        date_score = 100 if _within_date(datetime.combine(ocr.date, datetime.min.time()), tx_date, tol["days"]) else 0
        if date_score == 100:
            reasons.append("date≈")
        else:
            reasons.append(f"date_diff={date_diff}days(tol={tol['days']})")
    else:
        date_score = 0
        reasons.append("date_missing")

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
    # より多くの候補を評価するため前段フィルターを緩和
    min_sim = cfg.get("similarity", {}).get("min_candidate", 0.3)
    
    # 学習システムを初期化
    learner = VendorMappingLearner()
    
    candidates: List[Dict] = []
    for tx in tx_list:
        tx_description = tx.get("description", "") or tx.get("partner_name", "")
        
        # 1. 学習データからの候補チェック（空の場合はスキップ）
        learned_bonus = 0
        if tx_description and tx_description.strip() and tx_description != "None":
            learned_candidates = learner.get_vendor_candidates(tx_description)
            for learned_candidate in learned_candidates:
                if _similarity(_normalize_name(ocr_receipt.vendor), _normalize_name(learned_candidate["vendor_name"])) > 0.7:
                    learned_bonus = learned_candidate["confidence"] * 30  # 最大30点のボーナス
                    print(f"    🧠 学習データマッチ: '{tx_description}' -> '{learned_candidate['vendor_name']}' (+{learned_bonus:.0f}点)")
                    break
        
        # 2. 通常の類似度フィルター（学習ボーナスがあれば緩和）
        base_similarity = _similarity(_normalize_name(ocr_receipt.vendor), _normalize_name(tx_description))
        if base_similarity < min_sim and learned_bonus == 0:
            continue
            
        # 3. スコア計算
        score, reasons = score_match(ocr_receipt, tx, cfg)
        
        # 4. 学習ボーナスを加算
        if learned_bonus > 0:
            score = min(100, score + learned_bonus)
            reasons.append(f"learned_bonus=+{learned_bonus:.0f}")
        
        deltas = {
            "amount": abs(ocr_receipt.amount - abs(tx.get("amount", 0))),
            "date": tx.get("date"),
            "name": tx_description,
            "learned_bonus": learned_bonus
        }
        candidates.append({"tx_id": str(tx.get("id")), "score": score, "reasons": reasons, "deltas": deltas})

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:3]


