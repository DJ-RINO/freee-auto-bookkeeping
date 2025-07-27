"""
Slackインタラクティブメッセージのハンドラー
※ 注意: この機能を使用するには、SlackアプリでInteractive Componentsを有効にし、
Request URLを設定する必要があります。
"""

import os
import json
from typing import Dict, List
from flask import Flask, request, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

# freeeとの連携用
FREEE_BASE_URL = "https://api.freee.co.jp/api/1"
FREEE_ACCESS_TOKEN = os.getenv("FREEE_ACCESS_TOKEN")
FREEE_COMPANY_ID = os.getenv("FREEE_COMPANY_ID")


def create_interactive_message(txn: Dict, analysis: Dict) -> Dict:
    """インタラクティブなSlackメッセージを作成"""
    
    # 勘定科目の選択肢を作成
    account_options = [
        {"text": {"type": "plain_text", "text": "101: 売上高"}, "value": "101"},
        {"text": {"type": "plain_text", "text": "604: 通信費"}, "value": "604"},
        {"text": {"type": "plain_text", "text": "607: 旅費交通費"}, "value": "607"},
        {"text": {"type": "plain_text", "text": "650: 給料手当"}, "value": "650"},
        {"text": {"type": "plain_text", "text": "831: 雑費"}, "value": "831"},
    ]
    
    # 税区分の選択肢
    tax_options = [
        {"text": {"type": "plain_text", "text": "0: 非課税"}, "value": "0"},
        {"text": {"type": "plain_text", "text": "21: 課税仕入 10%"}, "value": "21"},
        {"text": {"type": "plain_text", "text": "24: 課税仕入 8%（軽減）"}, "value": "24"},
    ]
    
    return {
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
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*推定結果を修正できます:*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "勘定科目:"
                },
                "accessory": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": f"現在: {analysis['account_item_id']}"
                    },
                    "options": account_options,
                    "action_id": f"account_select_{txn['id']}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "税区分:"
                },
                "accessory": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": f"現在: {analysis['tax_code']}"
                    },
                    "options": tax_options,
                    "action_id": f"tax_select_{txn['id']}"
                }
            },
            {
                "type": "input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": f"partner_input_{txn['id']}",
                    "initial_value": analysis['partner_name']
                },
                "label": {
                    "type": "plain_text",
                    "text": "取引先名"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "登録する"
                        },
                        "style": "primary",
                        "action_id": f"approve_{txn['id']}",
                        "value": json.dumps({
                            "txn_id": txn['id'],
                            "account_item_id": analysis['account_item_id'],
                            "tax_code": analysis['tax_code'],
                            "partner_name": analysis['partner_name']
                        })
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "スキップ"
                        },
                        "action_id": f"skip_{txn['id']}"
                    }
                ]
            }
        ]
    }


@app.route('/slack/interactive', methods=['POST'])
def handle_interactive():
    """Slackからのインタラクティブメッセージを処理"""
    payload = json.loads(request.form['payload'])
    
    # アクションタイプの判定
    action = payload['actions'][0]
    action_id = action['action_id']
    
    if action_id.startswith('approve_'):
        # 登録処理
        txn_id = int(action_id.replace('approve_', ''))
        values = json.loads(action['value'])
        
        # freee APIで取引を登録
        result = create_freee_deal(
            txn_id,
            values['account_item_id'],
            values['tax_code'],
            values['partner_name']
        )
        
        # Slackメッセージを更新
        update_message(payload['response_url'], {
            "text": f"✅ 取引を登録しました (Deal ID: {result['deal']['id']})",
            "replace_original": True
        })
        
    elif action_id.startswith('skip_'):
        # スキップ処理
        update_message(payload['response_url'], {
            "text": "⏭️ この取引をスキップしました",
            "replace_original": True
        })
    
    return jsonify({"status": "ok"})


def create_freee_deal(wallet_txn_id: int, account_item_id: int, 
                     tax_code: int, partner_name: str) -> Dict:
    """freee APIで取引を作成"""
    headers = {
        "Authorization": f"Bearer {FREEE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # wallet_txnの詳細を取得
    txn_url = f"{FREEE_BASE_URL}/wallet_txns/{wallet_txn_id}"
    txn_response = requests.get(txn_url, headers=headers, params={"company_id": FREEE_COMPANY_ID})
    txn_detail = txn_response.json().get("wallet_txn", {})
    
    amount = abs(txn_detail.get("amount", 0))
    txn_type = "income" if txn_detail.get("amount", 0) > 0 else "expense"
    
    # 取引作成
    deal_url = f"{FREEE_BASE_URL}/deals"
    data = {
        "company_id": FREEE_COMPANY_ID,
        "issue_date": datetime.now().strftime("%Y-%m-%d"),
        "type": txn_type,
        "details": [{
            "account_item_id": account_item_id,
            "tax_code": tax_code,
            "amount": amount
        }],
        "payments": [{
            "from_walletable_type": "wallet_txn",
            "from_walletable_id": wallet_txn_id,
            "amount": amount
        }]
    }
    
    response = requests.post(deal_url, headers=headers, json=data)
    return response.json()


def update_message(response_url: str, message: Dict):
    """Slackメッセージを更新"""
    requests.post(response_url, json=message)


if __name__ == "__main__":
    # このサーバーを別途起動する必要があります
    # ngrokなどを使ってローカル開発環境を公開し、
    # SlackアプリのInteractivity Request URLに設定してください
    app.run(port=3000, debug=True)