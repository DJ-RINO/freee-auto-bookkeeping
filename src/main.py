import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

CONFIDENCE_THRESHOLD = 0.9  # 90%以上で自動登録

class FreeeClient:
    """freee API クライアント"""
    
    def __init__(self, access_token: str, company_id: int):
        self.access_token = access_token
        self.company_id = company_id
        self.base_url = "https://api.freee.co.jp/api/1"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def get_unmatched_wallet_txns(self, limit: int = 100) -> List[Dict]:
        """未仕訳の入出金明細を取得"""
        url = f"{self.base_url}/wallet_txns"
        params = {
            "company_id": self.company_id,
            "status": "unmatched",
            "limit": limit
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json().get("wallet_txns", [])
    
    def create_deal(self, wallet_txn_id: int, account_item_id: int, 
                   tax_code: int, partner_name: str, amount: int = None,
                   txn_type: str = None) -> Dict:
        """取引を登録"""
        url = f"{self.base_url}/deals"
        
        # wallet_txnの詳細を取得してamountとtypeを判定
        if amount is None or txn_type is None:
            txn_detail = self._get_wallet_txn_detail(wallet_txn_id)
            amount = abs(txn_detail.get("amount", 0))
            # 金額の正負で収入/支出を判定
            txn_type = "income" if txn_detail.get("amount", 0) > 0 else "expense"
        
        # 取引先の検索または作成
        partner_id = self._get_or_create_partner(partner_name) if partner_name else None
        
        data = {
            "company_id": self.company_id,
            "issue_date": datetime.now().strftime("%Y-%m-%d"),
            "type": txn_type,
            "details": [{
                "account_item_id": account_item_id,
                "tax_code": tax_code,
                "amount": amount
            }]
        }
        
        # 取引先IDがある場合は追加
        if partner_id:
            data["partner_id"] = partner_id
        
        # wallet_txnとの紐付け
        data["payments"] = [{
            "from_walletable_type": "wallet_txn",
            "from_walletable_id": wallet_txn_id,
            "amount": amount
        }]
        
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def _get_wallet_txn_detail(self, wallet_txn_id: int) -> Dict:
        """wallet_txnの詳細を取得"""
        url = f"{self.base_url}/wallet_txns/{wallet_txn_id}"
        params = {"company_id": self.company_id}
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json().get("wallet_txn", {})
    
    def _get_or_create_partner(self, partner_name: str) -> Optional[int]:
        """取引先を検索し、なければ作成"""
        # まず検索
        url = f"{self.base_url}/partners"
        params = {
            "company_id": self.company_id,
            "keyword": partner_name
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        partners = response.json().get("partners", [])
        
        # 完全一致する取引先があれば返す
        for partner in partners:
            if partner.get("name") == partner_name:
                return partner["id"]
        
        # なければ作成
        create_url = f"{self.base_url}/partners"
        data = {
            "company_id": self.company_id,
            "name": partner_name
        }
        
        response = requests.post(create_url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()["partner"]["id"]


class ClaudeClient:
    """Claude API クライアント"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # Few-shot examples for system prompt
        self.system_prompt = """
あなたは日本の会計・経理の専門家です。
入出金明細から適切な勘定科目、税区分、取引先名を推定してください。

以下の例を参考にしてください：

例1: {"description": "Amazon Web Services", "amount": -5500}
→ {"account_item_id": 604, "tax_code": 21, "partner_name": "アマゾンウェブサービスジャパン株式会社", "confidence": 0.95}

例2: {"description": "セブンイレブン", "amount": -324}
→ {"account_item_id": 831, "tax_code": 24, "partner_name": "セブンイレブン", "confidence": 0.90}

例3: {"description": "売上入金 ○○商事", "amount": 108000}
→ {"account_item_id": 101, "tax_code": 21, "partner_name": "○○商事", "confidence": 0.85}

例4: {"description": "JR東日本 交通費", "amount": -2200}
→ {"account_item_id": 607, "tax_code": 21, "partner_name": "JR東日本", "confidence": 0.92}

例5: {"description": "給与振込", "amount": -250000}
→ {"account_item_id": 650, "tax_code": 0, "partner_name": "従業員", "confidence": 0.88}

勘定科目ID参考:
- 101: 売上高
- 604: 通信費
- 607: 旅費交通費
- 650: 給料手当
- 831: 雑費

税区分参考:
- 0: 非課税
- 21: 課税仕入 10%
- 24: 課税仕入 8%（軽減）

必ずJSON形式で回答してください。
confidence は 0.0〜1.0 の値で、推定の確信度を表します。
完全に確実な場合のみ 1.0 を設定してください。
"""
    
    def analyze_transaction(self, txn: Dict) -> Dict:
        """取引を分析して勘定科目等を推定"""
        
        user_message = f"""
以下の取引を分析してください：
日付: {txn.get('date', '')}
金額: {txn.get('amount', 0)}円
摘要: {txn.get('description', '')}
"""
        
        data = {
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 1000,
            "temperature": 0.1,
            "system": self.system_prompt,
            "messages": [
                {"role": "user", "content": user_message}
            ]
        }
        
        response = requests.post(self.base_url, headers=self.headers, json=data)
        response.raise_for_status()
        
        # レスポンスからJSONを抽出
        content = response.json()["content"][0]["text"]
        try:
            # JSONブロックを探して抽出
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                # JSONらしい部分を抽出
                json_str = content.strip()
                if json_str.startswith("```") and json_str.endswith("```"):
                    json_str = json_str[3:-3].strip()
            
            return json.loads(json_str)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"JSON parse error: {e}")
            print(f"Content: {content}")
            # JSONパースエラーの場合はデフォルト値を返す
            return {
                "account_item_id": 999,
                "tax_code": 0,
                "partner_name": "不明",
                "confidence": 0.0
            }


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
        
        response = requests.post(self.webhook_url, json=message)
        return response.status_code == 200
    
    def send_summary(self, results: List[Dict]) -> bool:
        """処理結果のサマリーを送信"""
        
        registered = len([r for r in results if r["status"] == "registered"])
        needs_confirmation = len([r for r in results if r["status"] == "needs_confirmation"])
        errors = len([r for r in results if r["status"] == "error"])
        
        # エラー詳細を収集
        error_details = []
        for r in results:
            if r["status"] == "error":
                error_details.append(f"• TxnID {r['txn_id']}: {r.get('error', 'Unknown error')}")
        
        message = {
            "text": f"仕訳処理完了: 登録 {registered}件, 要確認 {needs_confirmation}件, エラー {errors}件",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "仕訳処理結果"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*自動登録:* {registered}件"},
                        {"type": "mrkdwn", "text": f"*要確認:* {needs_confirmation}件"},
                        {"type": "mrkdwn", "text": f"*エラー:* {errors}件"},
                        {"type": "mrkdwn", "text": f"*処理時刻:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
                    ]
                }
            ]
        }
        
        # エラーがある場合は詳細を追加
        if error_details:
            error_text = "\n".join(error_details[:10])  # 最大10件まで
            if len(error_details) > 10:
                error_text += f"\n... 他 {len(error_details) - 10}件"
            
            message["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*エラー詳細:*\n{error_text}"
                }
            })
        
        response = requests.post(self.webhook_url, json=message)
        return response.status_code == 200


def process_wallet_txn(txn: Dict, freee_client: FreeeClient, 
                      claude_client: ClaudeClient, 
                      slack_notifier: Optional[SlackNotifier]) -> Dict:
    """個別の取引を処理"""
    try:
        # Claude APIで分析
        print(f"  分析中: {txn.get('description', '')}")
        analysis = claude_client.analyze_transaction(txn)
        print(f"  分析結果: 信頼度={analysis['confidence']:.2f}")

        # DRY_RUNモードのチェック
        if os.getenv("DRY_RUN", "false").lower() == "true":
            print(f"  [DRY_RUN] 登録をスキップします")
            return {
                "txn_id": txn["id"],
                "status": "dry_run",
                "analysis": analysis
            }

        # 90%以上は自動登録
        if analysis["confidence"] >= CONFIDENCE_THRESHOLD:
            print(f"  信頼度90%以上のため自動登録を実行中...")
            result = freee_client.create_deal(
                wallet_txn_id=txn["id"],
                account_item_id=analysis["account_item_id"],
                tax_code=analysis["tax_code"],
                partner_name=analysis["partner_name"],
                amount=abs(txn.get("amount", 0)),
                txn_type="income" if txn.get("amount", 0) > 0 else "expense"
            )
            print(f"  登録完了: Deal ID={result['deal']['id']}")
            return {
                "txn_id": txn["id"],
                "status": "registered",
                "deal_id": result["deal"]["id"],
                "analysis": analysis
            }
        else:
            # 90%未満は全てSlack通知
            print(f"  信頼度90%未満のためSlack通知を送信します（信頼度: {analysis['confidence']:.2f}）")
            if slack_notifier:
                sent = slack_notifier.send_confirmation(txn, analysis)
                print(f"  Slack通知送信結果: {sent}")
            return {
                "txn_id": txn["id"],
                "status": "needs_confirmation",
                "analysis": analysis
            }

    except Exception as e:
        print(f"  エラー: {str(e)}")
        return {
            "txn_id": txn["id"],
            "status": "error",
            "error": str(e)
        }


def save_results(results: List[Dict]):
    """処理結果をJSONファイルに保存"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results_{timestamp}.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n結果を {filename} に保存しました")


def main():
    """メイン処理"""
    
    print("=== freee自動仕訳処理を開始します ===")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # トークンの自動更新を試みる
    try:
        from token_manager import integrate_with_main
        freee_access_token = integrate_with_main()
        print("トークン管理システムを使用しています")
    except Exception as e:
        print(f"トークン自動更新をスキップ: {e}")
        # フォールバック：環境変数から直接取得
        freee_access_token = os.getenv("FREEE_ACCESS_TOKEN")
    
    # その他の環境変数の読み込み
    freee_company_id = int(os.getenv("FREEE_COMPANY_ID", "0"))
    claude_api_key = os.getenv("CLAUDE_API_KEY")
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    
    # 必須パラメータのチェック
    if not freee_access_token or not freee_company_id or not claude_api_key:
        print("エラー: 必須の環境変数が設定されていません")
        print("FREEE_ACCESS_TOKEN, FREEE_COMPANY_ID, CLAUDE_API_KEY を確認してください")
        return []
    
    # DRY_RUNモードの表示
    if os.getenv("DRY_RUN", "false").lower() == "true":
        print("\n*** DRY_RUNモード: 実際の登録は行いません ***\n")
    
    # クライアントの初期化
    freee_client = FreeeClient(freee_access_token, freee_company_id)
    claude_client = ClaudeClient(claude_api_key)
    slack_notifier = SlackNotifier(slack_webhook_url) if slack_webhook_url else None
    
    try:
        # 未仕訳明細の取得
        print("\n未仕訳明細を取得中...")
        wallet_txns = freee_client.get_unmatched_wallet_txns()
        print(f"{len(wallet_txns)}件の未仕訳明細を取得しました")
        
        if not wallet_txns:
            print("処理対象の明細はありません")
            return []
        
        # 各取引の処理
        print("\n取引を処理中...")
        results = []
        for i, txn in enumerate(wallet_txns, 1):
            print(f"\n[{i}/{len(wallet_txns)}] 処理中: {txn.get('description', 'No description')} ¥{txn.get('amount', 0):,}")
            result = process_wallet_txn(txn, freee_client, claude_client, slack_notifier)
            results.append(result)
        
        # 結果の保存
        save_results(results)
        
        # サマリーの送信
        if slack_notifier and not os.getenv("DRY_RUN", "false").lower() == "true":
            print("\nSlackに結果を送信中...")
            slack_notifier.send_summary(results)
        
        # 結果の出力
        registered = len([r for r in results if r["status"] == "registered"])
        needs_confirmation = len([r for r in results if r["status"] == "needs_confirmation"])
        errors = len([r for r in results if r["status"] == "error"])
        dry_run = len([r for r in results if r["status"] == "dry_run"])
        
        print("\n=== 処理完了 ===")
        print(f"  自動登録: {registered}件")
        print(f"  要確認: {needs_confirmation}件")
        print(f"  エラー: {errors}件")
        if dry_run > 0:
            print(f"  DRY_RUN: {dry_run}件")
        
        return results
        
    except Exception as e:
        print(f"\n致命的なエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    main()