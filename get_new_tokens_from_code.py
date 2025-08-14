#!/usr/bin/env python3
"""
認可コードから新しいアクセストークンとリフレッシュトークンを取得
"""

import requests
import json
from datetime import datetime, timedelta

def get_tokens_from_authorization_code():
    """認可コードから新しいトークンを取得"""
    
    # 設定
    client_id = "613927644958899"
    client_secret = "DCG-XaRHceU1T2vmN8sEeCboTLa2LtWxP_JghU0HVXKqbYcM1ehToU398kDUD6gDA6HgFHkYb-FWP1_8ofac4g"
    authorization_code = "0yKnOpoqrstSADAK_KAU7JLaroJhu5NajZeJvWhbi5M"
    redirect_uri = "urn:ietf:wg:oauth:2.0:oob"  # freee Developersで設定したリダイレクトURI
    
    print("🔑 認可コードから新しいトークンを取得中...")
    print(f"Client ID: {client_id[:10]}...")
    print(f"認可コード: {authorization_code[:10]}...")
    
    # トークンエンドポイント
    token_url = "https://accounts.secure.freee.co.jp/public_api/token"
    
    # リクエストデータ
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": authorization_code,
        "redirect_uri": redirect_uri
    }
    
    try:
        # トークン取得リクエスト
        response = requests.post(token_url, data=data)
        
        print(f"\nレスポンス状況: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            
            print("✅ 新しいトークンの取得に成功しました！")
            print(f"アクセストークン: {token_data['access_token'][:20]}...")
            print(f"リフレッシュトークン: {token_data['refresh_token'][:20]}...")
            print(f"有効期限: {token_data['expires_in']}秒")
            print(f"会社ID: {token_data.get('company_id', 'N/A')}")
            
            # 有効期限を計算
            expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'])
            token_data['expires_at'] = expires_at.isoformat()
            token_data['created_at'] = datetime.now().timestamp()
            
            # ファイルに保存
            with open('latest_tokens.json', 'w') as f:
                json.dump(token_data, f, indent=2)
            
            print(f"\n💾 トークンをlatest_tokens.jsonに保存しました")
            
            # .envファイルを更新
            update_env_file(token_data)
            
            # 取得したトークンでAPI接続テスト
            test_new_tokens(token_data)
            
            return token_data
            
        else:
            print(f"❌ トークン取得失敗: {response.status_code}")
            try:
                error_data = response.json()
                print(f"エラー詳細: {error_data}")
            except:
                print(f"レスポンス: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        return None

def update_env_file(token_data):
    """新しいトークンで.envファイルを更新"""
    
    print("\n📝 .envファイルを更新中...")
    
    env_content = f"""# freee API設定 (latest_tokens.jsonから取得)
FREEE_ACCESS_TOKEN={token_data['access_token']}
FREEE_REFRESH_TOKEN={token_data['refresh_token']}
FREEE_COMPANY_ID={token_data.get('company_id', '10383235')}

# freee OAuth設定 (GitHub Secretsから取得)
FREEE_CLIENT_ID=613927644958899
FREEE_CLIENT_SECRET=DCG-XaRHceU1T2vmN8sEeCboTLa2LtWxP_JghU0HVXKqbYcM1ehToU398kDUD6gDA6HgFHkYb-FWP1_8ofac4g

# Claude API設定（freee自動仕訳用）
FREEE_CLAUDE_API_KEY=your_freee_claude_api_key_here

# Slack Webhook URL（オプション）
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# 実行モード（開発時はtrueに設定）
DRY_RUN=false

# CCA用に追加
CCA_ENABLED=true
CCA_REVIEW_LEVEL=detailed
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ .envファイルを更新しました")

def test_new_tokens(token_data):
    """新しいトークンでAPI接続をテスト"""
    
    print("\n🧪 新しいトークンでAPI接続テスト中...")
    
    access_token = token_data['access_token']
    company_id = token_data.get('company_id', '10383235')
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # 1. 会社情報取得
    try:
        response = requests.get(
            f"https://api.freee.co.jp/api/1/companies/{company_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            company_data = response.json()
            company_name = company_data.get('company', {}).get('name', 'N/A')
            print(f"✅ 会社情報取得成功 - 会社名: {company_name}")
        else:
            print(f"❌ 会社情報取得失敗: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 会社情報取得エラー: {e}")
        return False
    
    # 2. ファイルボックス取得
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
            print(f"✅ ファイルボックス取得成功: {len(receipts)}件のレシート")
            
            if receipts:
                print("\n📄 レシートサンプル（最初の3件）:")
                for i, receipt in enumerate(receipts[:3], 1):
                    receipt_id = receipt.get('id', 'N/A')
                    description = receipt.get('description', 'N/A')
                    amount = receipt.get('amount', 0)
                    print(f"  {i}. ID:{receipt_id}, vendor:{description[:25]}, ¥{amount:,}")
            
            print(f"\n🎯 OCR改善システムのテスト準備完了！")
            return True
            
        elif response.status_code == 403:
            print(f"❌ プラン制限: {response.status_code}")
            print("freeeベーシックプランではファイルボックスAPIは利用できません")
            print("プロフェッショナルプラン以上が必要です")
            return False
        else:
            print(f"❌ ファイルボックス取得失敗: {response.status_code}")
            print(f"レスポンス: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ファイルボックス取得エラー: {e}")
        return False

if __name__ == "__main__":
    print("🚀 freee認可コードからトークン取得")
    print("="*50)
    
    token_data = get_tokens_from_authorization_code()
    
    if token_data:
        print("\n" + "="*50)
        print("🎉 トークン取得完了 - OCR改善システムテスト実行可能！")
        print("="*50)
        print("\n次のコマンドでOCR改善システムをテストしてください:")
        print("export $(cat .env | grep -v '^#' | xargs) && python scripts/process_receipts_main.py --dry-run --limit 5")
    else:
        print("\n❌ トークン取得に失敗しました")
        print("認可コードが期限切れの可能性があります")