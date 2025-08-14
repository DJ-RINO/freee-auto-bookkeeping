#!/usr/bin/env python3
"""
実際のOCR問題パターンに基づいた改善効果テスト
GitHub Actionsで確認された実データパターンを使用
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from datetime import date
from ocr_models import ReceiptRecord

# 実際のOCR問題パターン（GitHub Actions分析結果）
REALISTIC_OCR_PATTERNS = [
    # 1. 高品質OCR（成功例）- 26%のみ
    {
        'receipt_id': '328979267',
        'vendor': 'CANNABIS JAPAN合同会社',
        'amount': 200000,
        'date': date(2025, 4, 9),
        'file_name': '2025-04-09_cannabis_receipt.pdf',
        'expected_quality': 'high'
    },
    {
        'receipt_id': '328979348', 
        'vendor': '株式会社 グリーンブラザーズ・ジャパン',
        'amount': 41600,
        'date': date(2025, 4, 10),
        'file_name': 'green_brothers_invoice.pdf',
        'expected_quality': 'high'
    },
    
    # 2. OCR処理未完了（¥0）- 74%の大部分
    {
        'receipt_id': '331122062',
        'vendor': 'レシート#331122062',
        'amount': 0,
        'date': date(2025, 6, 1),
        'file_name': 'IMG_20250601_starbucks_receipt.jpg',
        'expected_quality': 'low'
    },
    {
        'receipt_id': '351211310',
        'vendor': 'レシート#351211310', 
        'amount': 0,
        'date': date(2025, 8, 12),
        'file_name': '2025-08-12_amazon_purchase_1280yen.jpg',
        'expected_quality': 'low'
    },
    {
        'receipt_id': '351211401',
        'vendor': 'レシート#351211401',
        'amount': 0,
        'date': date(2025, 8, 13),
        'file_name': 'convenience_store_650.jpg',
        'expected_quality': 'low'
    },
    
    # 3. 文字化けOCR
    {
        'receipt_id': '334455566',
        'vendor': 'ス夕一バツヲス コーヒー',
        'amount': 68,  # 680円の誤認識
        'date': date(2025, 7, 15),
        'file_name': '2025-07-15_starbucks_morning.jpg',
        'expected_quality': 'medium'
    },
    {
        'receipt_id': '334455789',
        'vendor': 'アマゾン',
        'amount': 128,  # 1280円の誤認識
        'date': date(2025, 7, 20),
        'file_name': 'amazon_book_order_1280.pdf',
        'expected_quality': 'medium'
    }
]

# 対応する取引データ
MOCK_TRANSACTIONS = [
    {
        'id': 'TX001',
        'description': 'スターバックス コーヒー ジャパン 株式会社',
        'amount': -680,
        'date': '2025-06-01',
        'partner_name': 'スターバックス'
    },
    {
        'id': 'TX002',
        'description': 'Amazon.co.jp',
        'amount': -1280,
        'date': '2025-08-12',
        'partner_name': 'アマゾン'
    },
    {
        'id': 'TX003',
        'description': 'ファミリーマート',
        'amount': -650,
        'date': '2025-08-13',
        'partner_name': 'コンビニ'
    },
    {
        'id': 'TX004',
        'description': 'CANNABIS JAPAN合同会社',
        'amount': -200000,
        'date': '2025-04-09'
    },
    {
        'id': 'TX005',
        'description': '株式会社 グリーンブラザーズ・ジャパン', 
        'amount': -41600,
        'date': '2025-04-10'
    },
    {
        'id': 'TX006',
        'description': 'スターバックス',
        'amount': -680,
        'date': '2025-07-15'
    }
]

# 設定（OCR対応）
ENHANCED_CONFIG = {
    'thresholds': {'auto': 70, 'assist_min': 50, 'assist_max': 69},
    'ocr_adaptive_thresholds': {
        'high_quality': {'auto': 70, 'assist_min': 50, 'assist_max': 69},
        'low_quality': {'auto': 45, 'assist_min': 30, 'assist_max': 44}
    },
    'similarity': {'min_candidate': 0.3},
    'tolerances': {'amount_jpy': 1000, 'days': 45}
}

def test_before_improvements():
    """改善前のマッチング結果をシミュレート"""
    print("=" * 60)
    print("📊 改善前のマッチング結果（従来システム）")
    print("=" * 60)
    
    from matcher import match_candidates
    
    results = {'auto': 0, 'assist': 0, 'manual': 0}
    
    for pattern in REALISTIC_OCR_PATTERNS:
        receipt = ReceiptRecord(
            receipt_id=pattern['receipt_id'],
            file_hash='dummy',
            vendor=pattern['vendor'],
            date=pattern['date'],
            amount=pattern['amount']
        )
        
        print(f"\n🏪 {pattern['receipt_id']}: {pattern['vendor'][:30]}")
        print(f"💰 金額: ¥{pattern['amount']:,}")
        
        # 従来のマッチング
        candidates = match_candidates(receipt, MOCK_TRANSACTIONS, ENHANCED_CONFIG)
        
        if candidates:
            best_score = candidates[0]['score']
            print(f"📊 ベストスコア: {best_score}点")
            
            # 従来の閾値（高い）で判定
            if best_score >= 70:
                action = 'AUTO'
                results['auto'] += 1
            elif 50 <= best_score <= 69:
                action = 'ASSIST'
                results['assist'] += 1
            else:
                action = 'MANUAL'
                results['manual'] += 1
        else:
            action = 'MANUAL'
            results['manual'] += 1
            print(f"📊 マッチング候補なし")
        
        print(f"🎯 判定: {action}")
    
    print(f"\n" + "=" * 40)
    print(f"📈 改善前の結果:")
    print(f"  自動紐付け: {results['auto']}件 ({results['auto']/len(REALISTIC_OCR_PATTERNS)*100:.1f}%)")
    print(f"  人間確認: {results['assist']}件 ({results['assist']/len(REALISTIC_OCR_PATTERNS)*100:.1f}%)")
    print(f"  手動対応: {results['manual']}件 ({results['manual']/len(REALISTIC_OCR_PATTERNS)*100:.1f}%)")
    
    return results

def test_after_improvements():
    """改善後のマッチング結果をテスト"""
    print("\n" + "=" * 60)
    print("🚀 改善後のマッチング結果（OCR対応システム）")
    print("=" * 60)
    
    try:
        from enhanced_matcher import EnhancedMatcher
        from linker import decide_action
        
        enhanced_matcher = EnhancedMatcher()
        results = {'auto': 0, 'assist': 0, 'manual': 0}
        
        for pattern in REALISTIC_OCR_PATTERNS:
            receipt = ReceiptRecord(
                receipt_id=pattern['receipt_id'],
                file_hash='dummy',
                vendor=pattern['vendor'],
                date=pattern['date'],
                amount=pattern['amount']
            )
            
            print(f"\n🏪 {pattern['receipt_id']}: {pattern['vendor'][:30]}")
            print(f"💰 金額: ¥{pattern['amount']:,}")
            
            # OCR対応強化マッチング
            candidates = enhanced_matcher.match_with_ocr_awareness(
                receipt, MOCK_TRANSACTIONS, ENHANCED_CONFIG
            )
            
            if candidates:
                best = candidates[0]
                score = best['score']
                ocr_quality = best.get('ocr_quality_score', 0.5)
                
                print(f"📊 スコア: {score}点 (OCR品質: {ocr_quality:.2f})")
                
                # OCR適応型閾値で判定
                action = decide_action(score, ENHANCED_CONFIG, ocr_quality)
                results[action.lower()] += 1
                
                # 改善ポイントの表示
                if 'learned_bonus' in best.get('reasons', []):
                    print(f"🧠 学習ボーナス適用")
                if 'low_quality_ocr_mode' in best.get('reasons', []):
                    print(f"🔧 低品質OCR対応モード")
                if best.get('deltas', {}).get('ocr_quality', 0) < 0.7:
                    print(f"📈 OCR品質低下 → 緩和閾値適用")
            else:
                action = 'MANUAL'
                results['manual'] += 1
                print(f"📊 マッチング候補なし")
            
            print(f"🎯 判定: {action}")
        
        print(f"\n" + "=" * 40)
        print(f"📈 改善後の結果:")
        print(f"  自動紐付け: {results['auto']}件 ({results['auto']/len(REALISTIC_OCR_PATTERNS)*100:.1f}%)")
        print(f"  人間確認: {results['assist']}件 ({results['assist']/len(REALISTIC_OCR_PATTERNS)*100:.1f}%)")
        print(f"  手動対応: {results['manual']}件 ({results['manual']/len(REALISTIC_OCR_PATTERNS)*100:.1f}%)")
        
        return results
        
    except ImportError as e:
        print(f"⚠️ 強化マッチャーのインポートエラー: {e}")
        return {'auto': 0, 'assist': 0, 'manual': len(REALISTIC_OCR_PATTERNS)}

def analyze_improvements(before, after):
    """改善効果の分析"""
    print("\n" + "=" * 60)
    print("📊 改善効果の分析")
    print("=" * 60)
    
    total = len(REALISTIC_OCR_PATTERNS)
    
    print(f"\n🎯 自動紐付け率の改善:")
    before_auto_rate = before['auto'] / total * 100
    after_auto_rate = after['auto'] / total * 100
    improvement = after_auto_rate - before_auto_rate
    
    print(f"  改善前: {before['auto']}/{total}件 ({before_auto_rate:.1f}%)")
    print(f"  改善後: {after['auto']}/{total}件 ({after_auto_rate:.1f}%)")
    print(f"  向上: +{improvement:.1f}ポイント")
    
    print(f"\n🔧 効率化の改善:")
    before_non_manual = (before['auto'] + before['assist']) / total * 100
    after_non_manual = (after['auto'] + after['assist']) / total * 100
    efficiency_improvement = after_non_manual - before_non_manual
    
    print(f"  改善前（自動+確認）: {before_non_manual:.1f}%")
    print(f"  改善後（自動+確認）: {after_non_manual:.1f}%")
    print(f"  効率化: +{efficiency_improvement:.1f}ポイント")
    
    print(f"\n💡 OCR問題パターンの救済:")
    ocr_zero_patterns = [p for p in REALISTIC_OCR_PATTERNS if p['amount'] == 0]
    print(f"  OCR処理未完了パターン: {len(ocr_zero_patterns)}件")
    print(f"  → ファイル名解析による補強")
    print(f"  → 緩和閾値（45点）適用")
    
    garbled_patterns = [p for p in REALISTIC_OCR_PATTERNS if p['expected_quality'] == 'medium']
    print(f"  文字化けパターン: {len(garbled_patterns)}件") 
    print(f"  → 部分マッチング適用")
    print(f"  → 金額重視マッチング")

def main():
    """メインテスト実行"""
    print("🧪 実際のOCR問題パターンによる改善効果テスト")
    print("データソース: GitHub Actions実行結果分析")
    
    # テスト実行
    before_results = test_before_improvements()
    after_results = test_after_improvements()
    
    # 分析
    analyze_improvements(before_results, after_results)
    
    print(f"\n" + "=" * 60)
    print("✅ テスト完了")
    print("=" * 60)
    
    # 次のアクション提案
    print(f"\n🚀 推奨される次のアクション:")
    print(f"1. 実環境でのテスト実行")
    print(f"2. 閾値の微調整（必要に応じて）")
    print(f"3. 学習データの蓄積と活用")
    print(f"4. OCR品質向上への継続的対応")

if __name__ == "__main__":
    main()