import hashlib
from typing import Dict, List, Optional

from ocr_models import ReceiptRecord
from state_store import (
    is_duplicated,
    mark_linked,
    write_audit,
    record_file_seen,
    get_existing_for_file_sha1,
)


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


def link_receipt(freee_client, *, target_type: str, target_id: str, receipt_id: str) -> Dict:
    """freee APIで証憑ひも付けを実行

    Args:
        target_type: "wallet_txn" | "deal"
        target_id: str
        receipt_id: str
    """
    # TODO: deal への添付APIが利用可能になったら分岐実装
    if target_type not in {"wallet_txn", "deal"}:
        raise ValueError("target_type must be 'wallet_txn' or 'deal'")
    return freee_client.attach_receipt_to_tx(tx_id=int(target_id), receipt_id=int(receipt_id))


def ensure_not_duplicated_and_link(
    freee_client,
    rec: ReceiptRecord,
    file_digest_hex: str,
    best_target: Dict,
    cfg: Dict,
    *,
    target_type: str,
    allow_delete: bool = False,
) -> Optional[Dict]:
    rh = _receipt_hash(rec, file_digest_hex)
    # ファイル単位の重複追跡
    record_file_seen(file_digest_hex, rec.receipt_id)
    existing = get_existing_for_file_sha1(file_digest_hex)

    if is_duplicated(rh):
        write_audit("INFO", "system", "duplicate_skip", [str(best_target.get("id")), rec.receipt_id], best_target.get("score", 0), "skipped")
        return None

    # 既に同一ファイルSHA1の証憑が存在する場合の安全な扱い
    # - 完全重複（同一sha1かつ同一receipt_hash）の場合のみ、allow_delete=Trueかつポリシーに合致すれば削除を許容
    if existing:
        # ここでは削除せず、監査のみ（デフォルト安全策）
        write_audit(
            "INFO",
            "system",
            "duplicate_detected",
            [str(best_target.get("id")), rec.receipt_id] + existing,
            best_target.get("score", 0),
            "detected",
        )

    result = link_receipt(
        freee_client,
        target_type=target_type,
        target_id=str(best_target.get("id")),
        receipt_id=rec.receipt_id,
    )
    mark_linked(
        rh,
        {
            "target_type": target_type,
            "target_id": best_target.get("id"),
            "receipt_id": rec.receipt_id,
            "score": best_target.get("score"),
            "file_sha1": file_digest_hex,
        },
    )
    write_audit("INFO", "system", "link", [str(best_target.get("id")), rec.receipt_id], best_target.get("score", 0), "linked")
    return result


def normalize_targets(wallet_txns: List[Dict], deals: List[Dict]) -> List[Dict]:
    """wallet_txn と deal を単一の候補配列に正規化する。
    出力: { id, type, amount, date, description|partner_name, tax_rate }
    """
    out: List[Dict] = []
    for tx in wallet_txns or []:
        item = {
            "id": tx.get("id"),
            "type": "wallet_txn",
            "amount": tx.get("amount"),
            "date": tx.get("date") or tx.get("record_date"),
            "description": tx.get("description"),
            "partner_name": None,
            "tax_rate": tx.get("tax_rate"),
        }
        out.append(item)
    for d in deals or []:
        # deal の場合は details から代表値を拾う（MVP: 先頭要素）
        details = (d.get("details") or [{}])
        detail0 = details[0] if details else {}
        item = {
            "id": d.get("id"),
            "type": "deal",
            "amount": detail0.get("amount", 0),
            "date": d.get("issue_date") or d.get("date"),
            "description": d.get("ref_number"),
            "partner_name": None,  # APIで引けるなら設定
            "tax_rate": detail0.get("tax_code"),  # 厳密には税コード→税率マップが必要
        }
        out.append(item)
    return out


def find_best_target(ocr: ReceiptRecord, targets: List[Dict], cfg: Dict) -> Optional[Dict]:
    from matcher import match_candidates

    candidates = match_candidates(ocr, targets, cfg)
    return candidates[0] if candidates else None


