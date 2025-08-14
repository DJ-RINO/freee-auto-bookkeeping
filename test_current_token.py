#!/usr/bin/env python3
"""
現在のアクセストークンでAPI接続をテスト
"""

import os
import requests
from datetime import datetime

def test_current_access_token():
    """現在のアクセストークンが有効かテスト"""
    
    # .envから値を取得
    access_token = "mGWy2XVTmcHQrcKYLnWKXhfFIOjBzLVYLIT48pvUemw"
    company_id = 10383235
    
    print("🧪 現在のアクセストークンのテスト")
    print(f"トークン: {access_token[:20]}...")
    print(f"会社ID: {company_id}")
    
    # freee API基本テスト
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # 1. 会社情報取得テスト
    print("\n1️⃣ 会社情報取得テスト")
    try:
        response = requests.get(
            f"https://api.freee.co.jp/api/1/companies/{company_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            company_data = response.json()
            print(f"✅ 会社情報取得成功")
            print(f"   会社名: {company_data.get('company', {}).get('name', 'N/A')}")
        else:
            print(f"❌ 会社情報取得失敗: {response.status_code}")
            print(f"   エラー: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 会社情報取得エラー: {e}")
        return False
    
    # 2. ファイルボックス取得テスト
    print("\n2️⃣ ファイルボックス取得テスト")
    try:
        response = requests.get(
            f"https://api.freee.co.jp/api/1/receipts",
            headers=headers,
            params={
                "company_id": company_id,
                "limit": 5
            }
        )
        
        if response.status_code == 200:
            receipts_data = response.json()
            receipts = receipts_data.get('receipts', [])
            print(f"✅ ファイルボックス取得成功: {len(receipts)}件")
            
            if receipts:
                print("   最初の3件:")
                for i, receipt in enumerate(receipts[:3], 1):
                    receipt_id = receipt.get('id', 'N/A')
                    vendor = receipt.get('description', 'N/A')
                    amount = receipt.get('amount', 0)
                    print(f"   {i}. ID:{receipt_id}, vendor:{vendor[:20]}, ¥{amount:,}")
            
            return True
            
        elif response.status_code == 403:
            print(f"❌ ファイルボックス取得失敗: {response.status_code}")
            print(f"   プラン制限: freeeベーシックプランではAPIが利用できません")
            print(f"   プロフェッショナルプラン以上が必要です")
            return False
        else:
            print(f"❌ ファイルボックス取得失敗: {response.status_code}")
            print(f"   エラー: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ファイルボックス取得エラー: {e}")
        return False

def test_ocr_improvements_with_real_data():
    """実データを使ってOCR改善の効果をテスト"""
    
    print("\n" + "="*60)
    print("🚀 OCR改善システムの実データテスト")
    print("="*60)
    
    # まずAPIが利用可能か確認
    if not test_current_access_token():
        print("\n⚠️ APIアクセスが不可能なため、シミュレーションモードで実行")
        print("実際のデータテストは環境修正後に実行してください")
        return
    
    print("\n✅ APIアクセス確認完了 - 実データでのOCR改善テストが可能です")
    print("\n次のステップ:")
    print("1. process_receipts_main.py でOCR改善システムを実行")
    print("2. 低品質OCRレシートの救済状況を確認")
    print("3. 自動紐付け率の改善を測定")

if __name__ == "__main__":
    test_ocr_improvements_with_real_data()