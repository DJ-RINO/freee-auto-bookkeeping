from datetime import date
from src.ocr_models import ReceiptRecord
from src.matcher import match_candidates, score_match


CFG = {
    "weights": {"amount": 0.4, "date": 0.25, "name": 0.3, "tax_rate": 0.05},
    "tolerances": {"amount_jpy": 1, "days": 3},
    "similarity": {"min_candidate": 0.6}
}


def test_score_amount_and_date_exact():
    rec = ReceiptRecord("r1", "h", "セブンイレブン", date(2025, 8, 1), 1234, 0.1, 0.9)
    tx = {"id": 1, "amount": -1234, "date": "2025-08-01", "description": "セブン-イレブン"}
    score, reasons = score_match(rec, tx, CFG)
    assert score >= 85
    assert any("amount" in r for r in reasons)


def test_match_candidates_filters_by_similarity():
    rec = ReceiptRecord("r2", "h", "三井住友カード", date(2025, 8, 1), 999, 0.1, 0.9)
    txs = [
        {"id": 1, "amount": -999, "date": "2025-08-02", "description": "三井住友ｶｰﾄﾞ"},
        {"id": 2, "amount": -999, "date": "2025-08-02", "description": "NO MATCH"},
    ]
    cands = match_candidates(rec, txs, CFG)
    assert len(cands) == 1
    assert cands[0]["tx_id"] == "1"


