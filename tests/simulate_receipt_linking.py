#!/usr/bin/env python
"""
レシート紐付け処理のシミュレーション
freeeファイルボックスの38件のファイルを想定
"""

import os
import sys
import json
from datetime import datetime, date
from unittest.mock import Mock, MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

def simulate_filebox_api_responses():
    """freee APIの各種レスポンスをシミュレート"""
    
    print("=" * 70)
    print("🎭 freeeファイルボックスAPIシミュレーション")
    print("=" * 70)
    print("\n前提条件:")
    print("  - freeeダッシュボードで38件のファイルを確認")
    print("  - ファイルボックスに未添付の状態で保存")
    print("  - 請求書や領収書をアップロード済み")
    print("\n" + "=" * 70)
    
    # シナリオ1: ベーシックプラン（403エラー）
    print("\n📌 シナリオ1: ベーシックプランの場合")
    print("-" * 40)
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "code": "forbidden",
            "message": "このAPIはご利用のプランでは使用できません"
        }
        mock_get.return_value = mock_response
        
        from filebox_client import FileBoxClient
        client = FileBoxClient("dummy_token", 123456)
        
        print("実行中...")
        receipts = client.list_receipts(limit=50)
        print(f"\n結果: {len(receipts)}件のレシート取得")
        print("\n💡 対策: プロフェッショナルプラン以上にアップグレードが必要")
    
    # シナリオ2: プロフェッショナルプラン（成功）
    print("\n" + "=" * 70)
    print("\n📌 シナリオ2: プロフェッショナルプランの場合（成功）")
    print("-" * 40)
    
    # 38件のダミーレシートデータを生成
    dummy_receipts = []
    for i in range(1, 39):
        dummy_receipts.append({
            "id": f"receipt_{i}",
            "file_name": f"領収書_{i:03d}.pdf",
            "description": f"店舗名_{i}",
            "amount": 1000 * i,
            "created_at": "2024-01-01T10:00:00+09:00",
            "status": "unlinked"
        })
    
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "receipts": dummy_receipts
        }
        mock_get.return_value = mock_response
        
        client = FileBoxClient("dummy_token", 123456)
        
        print("実行中...")
        receipts = client.list_receipts(limit=50)
        print(f"\n✅ 結果: {len(receipts)}件のレシート取得成功！")
        
        if receipts:
            print("\n取得したレシート（最初の5件）:")
            for i, receipt in enumerate(receipts[:5], 1):
                print(f"  {i}. ID: {receipt['id']}, ファイル: {receipt['file_name']}")
    
    # シナリオ3: 取引とのマッチング
    print("\n" + "=" * 70)
    print("\n📌 シナリオ3: 取引とのマッチング処理")
    print("-" * 40)
    
    # ダミーの取引データ
    dummy_transactions = [
        {"id": "tx_1", "amount": 1000, "date": "2024-01-01", "description": "店舗名_1"},
        {"id": "tx_2", "amount": 2000, "date": "2024-01-02", "description": "店舗名_2"},
        {"id": "tx_3", "amount": 5000, "date": "2024-01-03", "description": "違う店舗"},
    ]
    
    print("\nマッチング結果:")
    matched = 0
    for receipt in dummy_receipts[:10]:  # 最初の10件だけシミュレート
        # 金額と店舗名でマッチング
        for tx in dummy_transactions:
            if receipt["amount"] == tx["amount"] and receipt["description"] in tx["description"]:
                print(f"  ✅ マッチ: レシート {receipt['id']} → 取引 {tx['id']} (スコア: 95)")
                matched += 1
                break
        else:
            print(f"  ❓ 未マッチ: レシート {receipt['id']} → 手動確認が必要")
    
    print(f"\n結果サマリー:")
    print(f"  - 自動マッチング: {matched}件")
    print(f"  - 手動確認必要: {10 - matched}件")
    
    # シナリオ4: 完全な処理フロー
    print("\n" + "=" * 70)
    print("\n📌 シナリオ4: 完全な処理フロー")
    print("-" * 40)
    
    print("\n1️⃣ ファイルボックスから38件取得")
    print("2️⃣ 各レシートに対して:")
    print("   - 取引とマッチング試行")
    print("   - スコア85点以上 → 自動紐付け")
    print("   - スコア65-84点 → Slack通知で確認")
    print("   - スコア65点未満 → 手動対応")
    print("3️⃣ 処理結果をSlackに通知")
    
    # 予想される結果
    print("\n予想される処理結果（38件の場合）:")
    print("  - 自動紐付け: 約15件（40%）")
    print("  - Slack確認: 約10件（26%）")
    print("  - 手動対応: 約13件（34%）")
    
    print("\n" + "=" * 70)
    print("✨ シミュレーション完了")
    print("=" * 70)

def simulate_api_errors():
    """APIエラーパターンのシミュレーション"""
    
    print("\n\n")
    print("=" * 70)
    print("⚠️ APIエラーパターンのシミュレーション")
    print("=" * 70)
    
    error_patterns = [
        {
            "status": 400,
            "error": {"errors": [{"message": "status パラメータが不正です"}]},
            "説明": "パラメータエラー（statusの値が間違っている）"
        },
        {
            "status": 403,
            "error": {"code": "forbidden", "message": "プランの制限"},
            "説明": "ベーシックプランでAPIが使えない"
        },
        {
            "status": 404,
            "error": {"code": "not_found", "message": "エンドポイントが存在しません"},
            "説明": "APIエンドポイントが間違っている"
        },
        {
            "status": 401,
            "error": {"code": "unauthorized", "message": "トークンが無効です"},
            "説明": "アクセストークンの期限切れ"
        }
    ]
    
    for i, pattern in enumerate(error_patterns, 1):
        print(f"\n{i}. {pattern['説明']}")
        print(f"   Status: {pattern['status']}")
        print(f"   Error: {pattern['error']}")
        print(f"   対策: ", end="")
        
        if pattern["status"] == 400:
            print("パラメータを修正する")
        elif pattern["status"] == 403:
            print("プランをアップグレードする")
        elif pattern["status"] == 404:
            print("正しいエンドポイントを使用する")
        elif pattern["status"] == 401:
            print("トークンをリフレッシュする")

if __name__ == "__main__":
    # メインのシミュレーション実行
    simulate_filebox_api_responses()
    
    # エラーパターンも表示
    simulate_api_errors()
    
    print("\n\n🎯 次のアクション:")
    print("1. GitHub Actionsで実際に実行")
    print("2. エラーコードを確認")
    print("3. 必要に応じてプランの確認またはAPI仕様の再確認")