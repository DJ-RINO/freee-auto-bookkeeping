#!/usr/bin/env python
"""
レシート紐付け専用のメインスクリプト
ファイルボックスのレシート/領収書を取引に紐付ける
"""

import os
import sys
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from token_manager import FreeeTokenManager
from state_store import init_db, write_audit
from config_loader import load_linking_config
from filebox_client import FileBoxClient
from ocr_models import ReceiptRecord
from matcher import find_best_target, normalize_targets
from linker import ensure_not_duplicated_and_link, decide_action
from notifier import SlackNotifier

class FreeeClient:
    """freee APIクライアント（レシート処理用）"""
    
    def __init__(self, access_token: str, company_id: int):
        self.access_token = access_token
        self.company_id = company_id
        self.base_url = "https://api.freee.co.jp/api/1"
        
    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def get_wallet_transactions(self, limit: int = 100):
        """明細一覧を取得（未仕訳・仕訳済み両方）"""
        import requests
        url = f"{self.base_url}/wallet_txns"
        params = {
            "company_id": self.company_id,
            "limit": limit,
            "walletable_type": "bank_account"
        }
        
        response = requests.get(url, headers=self.get_headers(), params=params)
        if response.status_code == 200:
            return response.json().get("wallet_txns", [])
        return []
    
    def get_deals(self, limit: int = 100):
        """登録済み取引を取得"""
        import requests
        url = f"{self.base_url}/deals"
        params = {
            "company_id": self.company_id,
            "limit": limit
        }
        
        response = requests.get(url, headers=self.get_headers(), params=params)
        if response.status_code == 200:
            return response.json().get("deals", [])
        return []
    
    def attach_receipt_to_tx(self, tx_id: int, receipt_id: int):
        """レシートを明細に紐付け"""
        import requests
        url = f"{self.base_url}/wallet_txns/{tx_id}/receipts/{receipt_id}"
        params = {"company_id": self.company_id}
        
        response = requests.put(url, headers=self.get_headers(), params=params)
        return response.json() if response.status_code in (200, 201) else None
    
    def attach_receipt_to_deal(self, deal_id: int, receipt_id: int):
        """レシートを取引に紐付け"""
        # TODO: API実装待ち
        print(f"[INFO] 取引への紐付けAPI未実装: deal_id={deal_id}, receipt_id={receipt_id}")
        return None


def main():
    """メイン処理"""
    print("=== レシート紐付け処理を開始 ===")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 環境変数取得
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    receipt_limit = int(os.getenv("RECEIPT_LIMIT", "50"))
    target_type = os.getenv("TARGET_TYPE", "both")
    
    if dry_run:
        print("⚠️ DRY_RUNモード: 実際の紐付けは行いません")
    
    # データベース初期化
    init_db()
    
    # トークン管理
    token_manager = FreeeTokenManager()
    access_token = token_manager.ensure_valid_token()
    
    if not access_token:
        print("❌ アクセストークンの取得に失敗しました")
        return
    
    company_id = int(os.getenv("FREEE_COMPANY_ID"))
    
    # クライアント初期化
    freee_client = FreeeClient(access_token, company_id)
    filebox_client = FileBoxClient(access_token, company_id)
    
    # 設定読み込み
    linking_cfg = load_linking_config()
    
    # Slack通知準備
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    notifier = SlackNotifier(slack_url) if slack_url else None
    
    # ファイルボックスからレシート取得
    print("\n📎 ファイルボックスからレシート取得中...")
    try:
        receipts = filebox_client.list_receipts(limit=receipt_limit)
        print(f"  {len(receipts)}件のレシートを取得")
    except Exception as e:
        print(f"❌ レシート取得エラー: {e}")
        return
    
    if not receipts:
        print("  処理対象のレシートはありません")
        if notifier:
            notifier.send({
                "text": "📎 レシート紐付け: 処理対象なし",
                "blocks": [{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "ファイルボックスに未処理のレシートがありません"
                    }
                }]
            })
        return
    
    # 紐付け対象の取引を取得
    print("\n💳 紐付け対象の取引を取得中...")
    targets = []
    
    if target_type in ("both", "wallet_txn"):
        wallet_txns = freee_client.get_wallet_transactions(limit=200)
        print(f"  明細: {len(wallet_txns)}件")
        targets.extend(normalize_targets(wallet_txns, []))
    
    if target_type in ("both", "deal"):
        deals = freee_client.get_deals(limit=200)
        print(f"  取引: {len(deals)}件")
        # TODO: dealsのnormalize実装
        # targets.extend(normalize_targets([], deals))
    
    if not targets:
        print("❌ 紐付け対象の取引がありません")
        return
    
    # レシート処理
    print("\n🔄 レシート紐付け処理中...")
    results = {
        "auto": 0,
        "assist": 0,
        "manual": 0,
        "error": 0,
        "skipped": 0
    }
    
    for i, receipt in enumerate(receipts, 1):
        receipt_id = str(receipt.get("id"))
        print(f"\n[{i}/{len(receipts)}] レシートID: {receipt_id}")
        
        try:
            # レシートデータダウンロード
            data = filebox_client.download_receipt(int(receipt_id))
            file_sha1 = FileBoxClient.sha1_of_bytes(data)
            
            # レシートレコード作成
            rec = ReceiptRecord(
                receipt_id=receipt_id,
                file_hash=file_sha1,
                vendor=receipt.get("description", "") or receipt.get("user_name", ""),
                date=datetime.fromisoformat(receipt.get("created_at", "")).date(),
                amount=abs(int(receipt.get("amount", 0)))
            )
            
            print(f"  店舗: {rec.vendor}, 金額: ¥{rec.amount:,}, 日付: {rec.date}")
            
            # 最適な取引を検索
            best = find_best_target(rec, targets, linking_cfg)
            
            if not best:
                print("  ⚠️ 適合する取引が見つかりません")
                results["manual"] += 1
                continue
            
            score = best.get("score", 0)
            action = decide_action(score, linking_cfg)
            
            print(f"  マッチング: スコア {score}点 → {action}")
            print(f"  対象取引: ID={best.get('id')}, 金額=¥{best.get('amount', 0):,}")
            
            if dry_run:
                print("  🔵 DRY_RUN: 紐付けをスキップ")
                results["skipped"] += 1
                continue
            
            if action == "AUTO":
                # 自動紐付け
                ensure_not_duplicated_and_link(
                    freee_client,
                    rec,
                    file_sha1,
                    best,
                    linking_cfg,
                    target_type=best.get("type", "wallet_txn"),
                    allow_delete=False
                )
                print("  ✅ 自動紐付け完了")
                results["auto"] += 1
                
            elif action == "ASSIST":
                # Slack確認
                if notifier:
                    print("  📨 Slack確認通知を送信")
                    # TODO: インタラクティブメッセージ実装
                    results["assist"] += 1
                else:
                    results["manual"] += 1
                    
            else:
                results["manual"] += 1
                
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            results["error"] += 1
            write_audit("ERROR", "receipt_linking", "process", [receipt_id], 0, "failed", str(e))
    
    # 結果サマリー
    print("\n" + "=" * 50)
    print("📊 処理結果サマリー")
    print(f"  自動紐付け: {results['auto']}件")
    print(f"  確認待ち: {results['assist']}件")
    print(f"  手動対応: {results['manual']}件")
    print(f"  スキップ: {results['skipped']}件")
    print(f"  エラー: {results['error']}件")
    
    # 結果を保存
    result_file = f"receipt_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "execution_time": datetime.now().isoformat(),
            "dry_run": dry_run,
            "results": results,
            "processed_receipts": len(receipts)
        }, f, ensure_ascii=False, indent=2)
    
    # Slack通知
    if notifier and not dry_run:
        notifier.send({
            "text": f"📎 レシート紐付け完了",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*レシート紐付け処理完了*\n処理件数: {len(receipts)}件"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*自動紐付け:* {results['auto']}件"},
                        {"type": "mrkdwn", "text": f"*確認待ち:* {results['assist']}件"},
                        {"type": "mrkdwn", "text": f"*手動対応:* {results['manual']}件"},
                        {"type": "mrkdwn", "text": f"*エラー:* {results['error']}件"}
                    ]
                }
            ]
        })
    
    print("\n✅ レシート紐付け処理完了")


if __name__ == "__main__":
    main()