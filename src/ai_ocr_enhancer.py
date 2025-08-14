#!/usr/bin/env python
"""
AI OCR改善システム
OCR品質の低いレシートデータを人工知能で改善する
"""

import re
import json
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class AIEnhancementResult:
    """AI改善結果"""
    enhanced_vendor: str
    enhanced_amount: int
    confidence_score: float
    enhancement_reason: str

class AIReceiptEnhancer:
    """AI レシート改善クラス"""
    
    def __init__(self):
        """AI OCR改善システムを初期化"""
        self.vendor_patterns = self._load_vendor_patterns()
        self.amount_patterns = self._load_amount_patterns()
        
    def enhance_receipt_with_ai(self, receipt_data: Dict[str, Any], image_data: Optional[bytes] = None) -> AIEnhancementResult:
        """AIを使用してレシートデータを改善
        
        Args:
            receipt_data: レシートデータ
            image_data: 画像データ（オプション）
            
        Returns:
            AIEnhancementResult: 改善結果
        """
        # 現在の値を取得
        original_vendor = receipt_data.get('ocr_vendor', '')
        original_amount = receipt_data.get('amount', 0)
        
        # AI改善処理
        enhanced_vendor = self._enhance_vendor_name(receipt_data)
        enhanced_amount = self._enhance_amount(receipt_data)
        
        # 信頼度スコアを計算
        confidence_score = self._calculate_confidence_score(receipt_data, enhanced_vendor, enhanced_amount)
        
        # 改善理由を生成
        enhancement_reason = self._generate_enhancement_reason(original_vendor, enhanced_vendor, original_amount, enhanced_amount)
        
        return AIEnhancementResult(
            enhanced_vendor=enhanced_vendor,
            enhanced_amount=enhanced_amount,
            confidence_score=confidence_score,
            enhancement_reason=enhancement_reason
        )
    
    def _enhance_vendor_name(self, receipt_data: Dict[str, Any]) -> str:
        """ベンダー名を改善"""
        # 複数のフィールドから情報を収集
        sources = [
            receipt_data.get('ocr_vendor', ''),
            receipt_data.get('file_name', ''),
            receipt_data.get('memo', ''),
            receipt_data.get('description', ''),
            receipt_data.get('user_name', '')
        ]
        
        # 空でない最初の値を取得
        for source in sources:
            if source and source.strip():
                # パターンマッチングで改善
                enhanced = self._apply_vendor_patterns(source.strip())
                if enhanced:
                    return enhanced
                return source.strip()
        
        # 何も見つからない場合のデフォルト
        return f"レシート#{receipt_data.get('id', 'unknown')}"
    
    def _enhance_amount(self, receipt_data: Dict[str, Any]) -> int:
        """金額を改善"""
        # 既に金額がある場合はそのまま返す
        current_amount = receipt_data.get('amount', 0)
        if current_amount > 0:
            return current_amount
        
        # ファイル名、メモ、説明から金額を抽出
        sources = [
            receipt_data.get('file_name', ''),
            receipt_data.get('memo', ''),
            receipt_data.get('description', '')
        ]
        
        for source in sources:
            if source:
                amount = self._extract_amount_from_text(source)
                if amount > 0:
                    return amount
        
        return 0
    
    def _apply_vendor_patterns(self, vendor_text: str) -> str:
        """ベンダー名パターンを適用"""
        # 一般的な店舗名の正規化
        patterns = {
            r'セブン[イー]*レブン|7[・-]*eleven|7ELEVEn': 'セブン-イレブン',
            r'ファミリー[マー]*ト|familymart': 'ファミリーマート',
            r'ローソン|lawson': 'ローソン',
            r'ミニストップ|ministop': 'ミニストップ',
            r'マクドナルド|McDonald|McD': 'マクドナルド',
            r'スターバックス|Starbucks|スタバ': 'スターバックス',
            r'ドトール|DOUTOR': 'ドトールコーヒー',
            r'コメダ珈琲|Komeda': 'コメダ珈琲店',
            r'すき家|sukiya': 'すき家',
            r'松屋|matsuya': '松屋',
            r'吉野家|yoshinoya': '吉野家',
            r'ガスト|Gusto': 'ガスト',
            r'サイゼリヤ|Saizeriya': 'サイゼリヤ',
            r'イオン|AEON': 'イオン',
            r'西友|SEIYU': '西友',
            r'イトーヨーカドー|Ito.Yokado': 'イトーヨーカドー',
        }
        
        vendor_lower = vendor_text.lower()
        for pattern, normalized_name in patterns.items():
            if re.search(pattern, vendor_text, re.IGNORECASE):
                return normalized_name
        
        # パターンにマッチしない場合は元の文字列を返す
        return vendor_text
    
    def _extract_amount_from_text(self, text: str) -> int:
        """テキストから金額を抽出"""
        # 金額パターン
        patterns = [
            r'([0-9,]+)円',
            r'¥([0-9,]+)',
            r'\$([0-9,]+)',
            r'([0-9,]+)\s*JPY',
            r'([0-9,]+)\s*yen',
            r'合計[：:]\s*([0-9,]+)',
            r'total[：:]\s*([0-9,]+)',
            r'([0-9,]+)\s*合計',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '').replace(' ', '')
                try:
                    amount = int(amount_str)
                    # 妥当な金額範囲かチェック（1円～100万円）
                    if 1 <= amount <= 1000000:
                        return amount
                except ValueError:
                    continue
        
        return 0
    
    def _calculate_confidence_score(self, receipt_data: Dict[str, Any], enhanced_vendor: str, enhanced_amount: int) -> float:
        """信頼度スコアを計算"""
        score = 0.0
        
        # ベンダー名の信頼度
        original_vendor = receipt_data.get('ocr_vendor', '')
        if enhanced_vendor and not enhanced_vendor.startswith('レシート#'):
            score += 0.4
            # パターンマッチした場合は追加ポイント
            if enhanced_vendor != original_vendor and original_vendor:
                score += 0.2
        
        # 金額の信頼度
        original_amount = receipt_data.get('amount', 0)
        if enhanced_amount > 0:
            score += 0.3
            # 新しく抽出した場合は追加ポイント
            if original_amount == 0:
                score += 0.1
        
        # 複数の情報源がある場合は信頼度向上
        info_sources = [
            receipt_data.get('file_name', ''),
            receipt_data.get('memo', ''),
            receipt_data.get('description', ''),
            receipt_data.get('user_name', '')
        ]
        available_sources = len([s for s in info_sources if s and s.strip()])
        if available_sources >= 2:
            score += 0.1
        
        return min(1.0, score)
    
    def _generate_enhancement_reason(self, original_vendor: str, enhanced_vendor: str, original_amount: int, enhanced_amount: int) -> str:
        """改善理由を生成"""
        reasons = []
        
        if enhanced_vendor != original_vendor:
            if enhanced_vendor and not enhanced_vendor.startswith('レシート#'):
                reasons.append(f"店舗名改善: '{original_vendor}' → '{enhanced_vendor}'")
            else:
                reasons.append("店舗名を代替情報から推定")
        
        if enhanced_amount != original_amount:
            if original_amount == 0 and enhanced_amount > 0:
                reasons.append(f"金額抽出: ¥{enhanced_amount:,}")
            elif enhanced_amount != original_amount:
                reasons.append(f"金額修正: ¥{original_amount:,} → ¥{enhanced_amount:,}")
        
        if not reasons:
            reasons.append("既存データを検証")
        
        return "; ".join(reasons)
    
    def _load_vendor_patterns(self) -> Dict[str, str]:
        """ベンダーパターンを読み込み"""
        # 実装：データファイルから読み込み、またはハードコーディング
        return {}
    
    def _load_amount_patterns(self) -> List[str]:
        """金額パターンを読み込み"""
        # 実装：パターンファイルから読み込み、またはハードコーディング
        return []