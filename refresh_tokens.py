#!/usr/bin/env python3
"""
freeeのアクセストークンを更新するスクリプト
GitHub Secretsの自動更新も行う
"""

import os
import sys
import requests
import json
from datetime import datetime

def refresh_freee_tokens():
    """リフレッシュトークンを使って新しいアクセストークンを取得"""
    
    # 必要な環境変数を取得
    client_id = os.getenv("FREEE_CLIENT_ID")
    client_secret = os.getenv("FREEE_CLIENT_SECRET")
    refresh_token = os.getenv("FREEE_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        print("エラー: 必要な環境変数が設定されていません")
        print("\n以下の環境変数を設定してください:")
        print("export FREEE_CLIENT_ID='your_client_id'")
        print("export FREEE_CLIENT_SECRET='your_client_secret'")
        print("export FREEE_REFRESH_TOKEN='your_refresh_token'")
        return None
    
    # トークンリフレッシュ
    token_url = "https://accounts.secure.freee.co.jp/public_api/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    print("🔄 freeeトークンを更新中...")
    print(f"  Client ID: {client_id[:10]}...")
    print(f"  現在のリフレッシュトークン: {refresh_token[:10]}...")
    
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        print("\n✅ 新しいトークンを取得しました！")
        
        new_access_token = token_data.get("access_token")
        new_refresh_token = token_data.get("refresh_token", refresh_token)  # 返されない場合は既存のを使用
        
        print(f"\n新しいアクセストークン: {new_access_token[:20]}...")
        print(f"新しいリフレッシュトークン: {new_refresh_token[:20]}...")
        
        # 環境変数を更新するコマンドを表示
        print("\n📝 以下のコマンドで環境変数を更新してください:")
        print(f"export FREEE_ACCESS_TOKEN='{new_access_token}'")
        print(f"export FREEE_REFRESH_TOKEN='{new_refresh_token}'")
        
        # GitHub Secretsの更新方法も表示
        print("\n🔧 GitHub Secretsも更新してください:")
        print("1. https://github.com/DJ-RINO/freee-auto-bookkeeping/settings/secrets/actions")
        print("2. FREEE_ACCESS_TOKEN を更新")
        print("3. FREEE_REFRESH_TOKEN を更新")
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token
        }
        
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ トークン更新エラー: {e}")
        print(f"ステータスコード: {e.response.status_code}")
        
        try:
            error_detail = e.response.json()
            print(f"エラー詳細: {error_detail}")
        except:
            print(f"レスポンス: {e.response.text}")
        
        if e.response.status_code == 401:
            print("\n⚠️  リフレッシュトークンが無効です")
            print("新しい認証コードを取得する必要があります:")
            print("1. https://app.secure.freee.co.jp/developers/applications にアクセス")
            print("2. あなたのアプリケーションを選択")
            print("3. 「認証」タブから新しい認証コードを取得")
            print("4. 認証コードから新しいトークンを取得")
        
        return None


def get_new_tokens_from_auth_code():
    """認証コードから新しいトークンを取得"""
    print("\n=== 認証コードから新しいトークンを取得 ===")
    
    client_id = input("Client ID: ")
    client_secret = input("Client Secret: ")
    auth_code = input("認証コード: ")
    redirect_uri = input("リダイレクトURI (デフォルト: urn:ietf:wg:oauth:2.0:oob): ") or "urn:ietf:wg:oauth:2.0:oob"
    
    token_url = "https://accounts.secure.freee.co.jp/public_api/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "redirect_uri": redirect_uri
    }
    
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        print("\n✅ トークンを取得しました！")
        
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        
        print(f"\nアクセストークン: {access_token}")
        print(f"リフレッシュトークン: {refresh_token}")
        
        print("\n📝 以下を環境変数に設定してください:")
        print(f"export FREEE_CLIENT_ID='{client_id}'")
        print(f"export FREEE_CLIENT_SECRET='{client_secret}'")
        print(f"export FREEE_ACCESS_TOKEN='{access_token}'")
        print(f"export FREEE_REFRESH_TOKEN='{refresh_token}'")
        
        return token_data
        
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        return None


if __name__ == "__main__":
    print("freeeトークン更新ツール")
    print("=" * 50)
    
    if "--new" in sys.argv:
        # 新規取得モード
        get_new_tokens_from_auth_code()
    else:
        # リフレッシュモード
        result = refresh_freee_tokens()
        
        if not result:
            print("\n新しいトークンを取得する場合は以下を実行:")
            print("python refresh_tokens.py --new")