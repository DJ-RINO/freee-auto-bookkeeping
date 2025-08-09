#!/usr/bin/env python3
"""
freeeの新しいトークンを取得するスクリプト
"""

import requests
import json
import os
from datetime import datetime

def get_new_tokens(auth_code, client_id, client_secret):
    """認証コードを使って新しいトークンを取得"""
    
    url = "https://accounts.secure.freee.co.jp/public_api/token"
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob"
    }
    
    print("🔄 新しいトークンを取得中...")
    print(f"  - Client ID: {client_id[:10]}...")
    print(f"  - Auth Code: {auth_code[:10]}...")
    
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        
        # 有効期限を計算
        expires_at = datetime.now().timestamp() + token_data.get('expires_in', 86400)
        token_data['expires_at'] = expires_at
        
        print("✅ 新しいトークンを取得しました！")
        print(f"  - Access Token: {token_data['access_token'][:20]}...")
        print(f"  - Refresh Token: {token_data['refresh_token'][:20]}...")
        print(f"  - 有効期限: {token_data['expires_in']}秒")
        
        return token_data
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ トークン取得エラー: {e}")
        print(f"  - ステータスコード: {response.status_code}")
        try:
            error_detail = response.json()
            print(f"  - エラー詳細: {error_detail}")
        except:
            print(f"  - レスポンス本文: {response.text}")
        return None

def save_tokens(token_data, filename="new_tokens.json"):
    """トークンをファイルに保存"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(token_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 トークンを {filename} に保存しました")

def main():
    print("=== freee 新しいトークン取得 ===")
    print()
    
    # ユーザーから情報を取得
    print("以下の情報を入力してください:")
    print()
    
    client_id = input("Client ID: ").strip()
    client_secret = input("Client Secret: ").strip()
    auth_code = input("認証コード: ").strip()
    
    if not all([client_id, client_secret, auth_code]):
        print("❌ すべての情報を入力してください")
        return
    
    # 新しいトークンを取得
    token_data = get_new_tokens(auth_code, client_id, client_secret)
    
    if token_data:
        # トークンを保存
        save_tokens(token_data)
        
        print("\n" + "="*50)
        print("🎉 トークン取得完了！")
        print("\n次のステップ:")
        print("1. GitHubリポジトリの Settings > Secrets and variables > Actions")
        print("2. 以下のSecretsを更新:")
        print(f"   - FREEE_ACCESS_TOKEN: {token_data['access_token']}")
        print(f"   - FREEE_REFRESH_TOKEN: {token_data['refresh_token']}")
        print("3. 必要に応じて他のSecretsも更新")
        print("\n⚠️  注意: 認証コードは一度使用すると無効になります")
        
    else:
        print("\n❌ トークン取得に失敗しました")
        print("認証コードが正しいか、有効期限が切れていないか確認してください")

if __name__ == "__main__":
    main() 