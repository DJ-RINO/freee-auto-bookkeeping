#!/usr/bin/env python
"""
freee APIのエンドポイントをテスト
"""

import os
import sys
import requests

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from token_manager import integrate_with_main

def test_freee_endpoints():
    """freee APIの各エンドポイントをテスト"""
    
    # トークン取得
    access_token = integrate_with_main()
    company_id = os.getenv("FREEE_COMPANY_ID")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    base_url = "https://api.freee.co.jp/api/1"
    
    endpoints = [
        # 会社情報（動作確認用）
        {
            "name": "会社情報",
            "method": "GET",
            "url": f"{base_url}/companies/{company_id}",
            "params": None
        },
        # 証憑一覧
        {
            "name": "証憑一覧 (receipts)",
            "method": "GET",
            "url": f"{base_url}/receipts",
            "params": {"company_id": company_id, "limit": 1}
        },
        # ファイルボックス
        {
            "name": "ファイルボックス (user_files)",
            "method": "GET",
            "url": f"{base_url}/user_files",
            "params": {"company_id": company_id, "limit": 1}
        },
        # 取引一覧
        {
            "name": "取引一覧 (deals)",
            "method": "GET",
            "url": f"{base_url}/deals",
            "params": {"company_id": company_id, "limit": 1}
        },
        # 明細一覧
        {
            "name": "明細一覧 (wallet_txns)",
            "method": "GET",
            "url": f"{base_url}/wallet_txns",
            "params": {"company_id": company_id, "limit": 1}
        }
    ]
    
    print("=" * 60)
    print("freee APIエンドポイントテスト")
    print("=" * 60)
    
    for endpoint in endpoints:
        print(f"\n[{endpoint['name']}]")
        print(f"  URL: {endpoint['url']}")
        
        try:
            if endpoint['method'] == 'GET':
                response = requests.get(
                    endpoint['url'],
                    headers=headers,
                    params=endpoint['params']
                )
            
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                # キーを表示
                print(f"  Response keys: {list(data.keys())}")
                
                # データ数を表示
                for key in data.keys():
                    if isinstance(data[key], list):
                        print(f"  {key} count: {len(data[key])}")
                    elif key == "company":
                        print(f"  Company name: {data[key].get('display_name', 'N/A')}")
                        
            else:
                print(f"  Error: {response.text[:200]}")
                
        except Exception as e:
            print(f"  Exception: {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_freee_endpoints()