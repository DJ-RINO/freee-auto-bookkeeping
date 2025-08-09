import hashlib
from typing import Dict, List, Optional

from ocr_models import ReceiptRecord
from state_store import is_duplicated, mark_linked, write_audit


def _receipt_hash(rec: ReceiptRecord, file_digest_hex: str) -> str:
    base = f"{rec.vendor.strip().upper()}|{rec.date.isoformat()}|{rec.amount}|{file_digest_hex}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def decide_action(score: int, cfg: Dict) -> str:
    th = cfg.get("thresholds", {"auto": 85, "assist_min": 65, "assist_max": 84})
    if score >= th["auto"]:
        return "AUTO"
    if th["assist_min"] <= score <= th["assist_max"]:
        return "ASSIST"
    return "MANUAL"


def link_receipt(freee_client, tx_id: str, receipt_id: str) -> Dict:
    """freee APIで証憑ひも付けを実行"""
    # 実装: POST /receipts/{id}/relationships or deals attachments API
    # ここでは簡易に wallet_txn に receipt を関連付けるエンドポイントを仮定
    return freee_client.attach_receipt_to_tx(tx_id=int(tx_id), receipt_id=int(receipt_id))


def ensure_not_duplicated_and_link(freee_client, rec: ReceiptRecord, file_digest_hex: str, best_tx: Dict, cfg: Dict) -> Optional[Dict]:
    rh = _receipt_hash(rec, file_digest_hex)
    if is_duplicated(rh):
        write_audit("INFO", "system", "duplicate_skip", [str(best_tx.get("id")), rec.receipt_id], best_tx.get("score", 0), "skipped")
        return None
    result = link_receipt(freee_client, str(best_tx.get("id")), rec.receipt_id)
    mark_linked(rh, {"tx_id": best_tx.get("id"), "receipt_id": rec.receipt_id, "score": best_tx.get("score")})
    write_audit("INFO", "system", "link", [str(best_tx.get("id")), rec.receipt_id], best_tx.get("score", 0), "linked")
    return result


