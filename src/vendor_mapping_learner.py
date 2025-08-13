#!/usr/bin/env python
"""
振込先-店舗名マッピング学習システム
成功した紐付けを学習し、次回以降のマッチング精度を向上
"""

import json
import os
from typing import Dict, List, Optional, Set
from datetime import datetime
from pathlib import Path


class VendorMappingLearner:
    """振込先と店舗名のマッピングを学習・蓄積するクラス"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.mapping_file = self.data_dir / "vendor_mappings.json"
        self.mappings = self._load_mappings()
    
    def _load_mappings(self) -> Dict:
        """保存されたマッピングデータを読み込み"""
        if self.mapping_file.exists():
            try:
                with open(self.mapping_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"マッピング読み込みエラー: {e}")
        
        return {
            "bank_to_vendor": {},  # 振込表記 → 正式店舗名
            "vendor_to_bank": {},  # 正式店舗名 → 振込表記リスト
            "confidence": {},      # マッピングの信頼度
            "last_updated": {},    # 最終更新日
            "success_count": {}    # 成功回数
        }
    
    def _save_mappings(self):
        """マッピングデータを保存"""
        try:
            with open(self.mapping_file, 'w', encoding='utf-8') as f:
                json.dump(self.mappings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"マッピング保存エラー: {e}")
    
    def learn_mapping(self, bank_description: str, vendor_name: str, confidence: float = 1.0):
        """成功したマッピングを学習"""
        now = datetime.now().isoformat()
        
        # 正規化（銀行表記から不要な文字を削除）
        bank_key = self._normalize_bank_description(bank_description)
        vendor_key = self._normalize_vendor_name(vendor_name)
        
        if not bank_key or not vendor_key:
            return
        
        # bank_to_vendor マッピング
        if bank_key in self.mappings["bank_to_vendor"]:
            # 既存のマッピングと一致するか確認
            existing_vendor = self.mappings["bank_to_vendor"][bank_key]
            if existing_vendor != vendor_key:
                print(f"⚠️ マッピング競合: {bank_key} -> {existing_vendor} vs {vendor_key}")
        
        self.mappings["bank_to_vendor"][bank_key] = vendor_key
        
        # vendor_to_bank マッピング（1つの店舗に複数の振込表記）
        if vendor_key not in self.mappings["vendor_to_bank"]:
            self.mappings["vendor_to_bank"][vendor_key] = []
        
        if bank_key not in self.mappings["vendor_to_bank"][vendor_key]:
            self.mappings["vendor_to_bank"][vendor_key].append(bank_key)
        
        # メタデータ更新
        mapping_id = f"{bank_key}->{vendor_key}"
        self.mappings["confidence"][mapping_id] = confidence
        self.mappings["last_updated"][mapping_id] = now
        self.mappings["success_count"][mapping_id] = self.mappings["success_count"].get(mapping_id, 0) + 1
        
        self._save_mappings()
        
        print(f"✅ マッピング学習: '{bank_description}' -> '{vendor_name}' (信頼度: {confidence:.2f})")
    
    def get_vendor_candidates(self, bank_description: str) -> List[Dict]:
        """振込表記から店舗名候補を取得"""
        bank_key = self._normalize_bank_description(bank_description)
        candidates = []
        
        # 完全一致
        if bank_key in self.mappings["bank_to_vendor"]:
            vendor_key = self.mappings["bank_to_vendor"][bank_key]
            mapping_id = f"{bank_key}->{vendor_key}"
            confidence = self.mappings["confidence"].get(mapping_id, 1.0)
            success_count = self.mappings["success_count"].get(mapping_id, 1)
            
            candidates.append({
                "vendor_name": self._denormalize_vendor_name(vendor_key),
                "bank_description": bank_description,
                "confidence": confidence,
                "success_count": success_count,
                "match_type": "exact"
            })
        
        # 部分一致（振込表記の一部が含まれる）
        for stored_bank_key, vendor_key in self.mappings["bank_to_vendor"].items():
            if stored_bank_key != bank_key and (
                bank_key in stored_bank_key or stored_bank_key in bank_key
            ):
                mapping_id = f"{stored_bank_key}->{vendor_key}"
                confidence = self.mappings["confidence"].get(mapping_id, 1.0) * 0.8  # 部分一致は信頼度減
                success_count = self.mappings["success_count"].get(mapping_id, 1)
                
                candidates.append({
                    "vendor_name": self._denormalize_vendor_name(vendor_key),
                    "bank_description": self._denormalize_bank_description(stored_bank_key),
                    "confidence": confidence,
                    "success_count": success_count,
                    "match_type": "partial"
                })
        
        # 信頼度とマッチタイプでソート
        candidates.sort(key=lambda x: (x["match_type"] == "exact", x["confidence"], x["success_count"]), reverse=True)
        return candidates[:5]  # 上位5候補
    
    def get_bank_candidates(self, vendor_name: str) -> List[str]:
        """店舗名から振込表記候補を取得"""
        vendor_key = self._normalize_vendor_name(vendor_name)
        return self.mappings["vendor_to_bank"].get(vendor_key, [])
    
    def _normalize_bank_description(self, description: str) -> str:
        """振込表記を正規化"""
        if not description:
            return ""
        
        # よくある振込表記パターンを正規化
        normalized = description.upper().strip()
        
        # 振込プレフィックスを削除
        prefixes = ["振込 ", "フリコミ ", "Vデビット　", "カード利用　"]
        for prefix in prefixes:
            if normalized.startswith(prefix.upper()):
                normalized = normalized[len(prefix):].strip()
        
        # カッコと記号を整理
        normalized = normalized.replace("カ）", "").replace("(株)", "").replace("㈱", "")
        normalized = normalized.replace("　", " ").replace("  ", " ").strip()
        
        return normalized
    
    def _denormalize_bank_description(self, key: str) -> str:
        """正規化キーから表示用文字列を復元"""
        return key  # 簡略化
    
    def _normalize_vendor_name(self, name: str) -> str:
        """店舗名を正規化"""
        if not name:
            return ""
        
        normalized = name.strip()
        # 会社表記の統一
        normalized = normalized.replace("株式会社", "").replace("(株)", "").replace("㈱", "")
        normalized = normalized.replace("合同会社", "").replace("有限会社", "")
        normalized = normalized.upper().strip()
        
        return normalized
    
    def _denormalize_vendor_name(self, key: str) -> str:
        """正規化キーから表示用店舗名を復元"""
        return key  # 簡略化（実際には元の表記を保存することも可能）
    
    def get_statistics(self) -> Dict:
        """学習統計を取得"""
        return {
            "total_mappings": len(self.mappings["bank_to_vendor"]),
            "total_vendors": len(self.mappings["vendor_to_bank"]),
            "high_confidence_mappings": len([
                k for k, v in self.mappings["confidence"].items() if v >= 0.9
            ]),
            "most_successful": sorted([
                (k, v) for k, v in self.mappings["success_count"].items()
            ], key=lambda x: x[1], reverse=True)[:5]
        }
    
    def export_for_matching(self) -> Dict:
        """マッチングアルゴリズム用にデータをエクスポート"""
        return {
            "bank_to_vendor": self.mappings["bank_to_vendor"],
            "confidence": self.mappings["confidence"],
            "success_count": self.mappings["success_count"]
        }


def test_vendor_mapping_learner():
    """テスト実行"""
    learner = VendorMappingLearner("test_data")
    
    # 学習データの追加
    test_cases = [
        ("振込 カ）コ−ヒ−ロ−ストビバ−チエ", "株式会社コーヒーローストビバーチェ", 0.95),
        ("振込 ヤマト", "ヤマト運輸株式会社", 0.90),
        ("Vデビット　AMAZON.CO.JP", "Amazon", 0.85),
        ("振込 カ）オ−シ−エス", "株式会社OCS", 0.88)
    ]
    
    for bank_desc, vendor, confidence in test_cases:
        learner.learn_mapping(bank_desc, vendor, confidence)
    
    # テスト検索
    print("\n=== 検索テスト ===")
    test_queries = [
        "振込 カ）コ−ヒ−ロ−スト",
        "ヤマト運輸",
        "AMAZON"
    ]
    
    for query in test_queries:
        print(f"\n検索: '{query}'")
        candidates = learner.get_vendor_candidates(query)
        for candidate in candidates:
            print(f"  -> {candidate['vendor_name']} (信頼度: {candidate['confidence']:.2f}, {candidate['match_type']})")
    
    # 統計表示
    stats = learner.get_statistics()
    print(f"\n統計: マッピング数={stats['total_mappings']}, 店舗数={stats['total_vendors']}")


if __name__ == "__main__":
    test_vendor_mapping_learner()