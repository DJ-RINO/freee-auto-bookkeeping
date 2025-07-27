import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

CONFIDENCE_THRESHOLD = 0.9  # 90%以上で自動登録
ALWAYS_NOTIFY = os.getenv("ALWAYS_NOTIFY", "false").lower() == "true"  # 常にSlack通知するオプション

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
    
    def get_account_items(self) -> List[Dict]:
        """勘定科目一覧を取得"""
        url = f"{self.base_url}/account_items"
        params = {"company_id": self.company_id}
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json().get("account_items", [])
    
    def get_unpaid_invoices(self) -> List[Dict]:
        """未消込の請求書を取得"""
        url = f"{self.base_url}/invoices"
        params = {
            "company_id": self.company_id,
            "payment_status": "unsettled",  # 未決済のみ
            "limit": 100
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json().get("invoices", [])
    
    def match_with_invoice(self, wallet_txn: Dict, invoices: List[Dict]) -> Optional[Dict]:
        """入金と請求書をマッチング"""
        txn_amount = wallet_txn.get("amount", 0)
        txn_description = wallet_txn.get("description", "").upper()
        
        # 入金（プラス金額）のみ処理
        if txn_amount <= 0:
            return None
        
        for invoice in invoices:
            # 金額が一致するかチェック
            if invoice.get("total_amount") == txn_amount:
                # 取引先名が摘要に含まれるかチェック
                partner_name = invoice.get("partner_display_name", "").upper()
                if partner_name and partner_name in txn_description:
                    return invoice
                
                # 請求書番号が摘要に含まれるかチェック  
                invoice_number = invoice.get("invoice_number", "")
                if invoice_number and invoice_number in txn_description:
                    return invoice
        
        return None
    
    def create_invoice_payment(self, wallet_txn_id: int, invoice_id: int, amount: int) -> Dict:
        """請求書への入金消込を作成"""
        url = f"{self.base_url}/invoice_payments"
        
        data = {
            "company_id": self.company_id,
            "invoice_id": invoice_id,
            "amount": amount,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "from_walletable_type": "wallet_txn",
            "from_walletable_id": wallet_txn_id
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()


class ClaudeClient:
    """Claude API クライアント"""
    
    def __init__(self, api_key: str, account_items: List[Dict] = None):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # 勘定科目リストを受け取る
        self.account_items = account_items or []
        
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

{self._format_account_items()}

税区分参考:
- 0: 非課税
- 21: 課税仕入 10%
- 24: 課税仕入 8%（軽減）

必ずJSON形式のみで回答してください。説明や理由は含めないでください。
以下の形式で出力してください：
{"account_item_id": 数値, "tax_code": 数値, "partner_name": "文字列", "confidence": 0.0〜1.0}

confidence は 0.0〜1.0 の値で、推定の確信度を表します。
完全に確実な場合のみ 1.0 を設定してください。
"""
    
    def _format_account_items(self) -> str:
        """勘定科目リストをフォーマット"""
        if not self.account_items:
            return """勘定科目ID参考:
- 101: 売上高
- 604: 通信費  
- 607: 旅費交通費
- 650: 給料手当
- 831: 雑費"""
        
        # 主要な勘定科目のみ表示（収益・費用科目を優先）
        formatted = "利用可能な勘定科目:\n"
        for item in self.account_items[:30]:  # 最大30件
            formatted += f"- {item.get('id')}: {item.get('name')}\n"
        return formatted
    
    def analyze_transaction(self, txn: Dict) -> Dict:
        """取引を分析して勘定科目等を推定"""
        
        user_message = f"""
以下の取引を分析してください：
日付: {txn.get('date', '')}
金額: {txn.get('amount', 0)}円
摘要: {txn.get('description', '')}
"""
        
        data = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1000,
            "temperature": 0.1,
            "system": self.system_prompt,
            "messages": [
                {"role": "user", "content": user_message}
            ]
        }
        
        try:
            response = requests.post(self.base_url, headers=self.headers, json=data)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"Claude API Error: {e}")
            print(f"Response status code: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            print(f"Response body: {response.text}")
            print(f"Request URL: {self.base_url}")
            print(f"Request headers (without API key): {{'x-api-key': '***', 'anthropic-version': self.headers['anthropic-version'], 'content-type': self.headers['content-type']}}")
            raise
        
        # レスポンスからJSONを抽出
        content = response.json()["content"][0]["text"]
        try:
            # JSONブロックを探して抽出
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                # JSONオブジェクトを探す（{で始まり}で終わる部分）
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = content[json_start:json_end]
                else:
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
    
    def __init__(self, webhook_url: str, account_items: List[Dict] = None):
        self.webhook_url = webhook_url
        self.account_items = account_items or []
        
        # 勘定科目IDから名前へのマッピングを作成
        self.account_item_names = {}
        for item in self.account_items:
            self.account_item_names[item.get('id')] = item.get('name', f"ID: {item.get('id')}")
    
    def _get_tax_name(self, tax_code: int) -> str:
        """税区分コードから名前を取得"""
        tax_names = {
            0: "非課税",
            21: "課税仕入 10%",
            24: "課税仕入 8%（軽減）"
        }
        return tax_names.get(tax_code, f"コード: {tax_code}")
    
    def _get_action_message(self, txn: Dict, analysis: Dict) -> str:
        """アクションメッセージを生成"""
        is_dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        
        if is_dry_run:
            return f"📝 *DRY_RUNモード*: この取引は確認のみで登録されません。\n\n*取引ID:* `{txn['id']}`\n\n本番実行時の推定内容を確認してください。\n問題がある場合は、仕訳ルールの追加や学習データの改善をご検討ください。"
        else:
            return f"⚠️ *要対応*: この取引は自動登録されていません。\n\n*取引ID:* `{txn['id']}`\n\n以下のいずれかの方法で手動登録してください：\n1. freee管理画面から「取引の登録」→「未仕訳明細」で処理\n2. 仕訳ルールを追加して次回から自動化\n3. 信頼度向上のため、過去の類似取引を確認"
    
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
                        {"type": "mrkdwn", "text": f"*推定勘定科目:* {self.account_item_names.get(analysis['account_item_id'], '不明')} (ID: {analysis['account_item_id']})"},
                        {"type": "mrkdwn", "text": f"*推定税区分:* {self._get_tax_name(analysis['tax_code'])} (コード: {analysis['tax_code']})"}
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": self._get_action_message(txn, analysis)
                    }
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
        
        # 未処理取引の詳細を収集
        unconfirmed_details = []
        for r in results:
            if r["status"] == "needs_confirmation":
                unconfirmed_details.append(f"• TxnID `{r['txn_id']}`: 信頼度 {r.get('analysis', {}).get('confidence', 0):.2f}")
        
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
        
        # 未処理取引がある場合は追加
        if unconfirmed_details:
            unconfirmed_text = "\n".join(unconfirmed_details[:10])  # 最大10件まで
            if len(unconfirmed_details) > 10:
                unconfirmed_text += f"\n... 他 {len(unconfirmed_details) - 10}件"
            
            message["blocks"].append({
                "type": "divider"
            })
            message["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*⚠️ 要手動処理取引:*\n{unconfirmed_text}\n\n👉 freee管理画面の「取引の登録」→「未仕訳明細」から手動登録してください。"
                }
            })
        
        response = requests.post(self.webhook_url, json=message)
        return response.status_code == 200


def process_wallet_txn(txn: Dict, freee_client: FreeeClient, 
                      claude_client: ClaudeClient, 
                      slack_notifier: Optional[SlackNotifier],
                      unpaid_invoices: List[Dict] = None) -> Dict:
    """個別の取引を処理"""
    try:
        # まず請求書とのマッチングを試みる（入金の場合のみ）
        if txn.get("amount", 0) > 0 and unpaid_invoices:
            print(f"  請求書とのマッチングを確認中...")
            matched_invoice = freee_client.match_with_invoice(txn, unpaid_invoices)
            
            if matched_invoice:
                print(f"  請求書とマッチしました: {matched_invoice.get('invoice_number')} ({matched_invoice.get('partner_display_name')})")
                
                # DRY_RUNモードのチェック
                if os.getenv("DRY_RUN", "false").lower() == "true":
                    print(f"  [DRY_RUN] 請求書消込をスキップします")
                    return {
                        "txn_id": txn["id"],
                        "status": "dry_run_invoice_matched",
                        "invoice_id": matched_invoice["id"],
                        "invoice_number": matched_invoice.get("invoice_number"),
                        "partner_name": matched_invoice.get("partner_display_name")
                    }
                
                # 請求書への消込を実行
                result = freee_client.create_invoice_payment(
                    wallet_txn_id=txn["id"],
                    invoice_id=matched_invoice["id"],
                    amount=txn.get("amount", 0)
                )
                print(f"  請求書消込完了: Invoice Payment ID={result.get('invoice_payment', {}).get('id')}")
                return {
                    "txn_id": txn["id"],
                    "status": "invoice_matched",
                    "invoice_id": matched_invoice["id"],
                    "invoice_payment_id": result.get("invoice_payment", {}).get("id")
                }
        
        # 請求書とマッチしない場合は、通常の分析処理
        print(f"  分析中: {txn.get('description', '')}")
        analysis = claude_client.analyze_transaction(txn)
        print(f"  分析結果: 信頼度={analysis['confidence']:.2f}")

        # DRY_RUNモードのチェック
        if os.getenv("DRY_RUN", "false").lower() == "true":
            print(f"  [DRY_RUN] 登録をスキップします")
            
            # DRY_RUNモードでも通知を送る条件
            # 1. 信頼度が低い取引
            # 2. ALWAYS_NOTIFYがtrueの場合は全て
            if slack_notifier and (analysis["confidence"] < CONFIDENCE_THRESHOLD or ALWAYS_NOTIFY):
                print(f"  信頼度{analysis['confidence']:.2f}の取引をSlackに通知します")
                sent = slack_notifier.send_confirmation(txn, analysis)
                print(f"  Slack通知送信結果: {sent}")
            
            return {
                "txn_id": txn["id"],
                "status": "dry_run",
                "analysis": analysis
            }

        # 90%以上は自動登録（ALWAYS_NOTIFYがtrueの場合は通知も送る）
        if analysis["confidence"] >= CONFIDENCE_THRESHOLD:
            if ALWAYS_NOTIFY and slack_notifier:
                print(f"  信頼度{analysis['confidence']:.2f}の取引をSlackに通知します（確認用）")
                sent = slack_notifier.send_confirmation(txn, analysis)
                print(f"  Slack通知送信結果: {sent}")
            
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
        import traceback
        traceback.print_exc()
        return {
            "txn_id": txn["id"],
            "status": "error",
            "error": str(e)
        }


def save_results(results: List[Dict]):
    """処理結果をJSONファイルに保存"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results_{timestamp}.json"
    
    # 統計情報を計算
    stats = {
        "total": len(results),
        "registered": len([r for r in results if r["status"] == "registered"]),
        "invoice_matched": len([r for r in results if r["status"] == "invoice_matched"]),
        "needs_confirmation": len([r for r in results if r["status"] == "needs_confirmation"]),
        "errors": len([r for r in results if r["status"] == "error"]),
        "dry_run": len([r for r in results if r["status"] == "dry_run"]),
        "dry_run_invoice_matched": len([r for r in results if r["status"] == "dry_run_invoice_matched"])
    }
    
    # 要手動処理の取引IDリスト
    unprocessed_txn_ids = [
        r["txn_id"] for r in results 
        if r["status"] in ["needs_confirmation", "error"]
    ]
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "environment": {
                "dry_run": os.getenv("DRY_RUN", "false"),
                "always_notify": os.getenv("ALWAYS_NOTIFY", "false"),
                "confidence_threshold": CONFIDENCE_THRESHOLD
            },
            "statistics": stats,
            "unprocessed_transaction_ids": unprocessed_txn_ids,
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
    claude_api_key = os.getenv("FREEE_CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    
    # Slack環境変数のデバッグ情報
    print("\n[Slack設定の確認]")
    print(f"  - SLACK_WEBHOOK_URL が設定されているか: {'はい' if slack_webhook_url else 'いいえ'}")
    if slack_webhook_url:
        print(f"  - URLの長さ: {len(slack_webhook_url)}文字")
        print(f"  - URLの最初の部分: {slack_webhook_url[:30]}...")
    else:
        print("  - 注意: SLACK_WEBHOOK_URL が空です。GitHub Secretsを確認してください。")
    
    # 必須パラメータのチェック
    if not freee_access_token or not freee_company_id or not claude_api_key:
        print("エラー: 必須の環境変数が設定されていません")
        print("FREEE_ACCESS_TOKEN, FREEE_COMPANY_ID, FREEE_CLAUDE_API_KEY を確認してください")
        return []
    
    # Claude API キーのデバッグ情報
    print(f"\n[Claude API設定]")
    print(f"  - APIキー設定: あり")
    print(f"  - キーの最初の10文字: {claude_api_key[:10]}...")
    print(f"  - キーの長さ: {len(claude_api_key)}文字")
    print(f"  - キーの形式: {'✓ Anthropic形式' if claude_api_key.startswith('sk-ant-') else '? 不明な形式'}")
    
    # DRY_RUNモードの表示
    if os.getenv("DRY_RUN", "false").lower() == "true":
        print("\n*** DRY_RUNモード: 実際の登録は行いません ***\n")
    
    # 取引数制限の取得
    transaction_limit = int(os.getenv("TRANSACTION_LIMIT", "100"))
    print(f"📊 取引処理上限: {transaction_limit}件")
    
    # クライアントの初期化
    freee_client = FreeeClient(freee_access_token, freee_company_id)
    
    # 勘定科目リストを取得
    print("勘定科目マスタを取得中...")
    try:
        account_items = freee_client.get_account_items()
        print(f"  {len(account_items)}件の勘定科目を取得しました")
        
        # 主要な勘定科目をデバッグ表示（最初の10件）
        if account_items:
            print("  主要な勘定科目:")
            for item in account_items[:10]:
                print(f"    - {item.get('id')}: {item.get('name')}")
    except Exception as e:
        print(f"  勘定科目の取得に失敗しました: {e}")
        account_items = []
    
    claude_client = ClaudeClient(claude_api_key, account_items)
    slack_notifier = SlackNotifier(slack_webhook_url, account_items) if slack_webhook_url else None
    
    try:
        # 未仕訳明細の取得
        print("\n未仕訳明細を取得中...")
        wallet_txns = freee_client.get_unmatched_wallet_txns(limit=transaction_limit)
        print(f"{len(wallet_txns)}件の未仕訳明細を取得しました")
        
        if not wallet_txns:
            print("処理対象の明細はありません")
            return []
        
        # 未消込請求書の取得
        print("\n未消込請求書を取得中...")
        try:
            unpaid_invoices = freee_client.get_unpaid_invoices()
            print(f"{len(unpaid_invoices)}件の未消込請求書を取得しました")
        except Exception as e:
            print(f"  未消込請求書の取得に失敗しました: {e}")
            unpaid_invoices = []
        
        # 各取引の処理
        print("\n取引を処理中...")
        results = []
        for i, txn in enumerate(wallet_txns, 1):
            print(f"\n[{i}/{len(wallet_txns)}] 処理中: {txn.get('description', 'No description')} ¥{txn.get('amount', 0):,}")
            result = process_wallet_txn(txn, freee_client, claude_client, slack_notifier, unpaid_invoices)
            results.append(result)
        
        # 結果の保存
        save_results(results)
        
        # サマリーの送信（DRY_RUNモードでも送信）
        if slack_notifier:
            print("\nSlackに結果を送信中...")
            slack_notifier.send_summary(results)
        
        # 結果の出力
        registered = len([r for r in results if r["status"] == "registered"])
        invoice_matched = len([r for r in results if r["status"] == "invoice_matched"])
        needs_confirmation = len([r for r in results if r["status"] == "needs_confirmation"])
        errors = len([r for r in results if r["status"] == "error"])
        dry_run = len([r for r in results if r["status"] == "dry_run"])
        dry_run_invoice = len([r for r in results if r["status"] == "dry_run_invoice_matched"])
        
        print("\n=== 処理完了 ===")
        print(f"  自動登録: {registered}件")
        print(f"  請求書消込: {invoice_matched}件")
        print(f"  要確認: {needs_confirmation}件")
        print(f"  エラー: {errors}件")
        if dry_run > 0 or dry_run_invoice > 0:
            print(f"  DRY_RUN: {dry_run + dry_run_invoice}件 (うち請求書消込: {dry_run_invoice}件)")
        
        return results
        
    except Exception as e:
        print(f"\n致命的なエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    main()