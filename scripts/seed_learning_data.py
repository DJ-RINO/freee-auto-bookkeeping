#!/usr/bin/env python
"""
学習システムに初期データを投入
GitHub Actionsで確認されたパターンを事前学習
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vendor_mapping_learner import VendorMappingLearner


def seed_initial_data():
    """GitHub Actionsで確認された実際のパターンを学習"""
    learner = VendorMappingLearner()
    
    # 実際のGitHub Actionsログから抽出したパターン
    known_mappings = [
        # 振込表記, 店舗名, 信頼度
        ("振込 カ）コ−ヒ−ロ−ストビバ−チエ", "株式会社コーヒーローストビバーチェ", 0.95),
        ("振込 カ）コ−ヒ−ロ−ストビバ−チエ", "コーヒーローストビバーチェ", 0.90),
        ("ヤマト運輸株式会社", "ヤマト運輸株式会社", 0.98),
        ("振込 カ）オ−シ−エス", "株式会社OCS", 0.85),
        
        # よくある銀行振込パターン
        ("振込 アマゾン", "Amazon", 0.90),
        ("振込 グ−グル", "Google", 0.90),
        ("振込 マイクロソフト", "Microsoft", 0.90),
        ("Vデビット　AMAZON.CO.JP", "Amazon", 0.85),
        ("Vデビット　GOOGLE", "Google", 0.85),
        ("カード利用　セブンイレブン", "セブンイレブン", 0.90),
        ("カード利用　ファミマ", "ファミリーマート", 0.90),
        
        # 法人格のバリエーション
        ("振込 カ）", "株式会社", 0.30),  # 一般的なパターン（低信頼度）
        ("振込 ユ）", "有限会社", 0.30),
        ("振込 ド）", "合同会社", 0.30),
        
        # GitHub Actionsで見つかった具体例
        ("振込 カ）オ−シ−エス", "OCS", 0.80),
        ("CURSOR, AI POWERED IDE", "Cursor", 0.75),
        ("jp.plaud.ai", "Plaud", 0.70),
        ("CANNABIS JAPAN合同会社", "CANNABIS JAPAN合同会社", 0.95),
        ("株式会社 グリーンブラザーズ・ジャパン", "グリーンブラザーズ・ジャパン", 0.95),
        ("Recalmo合同会社", "Recalmo合同会社", 0.95),
        ("Grassland Trading LLC.", "Grassland Trading LLC", 0.95),
        ("chill spice cbd", "chill spice cbd", 0.95),
    ]
    
    print("=== 初期学習データの投入 ===")
    for bank_desc, vendor, confidence in known_mappings:
        learner.learn_mapping(bank_desc, vendor, confidence)
    
    print(f"\n✅ {len(known_mappings)}件の初期データを学習完了")
    
    # 統計表示
    stats = learner.get_statistics()
    print(f"マッピング数: {stats['total_mappings']}")
    print(f"店舗数: {stats['total_vendors']}")
    print(f"高信頼度マッピング: {stats['high_confidence_mappings']}")
    
    # 検索テスト
    print("\n=== 検索テスト ===")
    test_cases = [
        "振込 カ）コ−ヒ−ロ−スト",
        "コーヒーローストビバーチェ",
        "AMAZON",
        "株式会社OCS"
    ]
    
    for query in test_cases:
        print(f"\n🔍 '{query}'")
        candidates = learner.get_vendor_candidates(query)
        for i, candidate in enumerate(candidates[:3], 1):
            print(f"  {i}. {candidate['vendor_name']} (信頼度: {candidate['confidence']:.2f}, {candidate['match_type']})")


if __name__ == "__main__":
    seed_initial_data()