#!/usr/bin/env python
"""
freee API を直接テストして問題を特定
"""

import os
import sys
import requests
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from token_manager import integrate_with_main

def test_api_direct():
    """APIを直接テスト"""
    
    print("=" * 60)
    print("🔍 freee API 診断ツール")
    print("=" * 60)
    
    # トークン取得
    print("\n1. トークン取得中...")
    access_token = integrate_with_main()
    company_id = os.getenv("FREEE_COMPANY_ID")
    
    print(f"   ✅ アクセストークン: {access_token[:20]}...")
    print(f"   ✅ 会社ID: {company_id}")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    base_url = "https://api.freee.co.jp/api/1"
    
    # まずユーザー情報を確認（トークンが有効か）
    print("\n2. トークン有効性確認...")
    url = f"{base_url}/users/me"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        user_data = response.json()
        print(f"   ✅ トークン有効: ユーザー {user_data.get('user', {}).get('email', 'N/A')}")
    else:
        print(f"   ❌ トークン無効: {response.status_code} - {response.text}")
        return
    
    # 会社情報を確認
    print("\n3. 会社情報確認...")
    url = f"{base_url}/companies/{company_id}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        company_data = response.json()
        company = company_data.get('company', {})
        print(f"   ✅ 会社名: {company.get('display_name', 'N/A')}")
        print(f"   ✅ プラン情報取得中...")
        
        # プラン情報を表示
        role = company.get('role', 'N/A')
        print(f"   📋 ユーザーロール: {role}")
    else:
        print(f"   ❌ 会社情報取得失敗: {response.status_code}")
    
    # receipts API を複数パターンでテスト
    print("\n4. Receipts API テスト...")
    
    test_patterns = [
        {
            "name": "パラメータなし",
            "params": {"company_id": company_id}
        },
        {
            "name": "limit=1",
            "params": {"company_id": company_id, "limit": 1}
        },
        {
            "name": "start_date付き",
            "params": {"company_id": company_id, "start_date": "2024-01-01"}
        }
    ]
    
    for pattern in test_patterns:
        print(f"\n   テスト: {pattern['name']}")
        url = f"{base_url}/receipts"
        response = requests.get(url, headers=headers, params=pattern['params'])
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            receipts = data.get('receipts', [])
            print(f"   ✅ 成功！ {len(receipts)}件のレシート取得")
            
            if receipts:
                receipt = receipts[0]
                print(f"   サンプル: ID={receipt.get('id')}, "
                      f"説明={receipt.get('description', 'N/A')}")
            break
        elif response.status_code == 403:
            print(f"   ❌ 403 Forbidden")
            try:
                error = response.json()
                print(f"   エラー詳細: {json.dumps(error, ensure_ascii=False, indent=2)}")
            except:
                print(f"   レスポンス: {response.text[:200]}")
        elif response.status_code == 400:
            print(f"   ❌ 400 Bad Request")
            try:
                error = response.json()
                if 'errors' in error:
                    for e in error['errors']:
                        print(f"   - {e.get('message', e)}")
            except:
                print(f"   レスポンス: {response.text[:200]}")
        else:
            print(f"   ❌ エラー: {response.text[:200]}")
    
    # user_files API も試す
    print("\n5. User Files API テスト（代替）...")
    url = f"{base_url}/user_files"
    params = {"company_id": company_id, "limit": 1}
    response = requests.get(url, headers=headers, params=params)
    
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        files = data.get('user_files', [])
        print(f"   ✅ {len(files)}件のファイル取得")
    else:
        print(f"   ❌ エラー")
    
    print("\n" + "=" * 60)
    print("診断完了")
    print("=" * 60)

if __name__ == "__main__":
    test_api_direct()
