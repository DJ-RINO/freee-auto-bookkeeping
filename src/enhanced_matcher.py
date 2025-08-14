#!/usr/bin/env python3
"""
OCR精度問題対応の強化マッチャー
低品質OCRデータでも効果的な紐付けを実現
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from rapidfuzz.distance import JaroWinkler
from difflib import SequenceMatcher

from ocr_models import ReceiptRecord, MatchCandidate
from vendor_mapping_learner import VendorMappingLearner
from ocr_quality_manager import OCRQualityManager

class EnhancedMatcher:
    """OCR品質問題に対応した強化マッチャー"""
    
    def __init__(self):
        self.learner = VendorMappingLearner()
        self.ocr_manager = OCRQualityManager()
        
        # 金額ベースマッチングの重み調整
        self.weights = {
            'high_ocr_quality': {  # OCR品質が高い場合
                'amount': 0.4,
                'date': 0.15,
                'name': 0.35,
                'tax_rate': 0.1
            },
            'low_ocr_quality': {   # OCR品質が低い場合
                'amount': 0.7,     # 金額重視
                'date': 0.2,       # 日付重視
                'name': 0.05,      # 名前は参考程度
                'tax_rate': 0.05
            }
        }
    
    def match_with_ocr_awareness(self, ocr_receipt: ReceiptRecord, tx_list: List[Dict], cfg: Dict) -> List[Dict]:
        """OCR品質を考慮したマッチング"""
        
        # 1. OCR品質評価
        receipt_data = {
            'id': ocr_receipt.receipt_id,
            'ocr_vendor': ocr_receipt.vendor,
            'amount': ocr_receipt.amount,
            'date': ocr_receipt.date.isoformat() if ocr_receipt.date else None
        }
        
        ocr_quality = self.ocr_manager.check_ocr_quality(receipt_data)
        enhanced_data = self.ocr_manager.enhance_receipt_data(receipt_data)
        
        print(f"  🔍 OCR品質: {ocr_quality.completion_score:.2f} ({'高品質' if ocr_quality.is_complete else '低品質'})")
        
        # 2. 品質に応じたマッチング戦略選択
        if ocr_quality.is_complete:
            return self._high_quality_matching(ocr_receipt, tx_list, cfg, enhanced_data)
        else:
            return self._low_quality_matching(ocr_receipt, tx_list, cfg, enhanced_data, ocr_quality)
    
    def _high_quality_matching(self, ocr_receipt: ReceiptRecord, tx_list: List[Dict], 
                              cfg: Dict, enhanced_data: Dict) -> List[Dict]:
        """高品質OCRデータの標準マッチング"""
        weights = self.weights['high_ocr_quality']
        min_sim = cfg.get("similarity", {}).get("min_candidate", 0.3)
        
        candidates = []
        for tx in tx_list:
            tx_description = tx.get("description", "") or tx.get("partner_name", "")
            
            # 学習データボーナス
            learned_bonus = self._get_learned_bonus(ocr_receipt.vendor, tx_description)
            
            # 基本類似度フィルター
            base_similarity = self._similarity(self._normalize_name(ocr_receipt.vendor), 
                                              self._normalize_name(tx_description))
            
            if base_similarity < min_sim and learned_bonus == 0:
                continue
            
            # スコア計算
            score = self._calculate_score(ocr_receipt, tx, cfg, weights)
            
            # 学習ボーナス適用
            if learned_bonus > 0:
                score = min(100, score + learned_bonus)
            
            candidates.append({
                "tx_id": str(tx.get("id")),
                "score": score,
                "reasons": [f"high_quality_ocr", f"similarity={base_similarity:.2f}"],
                "deltas": {
                    "amount": abs(ocr_receipt.amount - abs(tx.get("amount", 0))),
                    "date": tx.get("date"),
                    "name": tx_description
                }
            })
        
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:3]
    
    def _low_quality_matching(self, ocr_receipt: ReceiptRecord, tx_list: List[Dict], 
                             cfg: Dict, enhanced_data: Dict, ocr_quality) -> List[Dict]:
        """低品質OCRデータの特別マッチング"""
        weights = self.weights['low_ocr_quality']
        
        # 金額と日付を重視した候補選出
        amount_tolerance = max(1000, int(ocr_receipt.amount * 0.1))  # 10%または1000円
        date_tolerance = 60  # 2ヶ月
        
        print(f"  🔧 低品質OCR対応: 金額±{amount_tolerance}円, 日付±{date_tolerance}日")
        
        candidates = []
        for tx in tx_list:
            tx_amount = abs(tx.get("amount", 0))
            
            # OCR処理未完了の場合は金額0でもマッチング試行
            if ocr_receipt.amount == 0:
                amount_score = self._amount_fuzzy_match(tx_amount, enhanced_data)
            else:
                amount_diff = abs(ocr_receipt.amount - tx_amount)
                amount_score = 100 if amount_diff <= amount_tolerance else max(0, 100 - amount_diff // 100)
            
            # 日付マッチング（OCR日付が不正確な場合の対応）
            date_score = self._date_fuzzy_match(ocr_receipt, tx, enhanced_data, date_tolerance)
            
            # 名前マッチング（補強データ使用）
            name_score = self._name_fuzzy_match(ocr_receipt, tx, enhanced_data)
            
            # 総合スコア計算
            total_score = int(
                amount_score * weights['amount'] +
                date_score * weights['date'] +
                name_score * weights['name']
            )
            
            # 最低スコア要件（低品質OCRの場合は緩和）
            min_score = 30 if ocr_receipt.amount == 0 else 40
            
            if total_score >= min_score:
                reasons = [
                    f"low_quality_ocr_mode",
                    f"amount_score={amount_score}",
                    f"date_score={date_score}",
                    f"name_score={name_score}"
                ]
                
                candidates.append({
                    "tx_id": str(tx.get("id")),
                    "score": total_score,
                    "reasons": reasons,
                    "deltas": {
                        "amount": abs(ocr_receipt.amount - tx_amount) if ocr_receipt.amount > 0 else 0,
                        "date": tx.get("date"),
                        "name": tx.get("description", "") or tx.get("partner_name", ""),
                        "ocr_quality": ocr_quality.completion_score
                    }
                })
        
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:5]  # 低品質OCRの場合はより多くの候補を返す
    
    def _amount_fuzzy_match(self, tx_amount: int, enhanced_data: Dict) -> int:
        """OCR金額が0の場合のファジー金額マッチング"""
        # ファイル名から金額推定を試行
        file_name = enhanced_data.get('file_name', '')
        estimated_amount = self._extract_amount_from_filename(file_name)
        
        if estimated_amount and estimated_amount > 0:
            amount_diff = abs(estimated_amount - tx_amount)
            amount_tolerance = max(1000, int(estimated_amount * 0.2))  # 20%許容
            
            if amount_diff <= amount_tolerance:
                print(f"    💰 ファイル名から金額推定: {estimated_amount}円 (差額: {amount_diff}円)")
                return max(60, 100 - amount_diff // 100)
        
        # 金額範囲による推定マッチング
        if 1000 <= tx_amount <= 100000:  # 一般的なレシート金額範囲
            return 40
        elif 100 <= tx_amount <= 1000000:  # 広範囲
            return 20
        
        return 0
    
    def _date_fuzzy_match(self, ocr_receipt: ReceiptRecord, tx: Dict, 
                         enhanced_data: Dict, tolerance: int) -> int:
        """日付のファジーマッチング"""
        tx_date_str = tx.get("date") or tx.get("record_date") or tx.get("due_date")
        
        if not tx_date_str:
            return 0
        
        try:
            tx_date = datetime.strptime(tx_date_str, "%Y-%m-%d")
            
            # 補強された日付を優先使用
            receipt_date = enhanced_data.get('enhanced_date') or ocr_receipt.date
            if isinstance(receipt_date, str):
                receipt_date = datetime.strptime(receipt_date, "%Y-%m-%d").date()
            
            if receipt_date:
                date_diff = abs((tx_date.date() - receipt_date).days)
                if date_diff <= tolerance:
                    return max(50, 100 - date_diff)
            
            # ファイル名からの日付推定
            file_date = enhanced_data.get('enhanced_date')
            if file_date:
                file_date_obj = datetime.strptime(file_date, "%Y-%m-%d").date()
                file_date_diff = abs((tx_date.date() - file_date_obj).days)
                if file_date_diff <= tolerance:
                    print(f"    📅 ファイル名日付マッチ: {file_date} (差: {file_date_diff}日)")
                    return max(40, 100 - file_date_diff)
            
        except (ValueError, TypeError):
            pass
        
        return 0
    
    def _name_fuzzy_match(self, ocr_receipt: ReceiptRecord, tx: Dict, enhanced_data: Dict) -> int:
        """名前のファジーマッチング（補強データ使用）"""
        tx_name = tx.get("description", "") or tx.get("partner_name", "")
        
        # 補強されたvendor名を優先使用
        receipt_vendor = enhanced_data.get('enhanced_vendor') or ocr_receipt.vendor
        
        if not receipt_vendor or not tx_name:
            return 0
        
        # 通常の類似度
        similarity = self._similarity(self._normalize_name(receipt_vendor), 
                                     self._normalize_name(tx_name))
        
        # 部分一致も考慮
        partial_match = self._partial_similarity(receipt_vendor, tx_name)
        
        # より良いスコアを採用
        best_similarity = max(similarity, partial_match)
        
        return int(best_similarity * 100)
    
    def _extract_amount_from_filename(self, filename: str) -> Optional[int]:
        """ファイル名から金額を抽出"""
        if not filename:
            return None
        
        # 金額パターン（円、yen、数字など）
        amount_patterns = [
            r'(\d{1,3}(?:,\d{3})*)\s*[円¥]',  # 1,000円
            r'(\d+)\s*yen',                    # 1000yen
            r'amount[\-_](\d+)',               # amount-1000
            r'(\d{3,8})(?![yY])',              # 1000-99999999 (年と区別)
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount = int(amount_str)
                    
                    # 妥当性チェック
                    if 100 <= amount <= 10000000:  # 100円〜1000万円
                        return amount
                except ValueError:
                    continue
        
        return None
    
    def _partial_similarity(self, a: str, b: str) -> float:
        """部分文字列の類似度計算"""
        if not a or not b:
            return 0.0
        
        a_norm = self._normalize_name(a)
        b_norm = self._normalize_name(b)
        
        # 短い方を長い方に含まれるかチェック
        if len(a_norm) < len(b_norm):
            short, long = a_norm, b_norm
        else:
            short, long = b_norm, a_norm
        
        if len(short) >= 3 and short in long:
            return 0.8  # 部分一致スコア
        
        # シーケンスマッチングによる類似度
        return SequenceMatcher(None, a_norm, b_norm).ratio()
    
    def _get_learned_bonus(self, vendor: str, tx_description: str) -> int:
        """学習データボーナス計算"""
        if not tx_description or tx_description.strip() == "" or tx_description == "None":
            return 0
        
        learned_candidates = self.learner.get_vendor_candidates(tx_description)
        for candidate in learned_candidates:
            if self._similarity(self._normalize_name(vendor), 
                               self._normalize_name(candidate["vendor_name"])) > 0.7:
                return int(candidate["confidence"] * 30)
        
        return 0
    
    def _calculate_score(self, ocr_receipt: ReceiptRecord, tx: Dict, cfg: Dict, weights: Dict) -> int:
        """基本スコア計算"""
        # 金額スコア
        tx_amount = abs(tx.get("amount", 0))
        amount_diff = abs(ocr_receipt.amount - tx_amount)
        amount_tolerance = max(1000, int(ocr_receipt.amount * 0.05))
        amount_score = 100 if amount_diff <= amount_tolerance else 0
        
        # 日付スコア
        tx_date_str = tx.get("date") or tx.get("record_date") or tx.get("due_date")
        date_score = 0
        if tx_date_str:
            try:
                tx_date = datetime.strptime(tx_date_str, "%Y-%m-%d")
                date_diff = abs((ocr_receipt.date - tx_date.date()).days)
                date_score = 100 if date_diff <= 45 else 0
            except:
                pass
        
        # 名前スコア
        tx_name = tx.get("description", "") or tx.get("partner_name", "")
        name_similarity = self._similarity(self._normalize_name(ocr_receipt.vendor),
                                          self._normalize_name(tx_name))
        name_score = int(name_similarity * 100)
        
        # 総合スコア
        total = int(
            amount_score * weights.get("amount", 0.4) +
            date_score * weights.get("date", 0.25) +
            name_score * weights.get("name", 0.3) +
            0 * weights.get("tax_rate", 0.05)  # tax_rateは後で実装
        )
        
        return max(0, min(100, total))
    
    def _normalize_name(self, text: str) -> str:
        """名前正規化"""
        if not text:
            return ""
        s = text
        s = s.replace("（", "(").replace("）", ")")
        s = s.replace("株式会社", "").replace("(株)", "").replace("㈱", "")
        s = re.sub(r"\s+", "", s)
        s = s.upper()
        return s
    
    def _similarity(self, a: str, b: str) -> float:
        """文字列類似度計算"""
        if not a or not b:
            return 0.0
        return JaroWinkler.normalized_similarity(a, b)