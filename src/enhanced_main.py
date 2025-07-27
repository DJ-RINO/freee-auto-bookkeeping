import os
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv
from collections import defaultdict
import re

load_dotenv()

CONFIDENCE_THRESHOLD = 1.0  # 100%の確信度のみ自動登録

class FreeeClient:
    """freee API クライアント（過去の取引履歴取得機能付き）"""
    
    def __init__(self, access_token: str, company_id: int):
        self.access_token = access_token
        self.company_id = company_id
        self.base_url = "https://api.freee.co.jp/api/1"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
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
    
    def analyze_historical_patterns(self, description: str, amount: int) -> List[Dict]:
        """類似する過去の取引パターンを分析"""
        historical_deals = self.get_historical_deals(days=365, limit=1000)
        
        similar_deals = []
        description_upper = description.upper()
        
        # 特定のキーワードを抽出（CURSOR、ANTHROPIC等）
        keywords = self._extract_keywords(description_upper)
        
        for deal in historical_deals:
            # 取引詳細を確認
            if deal.get("details"):
                for detail in deal["details"]:
                    detail_amount = detail.get("amount", 0)
                    partner_name = self._get_partner_name(deal.get("partner_id"))
                    ref_number = deal.get("ref_number", "").upper()
                    
                    # マッチング条件：
                    # 1. 金額が完全一致
                    # 2. 金額が近い（20%以内）かつキーワードが含まれる
                    # 3. 取引先名に含まれるキーワードがある
                    
                    is_amount_match = abs(detail_amount) == abs(amount)
                    is_amount_similar = abs(detail_amount - abs(amount)) / max(abs(amount), 1) < 0.2
                    is_keyword_match = any(kw in partner_name.upper() for kw in keywords) if partner_name else False
                    is_ref_match = any(kw in ref_number for kw in keywords) if ref_number else False
                    
                    score = 0
                    if is_amount_match:
                        score += 50
                    elif is_amount_similar:
                        score += 20
                    
                    if is_keyword_match or is_ref_match:
                        score += 30
                    
                    if score > 0:
                        similar_deals.append({
                            "date": deal.get("issue_date"),
                            "amount": detail_amount,
                            "description": ref_number,
                            "account_item_id": detail.get("account_item_id"),
                            "tax_code": detail.get("tax_code"),
                            "partner_name": partner_name,
                            "score": score
                        })
        
        # スコアの高い順にソート
        similar_deals.sort(key=lambda x: x["score"], reverse=True)
        return similar_deals[:10]  # 上位10件を返す
    
    def _extract_keywords(self, description: str) -> List[str]:
        """説明文からキーワードを抽出"""
        # 一般的な省略形と正式名のマッピング
        keyword_mapping = {
            "ANTHROPIC": ["ANTHROPIC", "アンソロピック", "CLAUDE"],
            "CURSOR": ["CURSOR", "カーソル"],
            "SLACK": ["SLACK", "スラック"],
            "ZOOM": ["ZOOM", "ズーム"],
            "JAPAN AIRLINES": ["JAL", "日本航空", "JAPAN AIRLINES"],
            "SOLASEED": ["SOLASEED", "ソラシド"],
            "ABEMATV": ["ABEMA", "アベマ"],
        }
        
        keywords = []
        for key, values in keyword_mapping.items():
            if any(v in description for v in values):
                keywords.extend(values)
        
        # 説明文中の英数字の単語も抽出
        import re
        words = re.findall(r'[A-Z][A-Z0-9]+', description)
        keywords.extend(words)
        
        return list(set(keywords))  # 重複を除去
    
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
    
    # 既存のメソッドは省略（前述のmain.pyと同じ）


class EnhancedClaudeClient(ClaudeClient):
    """過去の取引履歴を活用するClaude APIクライアント"""
    
    def __init__(self, api_key: str, freee_client: FreeeClient):
        super().__init__(api_key)
        self.freee_client = freee_client
        self._load_accounting_rules()
    
    def _load_accounting_rules(self):
        """日本の会計ルールをロード"""
        # 勘定科目と税区分の情報を取得
        try:
            self.account_items = self.freee_client.get_account_items()
            self.tax_codes = self.freee_client.get_tax_codes()
        except:
            self.account_items = {}
            self.tax_codes = {}
        
        # システムプロンプトを更新
        self.system_prompt = f"""
あなたは日本の会計・経理の専門家です。
入出金明細から適切な勘定科目、税区分、取引先名を推定してください。

使用可能な勘定科目:
{self._format_account_items()}

使用可能な税区分:
{self._format_tax_codes()}

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

必ずJSON形式のみで回答してください。説明や理由は含めないでください。
以下の形式で出力してください：
{"account_item_id": 数値, "tax_code": 数値, "partner_name": "文字列", "confidence": 0.0〜1.0}

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
    
    def analyze_transaction_with_history(self, txn: Dict) -> Dict:
        """過去の取引履歴を参考に取引を分析"""
        
        # 類似する過去の取引を取得
        similar_deals = self.freee_client.analyze_historical_patterns(
            txn.get("description", ""),
            txn.get("amount", 0)
        )
        
        # 過去の取引パターンをコンテキストに含める
        historical_context = self._format_historical_context(similar_deals)
        
        user_message = f"""
以下の取引を分析してください：
日付: {txn.get('date', '')}
金額: {txn.get('amount', 0)}円
摘要: {txn.get('description', '')}

過去の類似取引パターン:
{historical_context}

これらの過去の取引パターンを参考に、最も適切な勘定科目・税区分・取引先を推定してください。
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
            if similar_deals and self._is_perfect_match(result, similar_deals[0]):
                result["confidence"] = min(result.get("confidence", 0) * 1.2, 1.0)
            
            return result
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"JSON parse error: {e}")
            return {
                "account_item_id": 999,
                "tax_code": 0,
                "partner_name": "不明",
                "confidence": 0.0
            }
    
    def _format_historical_context(self, similar_deals: List[Dict]) -> str:
        """過去の取引をコンテキスト用にフォーマット"""
        if not similar_deals:
            return "（類似する過去の取引はありません）"
        
        context_lines = []
        for i, deal in enumerate(similar_deals[:5], 1):
            account_name = self.account_items.get(deal["account_item_id"], "不明")
            tax_name = self.tax_codes.get(deal["tax_code"], "不明")
            
            context_lines.append(f"""
例{i}:
  日付: {deal['date']}
  金額: {deal['amount']:,}円
  勘定科目: {account_name} (ID: {deal['account_item_id']})
  税区分: {tax_name} (コード: {deal['tax_code']})
  取引先: {deal['partner_name'] or '未設定'}""")
        
        return "\n".join(context_lines)
    
    def _is_perfect_match(self, result: Dict, historical: Dict) -> bool:
        """推定結果と過去の取引が完全一致するかチェック"""
        return (
            result.get("account_item_id") == historical.get("account_item_id") and
            result.get("tax_code") == historical.get("tax_code")
        )


# メイン処理の更新
def enhanced_main():
    """過去の取引履歴を活用したメイン処理"""
    
    print("=== freee自動仕訳処理を開始します（履歴学習版）===")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 環境変数の読み込み
    freee_access_token = os.getenv("FREEE_ACCESS_TOKEN")
    freee_company_id = int(os.getenv("FREEE_COMPANY_ID", "0"))
    claude_api_key = os.getenv("FREEE_CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    
    # クライアントの初期化
    freee_client = FreeeClient(freee_access_token, freee_company_id)
    claude_client = EnhancedClaudeClient(claude_api_key, freee_client)
    slack_notifier = SlackNotifier(slack_webhook_url) if slack_webhook_url else None
    
    # 過去の取引パターンを分析
    print("\n過去の取引パターンを学習中...")
    historical_summary = analyze_company_patterns(freee_client)
    print(f"  - 過去1年間の取引: {historical_summary['total_deals']}件")
    print(f"  - 頻出取引先: {', '.join(historical_summary['top_partners'][:5])}")
    print(f"  - 頻出勘定科目: {', '.join(historical_summary['top_accounts'][:5])}")
    
    # 以下、通常の処理...


def analyze_company_patterns(freee_client: FreeeClient) -> Dict:
    """会社固有の取引パターンを分析"""
    deals = freee_client.get_historical_deals(days=365, limit=1000)
    
    partner_counts = defaultdict(int)
    account_counts = defaultdict(int)
    
    for deal in deals:
        # 取引先の集計
        if deal.get("partner_id"):
            partner_name = freee_client._get_partner_name(deal["partner_id"])
            if partner_name:
                partner_counts[partner_name] += 1
        
        # 勘定科目の集計
        for detail in deal.get("details", []):
            account_id = detail.get("account_item_id")
            if account_id:
                account_counts[account_id] += 1
    
    # 頻出順にソート
    top_partners = sorted(partner_counts.keys(), key=lambda x: partner_counts[x], reverse=True)
    top_accounts = sorted(account_counts.keys(), key=lambda x: account_counts[x], reverse=True)
    
    # 勘定科目名を取得
    account_items = freee_client.get_account_items()
    top_account_names = [account_items.get(aid, f"ID:{aid}") for aid in top_accounts]
    
    return {
        "total_deals": len(deals),
        "top_partners": top_partners,
        "top_accounts": top_account_names,
        "partner_counts": dict(partner_counts),
        "account_counts": dict(account_counts)
    }


if __name__ == "__main__":
    enhanced_main()