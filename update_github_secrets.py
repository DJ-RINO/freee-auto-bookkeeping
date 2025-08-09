#!/usr/bin/env python3
"""
GitHub Secretsを自動更新するスクリプト
"""

import requests
import json
import base64
import os
from nacl import encoding, public

def update_github_secret(repo, secret_name, secret_value, github_token):
    """GitHub Secretを更新"""
    
    print(f"🔄 {secret_name} を更新中...")
    
    # リポジトリの公開鍵を取得
    public_key_url = f"https://api.github.com/repos/{repo}/actions/secrets/public-key"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(public_key_url, headers=headers)
    response.raise_for_status()
    public_key_data = response.json()
    
    # 値を暗号化
    public_key = public.PublicKey(public_key_data['key'].encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    encrypted_value = base64.b64encode(encrypted).decode("utf-8")
    
    # Secretを更新
    secret_url = f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}"
    data = {
        "encrypted_value": encrypted_value,
        "key_id": public_key_data['key_id']
    }
    
    response = requests.put(secret_url, headers=headers, json=data)
    response.raise_for_status()
    
    print(f"✅ {secret_name} を更新しました")

def main():
    print("=== GitHub Secrets 自動更新 ===")
    print()
    
    # 新しいトークンを読み込み
    try:
        with open("new_tokens.json", "r", encoding="utf-8") as f:
            token_data = json.load(f)
    except FileNotFoundError:
        print("❌ new_tokens.json が見つかりません")
        print("まず get_new_tokens.py を実行してトークンを取得してください")
        return
    
    # ユーザーから情報を取得
    github_token = input("GitHub Personal Access Token (PAT): ").strip()
    repo = input("リポジトリ名 (例: DJ-RINO/freee-auto-bookkeeping): ").strip()
    
    if not github_token or not repo:
        print("❌ 必要な情報を入力してください")
        return
    
    try:
        # GitHub Secretsを更新
        update_github_secret(repo, "FREEE_ACCESS_TOKEN", token_data['access_token'], github_token)
        update_github_secret(repo, "FREEE_REFRESH_TOKEN", token_data['refresh_token'], github_token)
        
        print("\n" + "="*50)
        print("🎉 GitHub Secrets更新完了！")
        print("\n更新されたSecrets:")
        print(f"  - FREEE_ACCESS_TOKEN: {token_data['access_token'][:20]}...")
        print(f"  - FREEE_REFRESH_TOKEN: {token_data['refresh_token'][:20]}...")
        print(f"  - 会社ID: {token_data['company_id']}")
        print("\n✅ これでGitHub Actionsが正常に動作するはずです")
        
    except Exception as e:
        print(f"❌ 更新に失敗しました: {e}")
        print("\n手動で更新する場合は以下を使用してください:")
        print(f"  FREEE_ACCESS_TOKEN: {token_data['access_token']}")
        print(f"  FREEE_REFRESH_TOKEN: {token_data['refresh_token']}")

if __name__ == "__main__":
    main() 