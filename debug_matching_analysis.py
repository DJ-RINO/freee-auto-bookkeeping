#!/usr/bin/env python
"""
TDD和田流 - マッチング問題の分析テスト
GitHub Actionsの結果から問題点を特定
"""

def analyze_github_actions_result():
    """GitHub Actionsの結果を分析"""
    print("=== TDD和田流 問題分析 ===")
    
    # 1. OCRデータ抽出の確認
    print("\n1. OCRデータ抽出状況:")
    ocr_success_cases = [
        ("328979267", "CANNABIS JAPAN合同会社", 200000, "2025-04-09"),
        ("328979348", "株式会社 グリーンブラザーズ・ジャパン", 41600, "2025-04-10"),
        ("328979401", "Recalmo合同会社", 31000, "2025-04-10"),
    ]
    
    ocr_failed_cases = [
        ("331122062", "レシート#331122062", 0, "2025-06-01"),
        ("351211310", "レシート#351211310", 0, "2025-08-12"),
        # ... 多数の¥0ケース
    ]
    
    print(f"  ✅ OCR成功: {len(ocr_success_cases)}件 (正確な店舗名・金額・日付)")
    print(f"  ❌ OCR失敗: 約25件 (¥0, レシート#ID)")
    
    # 2. 取引データの確認
    print("\n2. 取引データ状況:")
    print("  ✅ wallet_txns: 100件取得")
    print("  ✅ deals: 100件取得")
    print("  📊 合計: 200件の取引データ")
    
    # 3. マッチング結果
    print("\n3. マッチング結果:")
    print("  ❌ 成功: 0件")
    print("  ⚠️ 一部マッチ: 1件 (スコア20点 → MANUAL)")
    print("  ❌ 失敗: 33件")
    
    # 4. 問題の仮説
    print("\n4. 問題の仮説:")
    print("  A) OCR処理未完了 - freee側でOCR処理が完了していない証憑が多数")
    print("  B) 日付の不一致 - レシート日付と取引日付の範囲が異なる")
    print("  C) 金額の不一致 - 税込/税抜、手数料等の差異")
    print("  D) マッチングアルゴリズム - 許容範囲が狭すぎる")

def test_date_range_hypothesis():
    """仮説B: 日付範囲の問題をテスト"""
    print("\n=== 日付範囲仮説のテスト ===")
    
    receipt_dates = ["2025-04-09", "2025-04-10", "2025-04-28", "2025-05-02", "2025-05-06", "2025-05-18"]
    transaction_range = ("2025-05-15", "2025-08-13")  # GitHub Actionsで取得した範囲
    
    print(f"レシート日付: {receipt_dates}")
    print(f"取引取得範囲: {transaction_range[0]} ~ {transaction_range[1]}")
    
    out_of_range = [date for date in receipt_dates if date < transaction_range[0]]
    print(f"❌ 範囲外のレシート: {len(out_of_range)}件 - {out_of_range}")
    
    if out_of_range:
        print("✅ 仮説B確認: 日付範囲の問題が存在")
        return True
    return False

def test_ocr_completion_hypothesis():
    """仮説A: OCR処理未完了の問題をテスト"""
    print("\n=== OCR処理完了状況のテスト ===")
    
    total_receipts = 34
    ocr_completed = 9  # 金額・店舗名が正しく取得されている件数
    ocr_pending = 25   # ¥0で店舗名がレシート#IDの件数
    
    completion_rate = (ocr_completed / total_receipts) * 100
    print(f"OCR完了率: {completion_rate:.1f}% ({ocr_completed}/{total_receipts})")
    
    if completion_rate < 50:
        print("✅ 仮説A確認: OCR処理未完了の問題が深刻")
        return True
    return False

if __name__ == "__main__":
    analyze_github_actions_result()
    
    # 仮説テスト
    date_issue = test_date_range_hypothesis()
    ocr_issue = test_ocr_completion_hypothesis()
    
    print("\n=== 和田流 次のアクション ===")
    if date_issue:
        print("1. 日付範囲を拡大（90日 → 180日または1年）")
    if ocr_issue:
        print("2. OCR処理完了を待つか、手動で証憑を再アップロード")
    
    print("3. マッチングアルゴリズムの許容範囲を調整")
    print("4. デバッグ用のマッチング詳細ログを追加")