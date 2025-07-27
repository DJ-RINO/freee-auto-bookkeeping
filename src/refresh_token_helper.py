#!/usr/bin/env python3
"""
freeeのトークンを手動で取得・更新するためのヘルパースクリプト

使い方:
1. このスクリプトを実行
2. 表示されるURLにアクセスして認証コードを取得
3. 認証コードを入力
4. 新しいトークンが表示される
"""

import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def get_authorization_url(client_id: str) -> str:
    """認証URLを生成"""
    return (
        f"https://accounts.secure.freee.co.jp/public_api/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri=urn:ietf:wg:oauth:2.0:oob"
        f"&response_type=code"
    )

def exchange_code_for_tokens(code: str, client_id: str, client_secret: str) -> dict:
    """認証コードをアクセストークンとリフレッシュトークンに交換"""
    url = "https://accounts.secure.freee.co.jp/public_api/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob"
    }
    
    response = requests.post(url, data=data)
    if response.status_code != 200:
        print(f"エラー: {response.status_code}")
        print(f"詳細: {response.text}")
        return None
    
    return response.json()

def main():
    print("=== freeeトークン取得ヘルパー ===\n")
    
    # 環境変数から取得
    client_id = os.getenv("FREEE_CLIENT_ID")
    client_secret = os.getenv("FREEE_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("エラー: FREEE_CLIENT_ID と FREEE_CLIENT_SECRET を .env ファイルに設定してください")
        return
    
    # 認証URLを表示
    auth_url = get_authorization_url(client_id)
    print("1. 以下のURLにアクセスして認証してください:")
    print(f"\n{auth_url}\n")
    
    # 認証コードの入力を待つ
    code = input("2. 表示された認証コードを入力してください: ").strip()
    
    if not code:
        print("エラー: 認証コードが入力されませんでした")
        return
    
    # トークンを取得
    print("\n3. トークンを取得中...")
    tokens = exchange_code_for_tokens(code, client_id, client_secret)
    
    if not tokens:
        print("トークンの取得に失敗しました")
        return
    
    # 結果を表示
    print("\n✅ トークンの取得に成功しました！\n")
    print("=== GitHub Secretsに設定する値 ===")
    print(f"FREEE_ACCESS_TOKEN: {tokens['access_token']}")
    print(f"FREEE_REFRESH_TOKEN: {tokens['refresh_token']}")
    
    # ローカルにも保存
    expires_at = datetime.now() + timedelta(seconds=tokens.get('expires_in', 86400))
    tokens['expires_at'] = expires_at.isoformat()
    
    with open('.tokens.json', 'w') as f:
        json.dump(tokens, f, indent=2)
    
    print("\n💾 トークンを .tokens.json に保存しました")
    print("\n📝 次のステップ:")
    print("1. 上記のトークンをGitHub Secretsに設定してください")
    print("2. FREEE_CLIENT_ID と FREEE_CLIENT_SECRET も設定されていることを確認してください")
    print("3. GitHub Actionsを再実行してください")

if __name__ == "__main__":
    main()