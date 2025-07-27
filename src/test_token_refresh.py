#!/usr/bin/env python3
"""
トークンリフレッシュ機能のテストスクリプト

使い方:
python test_token_refresh.py

このスクリプトは実際にトークンをリフレッシュせず、
現在の設定と動作フローを確認します。
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

def check_environment():
    """環境変数の設定状態を確認"""
    print("=== 環境変数チェック ===\n")
    
    required_vars = {
        "FREEE_CLIENT_ID": "freee APIのクライアントID",
        "FREEE_CLIENT_SECRET": "freee APIのクライアントシークレット",
        "FREEE_ACCESS_TOKEN": "現在のアクセストークン",
        "FREEE_REFRESH_TOKEN": "現在のリフレッシュトークン",
        "GITHUB_TOKEN": "GitHub Actions用トークン（Actions内でのみ必要）"
    }
    
    all_set = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: 設定済み (length: {len(value)})")
        else:
            print(f"❌ {var}: 未設定 - {description}")
            if var != "GITHUB_TOKEN":  # GITHUB_TOKENはローカルでは不要
                all_set = False
    
    return all_set

def simulate_token_refresh():
    """トークンリフレッシュのシミュレーション"""
    print("\n=== トークンリフレッシュ・シミュレーション ===\n")
    
    # token_managerをインポート
    try:
        from token_manager import integrate_with_main
        print("✅ token_manager.py のインポート成功")
    except ImportError as e:
        print(f"❌ token_manager.py のインポート失敗: {e}")
        return
    
    print("\n以下の処理が実行されます：")
    print("1. 現在のアクセストークンの有効性をチェック")
    print("2. 無効な場合、リフレッシュトークンを使用して新しいトークンを取得")
    print("3. 新しいアクセストークンとリフレッシュトークンを取得")
    print("4. GitHub Secretsを自動更新（GitHub Actions内のみ）")
    print("5. ローカルバックアップファイル(.tokens.json)に保存")
    
    print("\n⚠️  重要な注意事項:")
    print("- リフレッシュトークンは1回しか使用できません")
    print("- 使用後は新しいリフレッシュトークンが発行されます")
    print("- 新しいリフレッシュトークンは必ずGitHub Secretsに保存される必要があります")
    print("- そうしないと次回のリフレッシュが失敗します")

def check_github_actions_setup():
    """GitHub Actions の設定確認"""
    print("\n=== GitHub Actions 設定チェック ===\n")
    
    print("📝 必要なGitHub Secrets:")
    print("- FREEE_CLIENT_ID")
    print("- FREEE_CLIENT_SECRET")
    print("- FREEE_ACCESS_TOKEN")
    print("- FREEE_REFRESH_TOKEN")
    print("- FREEE_COMPANY_ID")
    print("- FREEE_CLAUDE_API_KEY (またはANTHROPIC_API_KEY)")
    print("- SLACK_WEBHOOK_URL")
    print("- PAT_TOKEN (オプション: Secrets更新用)")
    
    print("\n📝 ワークフローの権限設定:")
    print("- permissions.actions: write (Secrets更新に必要)")
    print("- GITHUB_TOKEN は自動的に提供されます")
    
    print("\n⚠️  PAT_TOKENについて:")
    print("- GITHUB_TOKENではSecretsの更新権限が制限される場合があります")
    print("- その場合は、Personal Access Token (PAT) を作成して")
    print("- PAT_TOKEN として GitHub Secrets に設定してください")
    print("- 必要な権限: repo (Full control of private repositories)")

def main():
    """メイン処理"""
    print("=== freeeトークン自動更新システム テスト ===")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 環境変数チェック
    env_ok = check_environment()
    
    if not env_ok:
        print("\n❌ 必要な環境変数が設定されていません")
        print("📝 .env ファイルまたは GitHub Secrets を確認してください")
        return
    
    # トークンリフレッシュのシミュレーション
    simulate_token_refresh()
    
    # GitHub Actions設定の確認
    check_github_actions_setup()
    
    print("\n=== テスト完了 ===")
    print("\n✅ 推奨される次のステップ:")
    print("1. GitHub Actions を手動実行して動作確認")
    print("2. ログでトークン更新処理を確認")
    print("3. 必要に応じてPAT_TOKENを設定")

if __name__ == "__main__":
    main()