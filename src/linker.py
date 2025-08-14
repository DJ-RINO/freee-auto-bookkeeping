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
from vendor_mapping_learner import VendorMappingLearner


def _receipt_hash(rec: ReceiptRecord, file_digest_hex: str) -> str:
    base = f"{rec.vendor.strip().upper()}|{rec.date.isoformat()}|{rec.amount}|{file_digest_hex}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def decide_action(score: int, cfg: Dict, ocr_quality_score: float = None) -> str:
    """OCR品質を考慮したアクション決定"""
    
    # OCR品質対応の閾値使用
    if ocr_quality_score is not None and cfg.get("ocr_adaptive_thresholds"):
        if ocr_quality_score >= 0.7:  # 高品質OCR
            th = cfg["ocr_adaptive_thresholds"]["high_quality"]
        else:  # 低品質OCR
            th = cfg["ocr_adaptive_thresholds"]["low_quality"]
    else:
        # 従来の閾値
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
    
    # 成功した場合は学習システムに記録
    if result:
        try:
            learner = VendorMappingLearner()
            bank_description = best_target.get("description", "") or best_target.get("partner_name", "")
            confidence = (best_target.get("score", 0) / 100.0)  # スコアを信頼度に変換
            
            learner.learn_mapping(
                bank_description=bank_description,
                vendor_name=rec.vendor,
                confidence=confidence
            )
            print(f"  🧠 マッピング学習完了: '{bank_description}' -> '{rec.vendor}' (信頼度: {confidence:.2f})")
        except Exception as e:
            print(f"  ⚠️ 学習エラー: {e}")
    
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
    
    print(f"  [マッチング] レシート: {ocr.vendor[:20]} / ¥{ocr.amount:,} / {ocr.date}")
    print(f"  [マッチング] 対象取引: {len(targets)}件")

    # OCR品質チェックと適応的マッチング
    try:
        from enhanced_matcher import EnhancedMatcher
        from ocr_quality_manager import OCRQualityManager
        
        ocr_manager = OCRQualityManager()
        receipt_data = {
            'id': ocr.receipt_id,
            'ocr_vendor': ocr.vendor,
            'amount': ocr.amount,
            'date': ocr.date.isoformat() if ocr.date else None
        }
        
        ocr_quality = ocr_manager.check_ocr_quality(receipt_data)
        
        # OCR品質が低い場合は強化マッチャーを使用
        if ocr_quality.completion_score < 0.7 or ocr.amount == 0:
            print(f"  🔧 OCR品質低下検出 (score={ocr_quality.completion_score:.2f}) - 強化マッチャー使用")
            enhanced_matcher = EnhancedMatcher()
            candidates = enhanced_matcher.match_with_ocr_awareness(ocr, targets, cfg)
        else:
            print(f"  ✅ OCR品質良好 (score={ocr_quality.completion_score:.2f}) - 標準マッチャー使用")
            candidates = match_candidates(ocr, targets, cfg)
        
        # OCR品質スコアを保存
        quality_score = ocr_quality.completion_score
            
    except ImportError as e:
        print(f"  ⚠️ 強化マッチャー利用不可、標準マッチャーを使用: {e}")
        candidates = match_candidates(ocr, targets, cfg)
        quality_score = None
    
    if candidates:
        best = candidates[0]
        print(f"  [マッチング] ベスト候補: score={best['score']}, 理由={best.get('reasons', [])}")
        # best辞書にIDが含まれているか確認
        target_id = best.get('tx_id') or best.get('id')
        if not target_id:
            print(f"  ❌ マッチング候補にIDが含まれていません: {best}")
            return None
        
        # best['deltas']['name']がNoneでないことを確認
        deltas_name = best.get('deltas', {}).get('name', 'N/A')
        if deltas_name is None:
            deltas_name = 'N/A'
        print(f"  [マッチング] デルタ: 金額差={best['deltas']['amount']}円, 名前='{deltas_name[:30]}'")
        
        # bestにIDを確実に含める
        if 'id' not in best and 'tx_id' in best:
            best['id'] = best['tx_id']
        
        # OCR品質スコアを追加
        best['ocr_quality_score'] = quality_score
        
        return best
    else:
        print(f"  [マッチング] 候補なし (min_similarity={cfg.get('similarity', {}).get('min_candidate', 0.6)})")
        
        # デバッグ: 最初の3件の取引との類似度をチェック
        from matcher import _normalize_name, _similarity
        for i, tx in enumerate(targets[:3]):
            tx_name = _normalize_name(tx.get("description", "") or tx.get("partner_name", ""))
            ocr_name = _normalize_name(ocr.vendor)
            sim = _similarity(ocr_name, tx_name)
            print(f"    取引{i+1}: '{tx.get('description', '')[:30]}' sim={sim:.3f} amount={tx.get('amount', 0)}")
        
        return None


