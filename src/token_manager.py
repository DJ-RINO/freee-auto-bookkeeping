import os
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional
import base64

class FreeeTokenManager:
    """freeeのトークンを自動的に管理・更新するクラス"""
    
    def __init__(self, client_id: str, client_secret: str, github_token: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.github_token = github_token
        self.token_url = "https://accounts.secure.freee.co.jp/public_api/token"
        
    def refresh_token(self, refresh_token: str) -> Dict:
        """リフレッシュトークンを使って新しいアクセストークンを取得"""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        # デバッグ情報を表示（センシティブな情報は隠す）
        print(f"🔄 トークンリフレッシュを試行中...")
        print(f"  - Client ID: {self.client_id[:10]}... (length: {len(self.client_id)})")
        print(f"  - Refresh Token: {refresh_token[:10]}... (length: {len(refresh_token)})")
        
        try:
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            print("✅ 新しいアクセストークンを取得しました")
            
            # 有効期限を計算
            expires_at = datetime.now() + timedelta(seconds=token_data.get('expires_in', 86400))
            token_data['expires_at'] = expires_at.isoformat()
            
            return token_data
        except requests.exceptions.HTTPError as e:
            print(f"❌ トークンリフレッシュエラー: {e}")
            print(f"  - ステータスコード: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"  - エラー詳細: {error_detail}")
                
                # よくあるエラーの原因を表示
                if response.status_code == 401:
                    print("\n⚠️  考えられる原因:")
                    print("  1. リフレッシュトークンが期限切れ（freeeのリフレッシュトークンは14日間有効）")
                    print("  2. リフレッシュトークンが既に使用済み（一度使用すると無効になります）")
                    print("  3. CLIENT_IDまたはCLIENT_SECRETが正しくない")
                    print("\n📝 対処法:")
                    print("  1. freee Developersで新しい認証コードを取得してください")
                    print("  2. 新しいアクセストークンとリフレッシュトークンを取得してください")
                    print("  3. GitHub Secretsを更新してください")
            except:
                print(f"  - レスポンス本文: {response.text}")
            raise
    
    def update_github_secret(self, repo: str, secret_name: str, secret_value: str):
        """GitHub Secretsを更新"""
        if not self.github_token:
            print("⚠️  GitHub tokenが設定されていないため、Secretsを更新できません")
            return False
        
        # リポジトリの公開鍵を取得
        public_key_url = f"https://api.github.com/repos/{repo}/actions/secrets/public-key"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(public_key_url, headers=headers)
        response.raise_for_status()
        public_key_data = response.json()
        
        # 値を暗号化
        try:
            from nacl import encoding, public
            public_key = public.PublicKey(public_key_data['key'].encode("utf-8"), encoding.Base64Encoder())
            sealed_box = public.SealedBox(public_key)
            encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
            encrypted_value = base64.b64encode(encrypted).decode("utf-8")
        except ImportError:
            print("⚠️  PyNaClがインストールされていません。pip install PyNaClを実行してください")
            return False
        
        # Secretを更新
        secret_url = f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}"
        data = {
            "encrypted_value": encrypted_value,
            "key_id": public_key_data['key_id']
        }
        
        response = requests.put(secret_url, headers=headers, json=data)
        response.raise_for_status()
        
        print(f"✅ GitHub Secret '{secret_name}' を更新しました")
        return True
    
    def save_tokens_locally(self, token_data: Dict, file_path: str = ".tokens.json"):
        """トークンをローカルファイルに保存（バックアップ用）"""
        with open(file_path, 'w') as f:
            json.dump(token_data, f, indent=2)
        print(f"💾 トークンを {file_path} に保存しました")
    
    def load_tokens_locally(self, file_path: str = ".tokens.json") -> Optional[Dict]:
        """ローカルファイルからトークンを読み込み"""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
    
    def auto_refresh_if_needed(self, current_token: str, refresh_token: str) -> Optional[Dict]:
        """必要に応じて自動的にトークンをリフレッシュ"""
        # 現在のトークンが有効か確認
        test_url = "https://api.freee.co.jp/api/1/users/me"
        headers = {"Authorization": f"Bearer {current_token}"}
        
        response = requests.get(test_url, headers=headers)
        
        if response.status_code == 401:
            # トークンが無効なのでリフレッシュ
            print("🔄 アクセストークンの有効期限が切れています。更新します...")
            new_tokens = self.refresh_token(refresh_token)
            
            # 新しいトークンをローカルに保存（バックアップ）
            if new_tokens:
                self.save_tokens_locally(new_tokens)
            
            return new_tokens
        elif response.status_code == 200:
            print("✅ 現在のアクセストークンは有効です")
            return None
        else:
            response.raise_for_status()


def integrate_with_main():
    """main.pyに統合するためのコード例"""
    
    # 環境変数から設定を読み込み
    client_id = os.getenv("FREEE_CLIENT_ID")
    client_secret = os.getenv("FREEE_CLIENT_SECRET")
    refresh_token = os.getenv("FREEE_REFRESH_TOKEN")
    github_token = os.getenv("GITHUB_TOKEN")  # GitHub Actionsで自動的に利用可能
    
    # デバッグ情報を表示
    print("\n[トークン管理システム - 環境変数の確認]")
    print(f"  - FREEE_CLIENT_ID: {'設定済み' if client_id else '未設定'} (length: {len(client_id) if client_id else 0})")
    print(f"  - FREEE_CLIENT_SECRET: {'設定済み' if client_secret else '未設定'} (length: {len(client_secret) if client_secret else 0})")
    print(f"  - FREEE_REFRESH_TOKEN: {'設定済み' if refresh_token else '未設定'} (length: {len(refresh_token) if refresh_token else 0})")
    print(f"  - GITHUB_TOKEN: {'設定済み' if github_token else '未設定'}")
    
    # 必須パラメータのチェック
    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("必須の環境変数が設定されていません: FREEE_CLIENT_ID, FREEE_CLIENT_SECRET, FREEE_REFRESH_TOKEN")
    
    # トークンマネージャーを初期化
    token_manager = FreeeTokenManager(client_id, client_secret, github_token)
    
    # 現在のアクセストークンを取得
    access_token = os.getenv("FREEE_ACCESS_TOKEN")
    
    # 必要に応じてリフレッシュ
    new_tokens = token_manager.auto_refresh_if_needed(access_token, refresh_token)
    
    if new_tokens:
        # 新しいトークンを取得した場合
        access_token = new_tokens['access_token']
        new_refresh_token = new_tokens.get('refresh_token', refresh_token)
        
        # GitHub Secretsを更新
        repo = os.getenv("GITHUB_REPOSITORY", "DJ-RINO/freee-auto-bookkeeping")
        token_manager.update_github_secret(repo, "FREEE_ACCESS_TOKEN", access_token)
        
        if new_refresh_token != refresh_token:
            token_manager.update_github_secret(repo, "FREEE_REFRESH_TOKEN", new_refresh_token)
        
        # ローカルバックアップ
        token_manager.save_tokens_locally(new_tokens)
    
    return access_token


if __name__ == "__main__":
    # テスト実行
    print("=== freeeトークン管理システム ===")
    
    # 環境変数の確認
    required_env = ["FREEE_CLIENT_ID", "FREEE_CLIENT_SECRET", "FREEE_REFRESH_TOKEN"]
    missing = [env for env in required_env if not os.getenv(env)]
    
    if missing:
        print(f"❌ 以下の環境変数を設定してください: {', '.join(missing)}")
    else:
        access_token = integrate_with_main()
        print(f"\n使用するアクセストークン: {access_token[:20]}...")