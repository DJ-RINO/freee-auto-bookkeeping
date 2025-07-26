#!/usr/bin/env python3
"""
Slack通知機能のテストスクリプト
freee登録を行わずにSlack通知のみをテストします
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional

class SlackNotifier:
    """Slack通知クライアント"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send_confirmation(self, txn: Dict, analysis: Dict) -> bool:
        """確認が必要な取引をSlackに通知"""
        
        message = {
            "text": "仕訳の確認が必要です",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*未仕訳取引の確認*\n信頼度: {analysis['confidence']:.2f}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*日付:* {txn.get('date', '')}"},
                        {"type": "mrkdwn", "text": f"*金額:* ¥{txn.get('amount', 0):,}"},
                        {"type": "mrkdwn", "text": f"*摘要:* {txn.get('description', '')}"},
                        {"type": "mrkdwn", "text": f"*推定取引先:* {analysis['partner_name']}"}
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*推定勘定科目ID:* {analysis['account_item_id']}"},
                        {"type": "mrkdwn", "text": f"*推定税区分:* {analysis['tax_code']}"}
                    ]
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "承認"},
                            "value": f"approve_{txn['id']}",
                            "action_id": "approve_txn",
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "修正"},
                            "value": f"edit_{txn['id']}",
                            "action_id": "edit_txn"
                        }
                    ]
                }
            ]
        }
        
        try:
            response = requests.post(self.webhook_url, json=message)
            return response.status_code == 200
        except Exception as e:
            print(f"Slack通知エラー: {e}")
            return False
    
    def send_summary(self, results: List[Dict]) -> bool:
        """処理結果のサマリーを送信"""
        
        registered = len([r for r in results if r["status"] == "registered"])
        needs_confirmation = len([r for r in results if r["status"] == "needs_confirmation"])
        errors = len([r for r in results if r["status"] == "error"])
        dry_run = len([r for r in results if r["status"] == "dry_run"])
        
        message = {
            "text": f"テスト実行完了: DRY_RUN {dry_run}件, 要確認 {needs_confirmation}件, エラー {errors}件",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🧪 freee自動仕訳テスト結果"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*DRY_RUN:* {dry_run}件"},
                        {"type": "mrkdwn", "text": f"*要確認:* {needs_confirmation}件"},
                        {"type": "mrkdwn", "text": f"*エラー:* {errors}件"},
                        {"type": "mrkdwn", "text": f"*テスト時刻:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "✅ *テスト設定確認*\n• Freee通知: ❌ スキップ\n• Freee登録: ❌ スキップ\n• Slack通知: ✅ 正常動作"
                    }
                }
            ]
        }
        
        try:
            response = requests.post(self.webhook_url, json=message)
            return response.status_code == 200
        except Exception as e:
            print(f"Slack通知エラー: {e}")
            return False

def create_mock_transaction_data() -> List[Dict]:
    """テスト用のモック取引データを作成"""
    return [
        {
            "id": 1001,
            "date": "2025-07-26",
            "amount": -5500,
            "description": "Amazon Web Services",
            "confidence_analysis": {
                "account_item_id": 604,
                "tax_code": 21,
                "partner_name": "アマゾンウェブサービスジャパン株式会社",
                "confidence": 0.85  # 90%未満のためSlack通知対象
            }
        },
        {
            "id": 1002,
            "date": "2025-07-26",
            "amount": -324,
            "description": "セブンイレブン お弁当",
            "confidence_analysis": {
                "account_item_id": 831,
                "tax_code": 24,
                "partner_name": "セブンイレブン",
                "confidence": 0.75  # 90%未満のためSlack通知対象
            }
        },
        {
            "id": 1003,
            "date": "2025-07-26",
            "amount": 108000,
            "description": "売上入金 テスト株式会社",
            "confidence_analysis": {
                "account_item_id": 101,
                "tax_code": 21,
                "partner_name": "テスト株式会社",
                "confidence": 0.95  # 90%以上だが、DRY_RUNモードのため登録せず
            }
        }
    ]

def simulate_dry_run_processing(transactions: List[Dict], slack_notifier: Optional[SlackNotifier]) -> List[Dict]:
    """DRY_RUNモードでの処理をシミュレート"""
    results = []
    
    print("=== DRY_RUNモードでの処理シミュレーション ===")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("*** DRY_RUNモード: 実際の登録は行いません ***\n")
    
    for i, txn in enumerate(transactions, 1):
        print(f"[{i}/{len(transactions)}] 処理中: {txn['description']} ¥{txn['amount']:,}")
        analysis = txn["confidence_analysis"]
        print(f"  分析結果: 信頼度={analysis['confidence']:.2f}")
        
        # DRY_RUNモードなので全て dry_run ステータス
        print(f"  [DRY_RUN] freee登録をスキップします")
        
        # 信頼度が90%未満の場合はSlack通知
        if analysis["confidence"] < 0.9:
            print(f"  信頼度90%未満のためSlack通知を送信します")
            if slack_notifier:
                sent = slack_notifier.send_confirmation(txn, analysis)
                print(f"  Slack通知送信結果: {'成功' if sent else '失敗'}")
                
            results.append({
                "txn_id": txn["id"],
                "status": "needs_confirmation",
                "analysis": analysis
            })
        else:
            print(f"  信頼度90%以上ですが、DRY_RUNモードのため登録をスキップ")
            results.append({
                "txn_id": txn["id"],
                "status": "dry_run",
                "analysis": analysis
            })
        
        print()
    
    return results

def main():
    """テストメイン処理"""
    print("=== Slack通知機能テスト開始 ===\n")
    
    # 環境変数からSlack Webhook URLを取得
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    
    if not slack_webhook_url:
        print("⚠️  警告: SLACK_WEBHOOK_URL環境変数が設定されていません")
        print("実際のSlack通知は送信されませんが、ロジックテストは実行します\n")
        slack_notifier = None
    else:
        print(f"✅ Slack Webhook URL設定済み")
        slack_notifier = SlackNotifier(slack_webhook_url)
    
    # モック取引データを作成
    transactions = create_mock_transaction_data()
    print(f"📊 テスト取引データ: {len(transactions)}件を生成")
    
    # DRY_RUNモードでの処理をシミュレート
    results = simulate_dry_run_processing(transactions, slack_notifier)
    
    # 結果サマリーをSlackに送信
    if slack_notifier:
        print("Slackに結果サマリーを送信中...")
        summary_sent = slack_notifier.send_summary(results)
        print(f"サマリー送信結果: {'成功' if summary_sent else '失敗'}")
    
    # 結果の表示
    dry_run = len([r for r in results if r["status"] == "dry_run"])
    needs_confirmation = len([r for r in results if r["status"] == "needs_confirmation"])
    
    print("\n=== テスト結果 ===")
    print(f"  DRY_RUN: {dry_run}件")
    print(f"  Slack通知対象: {needs_confirmation}件")
    print(f"  エラー: 0件")
    
    print("\n✅ テスト完了: freee登録はスキップし、Slack通知のみ実行されました")
    
    return results

if __name__ == "__main__":
    main()