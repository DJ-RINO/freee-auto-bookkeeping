import os
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
from dotenv import load_dotenv

# 他のモジュールをインポート
try:
    from learning_system import TransactionLearningSystem
except ImportError:
    TransactionLearningSystem = None

try:
    from data_importer import FreeeDataImporter
except ImportError:
    FreeeDataImporter = None

load_dotenv()

CONFIDENCE_THRESHOLD = 0.9  # 90%以上で自動登録（元の設定に戻す）

class IntegratedFreeeClient:
    """統合版freee API クライアント（全機能搭載）"""
    
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
    
    def get_historical_deals(self, days: int = 365, limit: int = 100) -> List[Dict]:
        """過去の仕訳済み取引を取得"""
        url = f"{self.base_url}/deals"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        params = {
            "company_id": self.company_id,
            "start_issue_date": start_date.strftime("%Y-%m-%d"),
            "end_issue_date": end_date.strftime("%Y-%m-%d"),
            "limit": limit
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json().get("deals", [])
    
    def get_account_items(self) -> Dict[int, str]:
        """勘定科目一覧を取得"""
        url = f"{self.base_url}/account_items"
        params = {"company_id": self.company_id}
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        # ID -> 名称のマッピングを作成
        items = {}
        for item in response.json().get("account_items", []):
            items[item["id"]] = item["name"]
        return items
    
    def get_tax_codes(self) -> Dict[int, str]:
        """税区分一覧を取得"""
        url = f"{self.base_url}/taxes/codes"
        params = {"company_id": self.company_id}
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        # コード -> 名称のマッピングを作成
        codes = {}
        for code in response.json().get("taxes", []):
            codes[code["code"]] = code["name_ja"]
        return codes
    
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

    def check_duplicate_transactions(self, description: str, amount: int, date: str = None) -> List[Dict]:
        """重複取引をチェック"""
        # 過去7日以内の類似取引を検索
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        url = f"{self.base_url}/deals"
        params = {
            "company_id": self.company_id,
            "start_issue_date": start_date.strftime("%Y-%m-%d"),
            "end_issue_date": end_date.strftime("%Y-%m-%d"),
            "limit": 100
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            deals = response.json().get("deals", [])
            
            # 類似取引を検索
            duplicates = []
            for deal in deals:
                # 取引の摘要や金額をチェック
                deal_description = deal.get("ref_number", "")
                for detail in deal.get("details", []):
                    # 金額と摘要の類似性をチェック
                    if (abs(detail.get("amount", 0) - abs(amount)) < 100 and
                        self._is_similar_description(description, deal_description)):
                        duplicates.append(deal)
                        break
            
            return duplicates
        except:
            return []
    
    def _is_similar_description(self, desc1: str, desc2: str) -> bool:
        """摘要の類似性をチェック"""
        if not desc1 or not desc2:
            return False
        
        desc1_lower = desc1.lower().strip()
        desc2_lower = desc2.lower().strip()
        
        # 完全一致
        if desc1_lower == desc2_lower:
            return True
        
        # 一方が他方を含む
        if desc1_lower in desc2_lower or desc2_lower in desc1_lower:
            return True
        
        # 単語レベルでの類似性チェック
        words1 = set(desc1_lower.split())
        words2 = set(desc2_lower.split())
        
        if words1 and words2:
            # Jaccard係数が0.5以上
            jaccard = len(words1 & words2) / len(words1 | words2)
            return jaccard >= 0.5
        
        return False

    def clear_related_invoice_transactions(self, partner_name: str, amount: int) -> List[Dict]:
        """関連する請求書取引を消し込み"""
        # 同じ取引先の未決済請求書を検索
        url = f"{self.base_url}/deals"
        params = {
            "company_id": self.company_id,
            "type": "income",  # 売上
            "status": "open",  # 未決済
            "limit": 50
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            deals = response.json().get("deals", [])
            
            # 該当する請求書を特定
            matching_invoices = []
            for deal in deals:
                # 取引先名と金額の一致をチェック
                if (self._get_partner_name(deal.get("partner_id")) == partner_name and
                    abs(deal.get("amount", 0) - abs(amount)) < 100):
                    matching_invoices.append(deal)
            
            # 消し込み処理を実行
            cleared_invoices = []
            for invoice in matching_invoices:
                try:
                    # 決済情報を更新
                    update_url = f"{self.base_url}/deals/{invoice['id']}"
                    update_data = {
                        "company_id": self.company_id,
                        "payments": [{
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "amount": abs(amount),
                            "from_walletable_type": "bank_account",
                            "from_walletable_id": 1  # デフォルトの口座ID
                        }]
                    }
                    
                    response = requests.put(update_url, headers=self.headers, json=update_data)
                    if response.status_code == 200:
                        cleared_invoices.append(invoice)
                except:
                    continue
            
            return cleared_invoices
        except:
            return []
    
    def _get_partner_name(self, partner_id: Optional[int]) -> str:
        """取引先IDから名称を取得"""
        if not partner_id:
            return ""
        
        url = f"{self.base_url}/partners/{partner_id}"
        params = {"company_id": self.company_id}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get("partner", {}).get("name", "")
        except:
            return ""


class IntegratedClaudeClient:
    """統合版Claude APIクライアント（学習システム統合）"""
    
    def __init__(self, api_key: str, freee_client: IntegratedFreeeClient, learning_system: Optional[TransactionLearningSystem] = None):
        self.api_key = api_key
        self.freee_client = freee_client
        self.learning_system = learning_system
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # 勘定科目と税区分の情報を取得
        try:
            self.account_items = self.freee_client.get_account_items()
            self.tax_codes = self.freee_client.get_tax_codes()
        except:
            self.account_items = {}
            self.tax_codes = {}
        
        # システムプロンプトを構築
        self._build_system_prompt()
    
    def _build_system_prompt(self):
        """システムプロンプトを構築"""
        account_items_text = self._format_account_items()
        tax_codes_text = self._format_tax_codes()
        
        self.system_prompt = f"""
あなたは日本の会計・経理の専門家です。
入出金明細から適切な勘定科目、税区分、取引先名を推定してください。

使用可能な勘定科目:
{account_items_text}

使用可能な税区分:
{tax_codes_text}

日本の会計ルール:
- 消費税10%の課税仕入は税区分21
- 軽減税率8%（食品等）は税区分24
- 非課税取引（給与等）は税区分0
- 売上は通常税区分21（標準税率）
- 交通費は原則として課税仕入10%
- 接待交際費は5000円以下なら会議費として処理可能

以下の例を参考にしてください：

例1: {{"description": "Amazon Web Services", "amount": -5500}}
→ {{"account_item_id": 604, "tax_code": 21, "partner_name": "アマゾンウェブサービスジャパン株式会社", "confidence": 0.95}}

例2: {{"description": "セブンイレブン", "amount": -324}}
→ {{"account_item_id": 831, "tax_code": 24, "partner_name": "セブンイレブン", "confidence": 0.90}}

例3: {{"description": "売上入金 ○○商事", "amount": 108000}}
→ {{"account_item_id": 101, "tax_code": 21, "partner_name": "○○商事", "confidence": 0.85}}

必ずJSON形式で回答してください。
confidence は 0.0〜1.0 の値で、推定の確信度を表します。
完全に確実な場合のみ 1.0 を設定してください。
"""
    
    def _format_account_items(self) -> str:
        """勘定科目一覧をフォーマット"""
        if not self.account_items:
            return "（取得できませんでした）"
        
        items = []
        for id, name in list(self.account_items.items())[:20]:  # 主要20件
            items.append(f"- {id}: {name}")
        return "\n".join(items)
    
    def _format_tax_codes(self) -> str:
        """税区分一覧をフォーマット"""
        if not self.tax_codes:
            return "（取得できませんでした）"
        
        codes = []
        for code, name in list(self.tax_codes.items())[:10]:  # 主要10件
            codes.append(f"- {code}: {name}")
        return "\n".join(codes)
    
    def analyze_transaction_with_context(self, txn: Dict) -> Dict:
        """コンテキストを活用した取引分析"""
        # 学習システムからコンテキストを取得
        learning_context = ""
        if self.learning_system:
            learning_context = self.learning_system.generate_learning_context(txn)
        
        # 過去の類似取引を取得
        historical_deals = self.freee_client.get_historical_deals(days=365, limit=200)
        historical_context = self._format_historical_context(txn, historical_deals)
        
        user_message = f"""
以下の取引を分析してください：
日付: {txn.get('date', '')}
金額: {txn.get('amount', 0)}円
摘要: {txn.get('description', '')}

過去の類似取引パターン:
{historical_context}

{learning_context}

これらの過去の取引パターンと学習データを参考に、最も適切な勘定科目・税区分・取引先を推定してください。
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
        
        # レスポンスを処理
        content = response.json()["content"][0]["text"]
        try:
            # JSONブロックを探して抽出
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                json_str = content.strip()
                if json_str.startswith("```") and json_str.endswith("```"):
                    json_str = json_str[3:-3].strip()
            
            result = json.loads(json_str)
            
            # 過去の取引と完全一致する場合は信頼度を上げる
            if self._has_perfect_historical_match(result, historical_deals):
                result["confidence"] = min(result.get("confidence", 0) * 1.1, 1.0)
            
            return result
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"JSON parse error: {e}")
            return {
                "account_item_id": 999,
                "tax_code": 0,
                "partner_name": "不明",
                "confidence": 0.0
            }
    
    def _format_historical_context(self, txn: Dict, historical_deals: List[Dict]) -> str:
        """過去の取引をコンテキスト用にフォーマット"""
        similar_deals = self._find_similar_deals(txn, historical_deals)
        
        if not similar_deals:
            return "（類似する過去の取引はありません）"
        
        context_lines = []
        for i, deal in enumerate(similar_deals[:5], 1):
            partner_name = self.freee_client._get_partner_name(deal.get("partner_id"))
            
            context_lines.append(f"""
例{i}:
  日付: {deal.get('issue_date', '')}
  取引先: {partner_name or '未設定'}
  金額: {deal.get('amount', 0):,}円""")
            
            # 取引詳細を追加
            for detail in deal.get("details", [])[:1]:  # 最初の明細のみ
                account_name = self.account_items.get(detail.get("account_item_id"), "不明")
                tax_name = self.tax_codes.get(detail.get("tax_code"), "不明")
                
                context_lines.append(f"""  勘定科目: {account_name} (ID: {detail.get('account_item_id')})
  税区分: {tax_name} (コード: {detail.get('tax_code')})""")
        
        return "\n".join(context_lines)
    
    def _find_similar_deals(self, txn: Dict, historical_deals: List[Dict]) -> List[Dict]:
        """類似する過去取引を検索"""
        similar_deals = []
        txn_amount = abs(txn.get("amount", 0))
        txn_description = txn.get("description", "").lower()
        
        for deal in historical_deals:
            # 金額の類似性チェック（20%以内の差）
            deal_amount = abs(deal.get("amount", 0))
            if deal_amount > 0 and txn_amount > 0:
                amount_ratio = min(deal_amount, txn_amount) / max(deal_amount, txn_amount)
                if amount_ratio < 0.8:  # 20%以上の差がある場合はスキップ
                    continue
            
            # 摘要の類似性チェック
            deal_ref = deal.get("ref_number", "").lower()
            if txn_description and deal_ref:
                if self.freee_client._is_similar_description(txn_description, deal_ref):
                    similar_deals.append(deal)
        
        # 類似度でソート（金額差の小さい順）
        similar_deals.sort(key=lambda d: abs(abs(d.get("amount", 0)) - txn_amount))
        
        return similar_deals[:10]
    
    def _has_perfect_historical_match(self, result: Dict, historical_deals: List[Dict]) -> bool:
        """完全一致する過去取引があるかチェック"""
        for deal in historical_deals[:5]:  # 上位5件のみチェック
            for detail in deal.get("details", []):
                if (result.get("account_item_id") == detail.get("account_item_id") and
                    result.get("tax_code") == detail.get("tax_code")):
                    return True
        return False


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
        duplicates_skipped = len([r for r in results if r["status"] == "duplicate_skipped"])
        
        message = {
            "text": f"仕訳処理完了: 登録 {registered}件, 要確認 {needs_confirmation}件, 重複スキップ {duplicates_skipped}件, エラー {errors}件",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "仕訳処理結果（改良版）"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*自動登録:* {registered}件"},
                        {"type": "mrkdwn", "text": f"*要確認:* {needs_confirmation}件"},
                        {"type": "mrkdwn", "text": f"*重複スキップ:* {duplicates_skipped}件"},
                        {"type": "mrkdwn", "text": f"*エラー:* {errors}件"},
                        {"type": "mrkdwn", "text": f"*処理時刻:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
                    ]
                }
            ]
        }
        
        response = requests.post(self.webhook_url, json=message)
        return response.status_code == 200


def integrated_process_wallet_txn(txn: Dict, freee_client: IntegratedFreeeClient, 
                                 claude_client: IntegratedClaudeClient, 
                                 slack_notifier: Optional[SlackNotifier],
                                 learning_system: Optional[TransactionLearningSystem]) -> Dict:
    """完全統合版の個別取引処理"""
    try:
        print(f"  処理開始: {txn.get('description', '')}")
        
        # Step 1: 重複チェック
        print(f"  重複チェック中...")
        duplicates = freee_client.check_duplicate_transactions(
            txn.get("description", ""),
            txn.get("amount", 0),
            txn.get("date", "")
        )
        
        if duplicates:
            print(f"  重複する取引が{len(duplicates)}件見つかりました - スキップします")
            return {
                "txn_id": txn["id"],
                "status": "duplicate_skipped",
                "duplicate_count": len(duplicates),
                "duplicate_deals": [d["id"] for d in duplicates]
            }
        
        # Step 2: コンテキスト活用分析
        print(f"  コンテキスト活用分析中...")
        analysis = claude_client.analyze_transaction_with_context(txn)
        print(f"  分析結果: 信頼度={analysis['confidence']:.2f}")

        # DRY_RUNモードのチェック
        if os.getenv("DRY_RUN", "false").lower() == "true":
            print(f"  [DRY_RUN] 登録をスキップします")
            return {
                "txn_id": txn["id"],
                "status": "dry_run",
                "analysis": analysis
            }

        # Step 3: 請求書消し込みのチェック（収入の場合）
        cleared_invoices = []
        if txn.get("amount", 0) > 0 and analysis.get("partner_name"):
            print(f"  関連請求書の消し込みチェック中...")
            cleared_invoices = freee_client.clear_related_invoice_transactions(
                analysis["partner_name"],
                txn.get("amount", 0)
            )
            if cleared_invoices:
                print(f"  {len(cleared_invoices)}件の請求書を消し込みました")

        # Step 4: 信頼度に基づく処理
        if analysis["confidence"] >= CONFIDENCE_THRESHOLD:
            print(f"  信頼度{CONFIDENCE_THRESHOLD*100:.0f}%以上のため自動登録を実行中...")
            result = freee_client.create_deal(
                wallet_txn_id=txn["id"],
                account_item_id=analysis["account_item_id"],
                tax_code=analysis["tax_code"],
                partner_name=analysis["partner_name"],
                amount=abs(txn.get("amount", 0)),
                txn_type="income" if txn.get("amount", 0) > 0 else "expense"
            )
            print(f"  登録完了: Deal ID={result['deal']['id']}")
            
            # Step 5: 学習システムに記録
            if learning_system:
                learning_system.record_transaction(txn, analysis, {
                    "status": "registered",
                    "deal_id": result['deal']['id']
                })
            
            return {
                "txn_id": txn["id"],
                "status": "registered",
                "deal_id": result["deal"]["id"],
                "analysis": analysis,
                "cleared_invoices": cleared_invoices
            }
        else:
            # 信頼度が低い場合はSlack通知
            print(f"  信頼度{CONFIDENCE_THRESHOLD*100:.0f}%未満のためSlack通知を送信します（信頼度: {analysis['confidence']:.2f}）")
            
            # 学習システムに記録（要確認として）
            if learning_system:
                learning_system.record_transaction(txn, analysis, {
                    "status": "needs_confirmation"
                })
            
            if slack_notifier:
                sent = slack_notifier.send_confirmation(txn, analysis)
                print(f"  Slack通知送信結果: {sent}")
            
            return {
                "txn_id": txn["id"],
                "status": "needs_confirmation",
                "analysis": analysis,
                "cleared_invoices": cleared_invoices
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
    """完全統合版メイン処理"""
    
    print("=== freee自動仕訳処理を開始します（完全統合版）===")
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
    
    # 学習システムの初期化
    learning_system = None
    if TransactionLearningSystem:
        try:
            learning_system = TransactionLearningSystem()
            print("学習システムを初期化しました")
        except Exception as e:
            print(f"学習システムの初期化に失敗: {e}")
    
    # クライアントの初期化
    freee_client = IntegratedFreeeClient(freee_access_token, freee_company_id)
    claude_client = IntegratedClaudeClient(claude_api_key, freee_client, learning_system)
    slack_notifier = SlackNotifier(slack_webhook_url) if slack_webhook_url else None
    
    try:
        # 未仕訳明細の取得
        print("\n未仕訳明細を取得中...")
        wallet_txns = freee_client.get_unmatched_wallet_txns()
        print(f"{len(wallet_txns)}件の未仕訳明細を取得しました")
        
        if not wallet_txns:
            print("処理対象の明細はありません")
            return []
        
        # 各取引の処理（完全統合版）
        print("\n取引を処理中...")
        results = []
        for i, txn in enumerate(wallet_txns, 1):
            print(f"\n[{i}/{len(wallet_txns)}] 処理中: {txn.get('description', 'No description')} ¥{txn.get('amount', 0):,}")
            result = integrated_process_wallet_txn(txn, freee_client, claude_client, slack_notifier, learning_system)
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
        duplicates_skipped = len([r for r in results if r["status"] == "duplicate_skipped"])
        dry_run = len([r for r in results if r["status"] == "dry_run"])
        
        print("\n=== 処理完了 ===")
        print(f"  自動登録: {registered}件")
        print(f"  要確認: {needs_confirmation}件")
        print(f"  重複スキップ: {duplicates_skipped}件")
        print(f"  エラー: {errors}件")
        if dry_run > 0:
            print(f"  DRY_RUN: {dry_run}件")
        
        # 請求書消し込み統計
        total_cleared = sum(len(r.get("cleared_invoices", [])) for r in results)
        if total_cleared > 0:
            print(f"  請求書消し込み: {total_cleared}件")
        
        return results
        
    except Exception as e:
        print(f"\n致命的なエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    main()