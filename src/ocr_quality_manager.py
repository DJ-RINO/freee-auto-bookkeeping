#!/usr/bin/env python3
"""
OCR品質管理システム
freeeファイルボックスのOCR処理完了状況の監視と品質向上
"""

import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class OCRQualityCheck:
    """OCR品質チェック結果"""
    receipt_id: str
    is_complete: bool
    completion_score: float  # 0.0-1.0
    issues: List[str]
    suggestions: List[str]

class OCRQualityManager:
    """OCR品質管理クラス"""
    
    def __init__(self):
        self.ocr_patterns = {
            # OCR処理未完了を示すパターン
            'incomplete_patterns': [
                r'^レシート#\d+$',        # "レシート#123456"
                r'^receipt_\d+$',         # "receipt_123456"
                r'^img_\d+$',             # "img_123456"
                r'^\d{8,}$',              # 数字のみ8桁以上
            ],
            
            # 低品質OCRを示すパターン
            'low_quality_patterns': [
                r'[^\w\s\-\(\)\,\.\@]',   # 異常な文字
                r'\w{20,}',               # 異常に長い文字列
                r'^[\d\s\-\.]{10,}$',     # 数字・記号のみの長い文字列
            ],
            
            # 信頼できるvendorパターン
            'reliable_patterns': [
                r'株式会社',
                r'合同会社',
                r'有限会社',
                r'\(株\)|\㈱',
                r'Co\.?Ltd\.?',
                r'Inc\.?',
            ]
        }
    
    def check_ocr_quality(self, receipt_data: Dict) -> OCRQualityCheck:
        """OCR品質をチェック"""
        receipt_id = receipt_data.get('id', 'unknown')
        issues = []
        suggestions = []
        completion_score = 0.0
        
        # 基本データ取得
        ocr_vendor = receipt_data.get('ocr_vendor', '') or ''
        file_name = receipt_data.get('file_name', '') or ''
        amount = receipt_data.get('amount', 0)
        
        # 1. 金額チェック（最重要）
        if amount == 0:
            issues.append("金額情報なし（OCR処理未完了の可能性）")
            suggestions.append("freee管理画面でOCR処理状況を確認")
        else:
            completion_score += 0.4
        
        # 2. vendor名チェック
        vendor_score = self._check_vendor_quality(ocr_vendor, file_name)
        completion_score += vendor_score * 0.4
        
        if vendor_score < 0.3:
            issues.append(f"vendor名の品質が低い: '{ocr_vendor}'")
            suggestions.append("ファイル名やメモ欄の情報を活用")
        
        # 3. 日付チェック
        date_score = self._check_date_quality(receipt_data)
        completion_score += date_score * 0.2
        
        if date_score < 0.5:
            issues.append("日付情報の品質が低い")
            suggestions.append("ファイル名からの日付推定を活用")
        
        # 完了判定
        is_complete = completion_score > 0.7 and amount > 0
        
        return OCRQualityCheck(
            receipt_id=receipt_id,
            is_complete=is_complete,
            completion_score=completion_score,
            issues=issues,
            suggestions=suggestions
        )
    
    def _check_vendor_quality(self, ocr_vendor: str, file_name: str) -> float:
        """vendor名の品質チェック（0.0-1.0）"""
        if not ocr_vendor:
            return 0.0
        
        # OCR処理未完了パターンチェック
        for pattern in self.ocr_patterns['incomplete_patterns']:
            if re.match(pattern, ocr_vendor, re.IGNORECASE):
                return 0.0
        
        # 低品質パターンチェック
        for pattern in self.ocr_patterns['low_quality_patterns']:
            if re.search(pattern, ocr_vendor):
                return 0.2
        
        # 信頼できるパターンチェック
        for pattern in self.ocr_patterns['reliable_patterns']:
            if re.search(pattern, ocr_vendor, re.IGNORECASE):
                return 1.0
        
        # 長さベースの品質推定
        if len(ocr_vendor) < 2:
            return 0.1
        elif len(ocr_vendor) < 5:
            return 0.4
        else:
            return 0.7
    
    def _check_date_quality(self, receipt_data: Dict) -> float:
        """日付品質チェック（0.0-1.0）"""
        ocr_date = receipt_data.get('date')
        created_at = receipt_data.get('created_at')
        
        if not ocr_date:
            return 0.0
        
        try:
            # 現在から2年以内かチェック
            if isinstance(ocr_date, str):
                date_obj = datetime.fromisoformat(ocr_date.replace('Z', '+00:00'))
            else:
                date_obj = ocr_date
            
            days_ago = (datetime.now() - date_obj.replace(tzinfo=None)).days
            
            if 0 <= days_ago <= 365:  # 1年以内
                return 1.0
            elif 365 < days_ago <= 730:  # 2年以内
                return 0.8
            else:
                return 0.3
        except:
            return 0.2
    
    def enhance_receipt_data(self, receipt_data: Dict) -> Dict:
        """OCRデータを補強"""
        enhanced = receipt_data.copy()
        
        # ファイル名からvendor推定
        file_name = receipt_data.get('file_name', '')
        ocr_vendor = receipt_data.get('ocr_vendor', '') or ''
        
        if self._check_vendor_quality(ocr_vendor, file_name) < 0.3 and file_name:
            enhanced_vendor = self._extract_vendor_from_filename(file_name)
            if enhanced_vendor:
                enhanced['enhanced_vendor'] = enhanced_vendor
                print(f"  🔧 vendor補強: '{ocr_vendor}' → '{enhanced_vendor}' (from filename)")
        
        # ファイル名から日付推定
        if not receipt_data.get('date') or self._check_date_quality(receipt_data) < 0.5:
            enhanced_date = self._extract_date_from_filename(file_name)
            if enhanced_date:
                enhanced['enhanced_date'] = enhanced_date
                print(f"  🔧 日付補強: ファイル名から {enhanced_date} を推定")
        
        return enhanced
    
    def _extract_vendor_from_filename(self, filename: str) -> Optional[str]:
        """ファイル名からvendor名を抽出"""
        if not filename:
            return None
        
        # 一般的なvendor名パターン
        vendor_patterns = [
            r'([^\d\-\_\.\s]+(?:株式会社|合同会社|有限会社|\(株\)|\㈱))',
            r'([A-Za-z]+(?:Co\.?Ltd\.?|Inc\.?|Corp\.?))',
            r'([^\d\-\_\.]{3,})',  # 英数字以外の3文字以上
        ]
        
        filename_clean = filename.replace('_', ' ').replace('-', ' ')
        
        for pattern in vendor_patterns:
            match = re.search(pattern, filename_clean, re.IGNORECASE)
            if match:
                vendor = match.group(1).strip()
                if len(vendor) >= 3:
                    return vendor
        
        return None
    
    def _extract_date_from_filename(self, filename: str) -> Optional[str]:
        """ファイル名から日付を抽出"""
        if not filename:
            return None
        
        # 日付パターン（YYYY-MM-DD, YYYYMMDD など）
        date_patterns = [
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
            r'(\d{4})_(\d{1,2})_(\d{1,2})',
            r'(\d{4})(\d{2})(\d{2})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, filename)
            if match:
                try:
                    year = int(match.group(1))
                    month = int(match.group(2))
                    day = int(match.group(3))
                    
                    # 妥当性チェック
                    if 2020 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
                        return f"{year:04d}-{month:02d}-{day:02d}"
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def suggest_ocr_improvements(self, receipt_data: Dict) -> List[str]:
        """OCR改善提案"""
        suggestions = []
        quality = self.check_ocr_quality(receipt_data)
        
        if quality.completion_score < 0.5:
            suggestions.append("💡 freee管理画面で証憑を再アップロードしてOCR処理をやり直す")
            suggestions.append("💡 より高解像度の画像をアップロードする")
            suggestions.append("💡 メモ欄に店舗名・金額を手動で記載する")
        
        if quality.completion_score < 0.3:
            suggestions.append("💡 手動入力による取引作成を検討")
            suggestions.append("💡 学習データへの手動マッピング追加")
        
        return suggestions

# 使用例とテスト
def test_ocr_quality():
    """OCR品質管理のテスト"""
    manager = OCRQualityManager()
    
    # テストケース
    test_cases = [
        {
            'id': '328979267',
            'ocr_vendor': 'CANNABIS JAPAN合同会社',
            'amount': 200000,
            'date': '2025-04-09',
            'file_name': '2025-04-09_cannabis_receipt.pdf'
        },
        {
            'id': '331122062',
            'ocr_vendor': 'レシート#331122062',
            'amount': 0,
            'date': None,
            'file_name': 'IMG_20250601_123456.jpg'
        }
    ]
    
    print("=== OCR品質管理テスト ===")
    for case in test_cases:
        quality = manager.check_ocr_quality(case)
        enhanced = manager.enhance_receipt_data(case)
        
        print(f"\nレシート #{case['id']}:")
        print(f"  完了度: {quality.completion_score:.2f}")
        print(f"  完了: {'✅' if quality.is_complete else '❌'}")
        print(f"  問題: {', '.join(quality.issues)}")
        print(f"  提案: {', '.join(quality.suggestions)}")

if __name__ == "__main__":
    test_ocr_quality()