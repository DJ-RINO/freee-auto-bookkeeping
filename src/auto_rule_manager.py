"""
freee「自動で経理」の仕訳ルール管理
既存ルールの取得・分析・新規ルールの提案
"""

import os
import json
import requests
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
import re
from datetime import datetime, timedelta

class AutoRuleManager:
    """freee自動仕訳ルールの管理クラス"""
    
    def __init__(self, access_token: str, company_id: int):
        self.access_token = access_token
        self.company_id = company_id
        self.base_url = "https://api.freee.co.jp/api/1"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def get_existing_rules(self) -> List[Dict]:
        """既存の自動仕訳ルールを取得"""
        # freee APIには直接仕訳ルールを取得するエンドポイントがないため、
        # 過去の取引から推測する必要がある
        print("既存の仕訳パターンを分析中...")
        
        # 過去3ヶ月の取引を取得
        deals = self._get_recent_deals(days=90)
        
        # 取引パターンを分析
        patterns = self._analyze_transaction_patterns(deals)
        
        return patterns
    
    def _get_recent_deals(self, days: int = 90) -> List[Dict]:
        """最近の取引を取得"""
        url = f"{self.base_url}/deals"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        all_deals = []
        offset = 0
        limit = 100
        
        while True:
            params = {
                "company_id": self.company_id,
                "start_issue_date": start_date.strftime("%Y-%m-%d"),
                "end_issue_date": end_date.strftime("%Y-%m-%d"),
                "limit": limit,
                "offset": offset
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            deals = data.get("deals", [])
            if not deals:
                break
                
            all_deals.extend(deals)
            
            # 次のページがあるか確認
            if len(deals) < limit:
                break
            offset += limit
        
        return all_deals
    
    def _analyze_transaction_patterns(self, deals: List[Dict]) -> List[Dict]:
        """取引パターンを分析して仕訳ルールを推測"""
        patterns = defaultdict(lambda: {
            "count": 0,
            "account_items": Counter(),
            "tax_codes": Counter(),
            "amounts": [],
            "descriptions": []
        })
        
        for deal in deals:
            # ref_numberから取引の説明を取得
            ref_number = deal.get("ref_number", "")
            if not ref_number:
                continue
            
            # パターンのキーを生成（重要なキーワードを抽出）
            pattern_key = self._extract_pattern_key(ref_number)
            if not pattern_key:
                continue
            
            # 詳細から勘定科目と税区分を収集
            for detail in deal.get("details", []):
                account_item_id = detail.get("account_item_id")
                tax_code = detail.get("tax_code")
                amount = detail.get("amount", 0)
                
                if account_item_id:
                    patterns[pattern_key]["account_items"][account_item_id] += 1
                if tax_code is not None:
                    patterns[pattern_key]["tax_codes"][tax_code] += 1
                
                patterns[pattern_key]["count"] += 1
                patterns[pattern_key]["amounts"].append(amount)
                patterns[pattern_key]["descriptions"].append(ref_number)
        
        # パターンを仕訳ルールに変換
        rules = []
        for pattern_key, data in patterns.items():
            if data["count"] < 2:  # 2回未満のパターンは除外
                continue
            
            # 最も頻出する勘定科目と税区分を選択
            most_common_account = data["account_items"].most_common(1)
            most_common_tax = data["tax_codes"].most_common(1)
            
            if most_common_account and most_common_tax:
                rule = {
                    "pattern": pattern_key,
                    "account_item_id": most_common_account[0][0],
                    "tax_code": most_common_tax[0][0],
                    "confidence": min(data["count"] / 10.0, 1.0),  # 出現回数に基づく信頼度
                    "occurrence_count": data["count"],
                    "sample_descriptions": data["descriptions"][:3]
                }
                rules.append(rule)
        
        # 信頼度順にソート
        rules.sort(key=lambda x: (x["confidence"], x["occurrence_count"]), reverse=True)
        
        return rules
    
    def _extract_pattern_key(self, description: str) -> Optional[str]:
        """取引説明からパターンキーを抽出"""
        description_upper = description.upper()
        
        # 会社名・サービス名のパターン（優先度順）
        company_patterns = [
            # 航空会社（完全一致優先）
            r'日本航空株式会社|日本航空|JAPAN AIRLINES|JAL',
            r'ANAホールディングス|全日本空輸|全日空|ANA',
            r'ソラシドエア|SOLASEED AIR|SOLASEED',
            r'スカイマーク|SKYMARK',
            r'ピーチ・アビエーション|PEACH',
            r'ジェットスター|JETSTAR',
            
            # 交通機関
            r'JR東日本|JR EAST|東日本旅客鉄道',
            r'JR西日本|JR WEST|西日本旅客鉄道',
            r'JR東海|JR CENTRAL|東海旅客鉄道',
            r'JR九州|JR KYUSHU|九州旅客鉄道',
            r'JR北海道|JR HOKKAIDO|北海道旅客鉄道',
            r'JR四国|JR SHIKOKU|四国旅客鉄道',
            r'東京メトロ|TOKYO METRO|東京地下鉄',
            r'都営地下鉄|都営|TOEI',
            
            # AI・開発ツール
            r'ANTHROPIC PBC|ANTHROPIC|アンソロピック',
            r'CURSOR INC|CURSOR AI|CURSOR|カーソル',
            r'OPENAI|オープンAI|CHATGPT',
            r'GITHUB INC|GITHUB|ギットハブ',
            r'GITLAB|ギットラボ',
            
            # コミュニケーションツール
            r'SLACK TECHNOLOGIES|SLACK|スラック',
            r'ZOOM VIDEO|ZOOM|ズーム',
            r'MICROSOFT TEAMS|TEAMS|チームズ',
            r'DISCORD|ディスコード',
            
            # クラウドサービス
            r'AMAZON WEB SERVICES|AWS|アマゾンウェブサービス',
            r'GOOGLE CLOUD|GCP|グーグルクラウド',
            r'MICROSOFT AZURE|AZURE|アジュール',
            
            # EC・小売
            r'AMAZON.CO.JP|AMAZON|アマゾン',
            r'楽天市場|楽天|RAKUTEN',
            r'ヤフーショッピング|YAHOO',
            
            # エンタメ・サブスク
            r'ABEMATV|ABEMA|アベマ',
            r'NETFLIX|ネットフリックス',
            r'SPOTIFY|スポティファイ',
            r'APPLE MUSIC|アップルミュージック',
            r'YOUTUBE PREMIUM|ユーチューブ',
            
            # 支払い・金融
            r'PAYPAY|ペイペイ',
            r'LINE PAY|ラインペイ',
            r'楽天ペイ|RAKUTEN PAY',
            r'SQUARE|スクエア',
            r'STRIPE|ストライプ',
            
            # 飲食
            r'スターバックス|STARBUCKS',
            r'ドトール|DOUTOR',
            r'マクドナルド|MCDONALD',
            r'吉野家|YOSHINOYA',
            r'すき家|SUKIYA',
            r'セブンイレブン|7-ELEVEN',
            r'ローソン|LAWSON',
            r'ファミリーマート|FAMILYMART',
        ]
        
        # パターンマッチング
        for pattern in company_patterns:
            if re.search(pattern, description_upper):
                # マッチした部分を正規化して返す
                match = re.search(pattern, description_upper)
                return match.group(0).split('|')[0]  # 最初のバリエーションを使用
        
        # 振込パターン
        if '振込' in description or '振り込み' in description:
            # 振込元の名前を抽出
            name_match = re.search(r'振込\s*(\S+)', description)
            if name_match:
                return f"振込_{name_match.group(1)}"
        
        # カード決済パターン
        if 'Vデビット' in description or 'VISA' in description:
            # 加盟店名を抽出
            merchant_match = re.search(r'(?:Vデビット|VISA)\s*(\S+)', description)
            if merchant_match:
                return merchant_match.group(1)
        
        return None
    
    def suggest_new_rules(self, unmatched_transactions: List[Dict]) -> List[Dict]:
        """未処理取引から新しい仕訳ルールを提案"""
        suggestions = []
        
        # 取引をグループ化
        transaction_groups = defaultdict(list)
        for txn in unmatched_transactions:
            pattern_key = self._extract_pattern_key(txn.get("description", ""))
            if pattern_key:
                transaction_groups[pattern_key].append(txn)
        
        # グループごとに分析
        for pattern_key, transactions in transaction_groups.items():
            if len(transactions) < 2:  # 2件以上ある場合のみ提案
                continue
            
            # 金額の傾向を分析
            amounts = [abs(t.get("amount", 0)) for t in transactions]
            avg_amount = sum(amounts) / len(amounts)
            
            # 収入/支出の判定
            is_income = all(t.get("amount", 0) > 0 for t in transactions)
            is_expense = all(t.get("amount", 0) < 0 for t in transactions)
            
            # 推奨される勘定科目を決定
            suggested_account, suggested_tax = self._suggest_account_and_tax(
                pattern_key, avg_amount, is_income, is_expense
            )
            
            suggestion = {
                "pattern": pattern_key,
                "suggested_account_item_id": suggested_account,
                "suggested_tax_code": suggested_tax,
                "transaction_count": len(transactions),
                "average_amount": avg_amount,
                "type": "income" if is_income else "expense",
                "sample_transactions": transactions[:3]
            }
            suggestions.append(suggestion)
        
        return suggestions
    
    def _suggest_account_and_tax(self, pattern: str, avg_amount: float, 
                                 is_income: bool, is_expense: bool) -> Tuple[int, int]:
        """パターンに基づいて勘定科目と税区分を提案"""
        
        # 収入の場合
        if is_income:
            if avg_amount > 100000:  # 10万円以上
                return 101, 21  # 売上高、課税売上10%
            else:
                return 135, 21  # 雑収入、課税売上10%
        
        # 支出の場合 - パターンに基づく判定
        pattern_upper = pattern.upper()
        
        # 交通費
        if any(keyword in pattern_upper for keyword in ['AIR', '航空', 'JR', '鉄道', 'タクシー']):
            return 607, 21  # 旅費交通費、課税仕入10%
        
        # 通信費・サブスクリプション
        if any(keyword in pattern_upper for keyword in ['ANTHROPIC', 'OPENAI', 'CURSOR', 'GITHUB', 
                                                        'SLACK', 'ZOOM', 'CLOUD', 'AWS', 'サーバ']):
            return 604, 21  # 通信費、課税仕入10%
        
        # 広告宣伝費
        if any(keyword in pattern_upper for keyword in ['GOOGLE', 'FACEBOOK', 'TWITTER', '広告']):
            return 811, 21  # 広告宣伝費、課税仕入10%
        
        # 会議費（飲食）
        if any(keyword in pattern_upper for keyword in ['レストラン', 'カフェ', '飲食', '食']):
            if avg_amount <= 5000:  # 5000円以下
                return 815, 24  # 会議費、軽減税率8%
            else:
                return 810, 24  # 接待交際費、軽減税率8%
        
        # 消耗品費
        if any(keyword in pattern_upper for keyword in ['AMAZON', 'アマゾン', '文具', '事務']):
            return 827, 21  # 消耗品費、課税仕入10%
        
        # その他は雑費
        return 831, 21  # 雑費、課税仕入10%
    
    def create_rule_csv(self, rules: List[Dict], filename: str = "freee_auto_rules.csv"):
        """仕訳ルールをCSV形式で出力（freeeインポート用）"""
        import csv
        
        # 勘定科目マスタを取得
        account_items = self._get_account_items_dict()
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['取引先名', '勘定科目', '税区分', '摘要パターン', '推奨度', 'サンプル']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for rule in rules:
                writer.writerow({
                    '取引先名': rule.get('pattern', ''),
                    '勘定科目': account_items.get(rule.get('suggested_account_item_id', 0), '不明'),
                    '税区分': self._get_tax_name(rule.get('suggested_tax_code', 0)),
                    '摘要パターン': rule.get('pattern', ''),
                    '推奨度': f"{rule.get('confidence', 0):.0%}" if 'confidence' in rule else f"{rule.get('transaction_count', 0)}件",
                    'サンプル': rule.get('sample_descriptions', [''])[0] if 'sample_descriptions' in rule else ''
                })
        
        print(f"\n仕訳ルールを {filename} に出力しました")
        print("freeeの「自動で経理」設定画面でインポートしてください")
    
    def _get_account_items_dict(self) -> Dict[int, str]:
        """勘定科目IDと名前のマッピングを取得"""
        url = f"{self.base_url}/account_items"
        params = {"company_id": self.company_id}
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        items = response.json().get("account_items", [])
        return {item["id"]: item["name"] for item in items}
    
    def _get_tax_name(self, tax_code: int) -> str:
        """税区分コードから名前を取得"""
        tax_names = {
            0: "非課税",
            21: "課税仕入 10%",
            24: "課税仕入 8%（軽減）",
            10: "課税売上 10%",
            11: "課税売上 8%（軽減）"
        }
        return tax_names.get(tax_code, f"コード: {tax_code}")


def analyze_and_update_rules():
    """既存ルールの分析と新規ルール提案のメイン処理"""
    from enhanced_main import FreeeClient, EnhancedClaudeClient
    
    # 環境変数から設定を読み込み
    access_token = os.getenv("FREEE_ACCESS_TOKEN")
    company_id = int(os.getenv("FREEE_COMPANY_ID", "0"))
    
    if not access_token or not company_id:
        print("エラー: FREEE_ACCESS_TOKEN と FREEE_COMPANY_ID を設定してください")
        return
    
    # マネージャーを初期化
    rule_manager = AutoRuleManager(access_token, company_id)
    freee_client = FreeeClient(access_token, company_id)
    
    print("=== freee「自動で経理」ルール分析 ===")
    
    # 1. 既存のパターンを分析
    print("\n1. 既存の取引パターンを分析中...")
    existing_patterns = rule_manager.get_existing_rules()
    print(f"  {len(existing_patterns)}個のパターンを発見しました")
    
    # 上位パターンを表示
    print("\n  頻出パターン（上位10件）:")
    for i, pattern in enumerate(existing_patterns[:10], 1):
        print(f"  {i}. {pattern['pattern']} - {pattern['occurrence_count']}回")
    
    # 2. 未処理取引を取得
    print("\n2. 未処理取引を取得中...")
    unmatched_txns = freee_client.get_unmatched_wallet_txns(limit=100)
    print(f"  {len(unmatched_txns)}件の未処理取引があります")
    
    # 3. 新しいルールを提案
    print("\n3. 新しい仕訳ルールを提案中...")
    new_rules = rule_manager.suggest_new_rules(unmatched_txns)
    print(f"  {len(new_rules)}個の新しいルールを提案します")
    
    # 提案内容を表示
    if new_rules:
        print("\n  提案するルール:")
        for i, rule in enumerate(new_rules[:10], 1):
            account_name = rule_manager._get_account_items_dict().get(
                rule['suggested_account_item_id'], '不明'
            )
            print(f"  {i}. {rule['pattern']} → {account_name} ({rule['transaction_count']}件)")
    
    # 4. CSVファイルに出力
    if new_rules:
        print("\n4. 仕訳ルールをCSVファイルに出力中...")
        rule_manager.create_rule_csv(new_rules)
    
    return existing_patterns, new_rules


if __name__ == "__main__":
    analyze_and_update_rules()