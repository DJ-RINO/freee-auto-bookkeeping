#!/usr/bin/env python3
"""
Claude API動作テスト
GitHub Secretsと同じAPIキーでローカルテスト
"""

import os
from anthropic import Anthropic

def test_claude_api():
    # 環境変数からAPIキーを取得（GitHub Secretsと同じ方法）
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key:
        print("❌ ANTHROPIC_API_KEY環境変数が設定されていません")
        print("以下のコマンドで設定してください：")
        print("export ANTHROPIC_API_KEY='your-api-key'")
        return
    
    print(f"🔑 APIキー: {api_key[:20]}...{api_key[-10:]}")
    
    try:
        # Claude APIクライアント初期化
        client = Anthropic(api_key=api_key)
        
        print("🚀 Claude APIテスト実行中...")
        
        # シンプルなテストリクエスト
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",  # 最新モデル名
            max_tokens=100,
            messages=[{
                "role": "user", 
                "content": "Hello! APIテストです。簡単に挨拶してください。"
            }]
        )
        
        print("✅ Claude API 正常動作！")
        print(f"レスポンス: {response.content[0].text}")
        
    except Exception as e:
        print(f"❌ Claude API エラー: {e}")
        print(f"エラータイプ: {type(e).__name__}")
        
        if "api_key" in str(e).lower():
            print("💡 APIキーに問題がある可能性があります")
        elif "rate" in str(e).lower():
            print("💡 レート制限に引っかかっている可能性があります")
        elif "region" in str(e).lower():
            print("💡 地域制限がある可能性があります")

if __name__ == "__main__":
    test_claude_api()