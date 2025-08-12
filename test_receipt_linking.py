#!/usr/bin/env python
"""
レシート紐付け処理のテストスクリプト
GitHub Secretsの設定がある場合はGitHub Actionsで実行推奨
"""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def check_env():
    """環境変数のチェック"""
    load_dotenv()
    
    required = {
        'FREEE_ACCESS_TOKEN': os.getenv('FREEE_ACCESS_TOKEN'),
        'FREEE_COMPANY_ID': os.getenv('FREEE_COMPANY_ID'),
    }
    
    missing = [k for k, v in required.items() if not v or v.startswith('your_')]
    
    if missing:
        print("❌ 必要な環境変数が設定されていません:")
        for var in missing:
            print(f"  - {var}")
        print("\n以下の方法で実行してください:")
        print("1. GitHub Actionsの 'Auto Bookkeeping' ワークフローを実行")
        print("2. .envファイルに必要な情報を設定")
        return False
    
    print("✅ 環境変数チェック完了")
    return True

def main():
    """メイン処理"""
    if not check_env():
        return
    
    print("\n📋 レシート紐付け処理を開始します...")
    print("-" * 40)
    
    try:
        # Import after env check
        from src.main import FreeeClient, process_receipts
        from src.state_store import init_db
        
        # Initialize database
        init_db()
        
        # Initialize freee client
        freee_client = FreeeClient(
            access_token=os.getenv('FREEE_ACCESS_TOKEN'),
            company_id=int(os.getenv('FREEE_COMPANY_ID'))
        )
        
        # Process receipts
        process_receipts(freee_client)
        
        print("\n✅ レシート紐付け処理が完了しました")
        
    except ImportError as e:
        print(f"❌ モジュールのインポートエラー: {e}")
        print("requirements.txt から依存関係をインストールしてください:")
        print("  pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()