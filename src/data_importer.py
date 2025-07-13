import csv
import json
from pathlib import Path
from typing import Dict, List, Optional
import codecs

class FreeeDataImporter:
    """freeeの過去データをインポートするクラス"""
    
    def __init__(self, csv_dir: str):
        self.csv_dir = Path(csv_dir)
    
    def import_account_items(self) -> Dict[int, Dict]:
        """勘定科目マスタをインポート"""
        file_path = self.csv_dir / "freee_account_item_20250712.csv"
        account_items = {}
        
        with codecs.open(file_path, 'r', encoding='shift_jis') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # IDを抽出（ショートカット2列に数値がある場合）
                if row['ショートカット2'] and row['ショートカット2'].isdigit():
                    account_id = int(row['ショートカット2'])
                    account_items[account_id] = {
                        'name': row['勘定科目'],
                        'display_name': row['表示名（決算書）'],
                        'category': row['大分類'],
                        'tax_type': row['税区分'],
                        'shortcut': row['ショートカット1']
                    }
        
        return account_items
    
    def import_partners(self) -> Dict[str, Dict]:
        """取引先マスタをインポート"""
        file_path = self.csv_dir / "freee_partners_20250712.csv"
        partners = {}
        
        try:
            with codecs.open(file_path, 'r', encoding='shift_jis') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    partner_name = row.get('取引先名', '')
                    if partner_name:
                        partners[partner_name] = {
                            'code': row.get('取引先コード', ''),
                            'payment_term': row.get('支払期日', ''),
                            'address': row.get('住所', '')
                        }
        except FileNotFoundError:
            print(f"取引先マスタファイルが見つかりません: {file_path}")
        
        return partners
    
    def import_deals(self) -> List[Dict]:
        """過去の取引データをインポート"""
        file_path = self.csv_dir / "deals.csv"
        deals = []
        
        with codecs.open(file_path, 'r', encoding='shift_jis') as f:
            reader = csv.DictReader(f)
            current_deal = None
            
            for row in reader:
                if row['収支区分']:  # 新しい取引の開始
                    if current_deal:
                        deals.append(current_deal)
                    
                    current_deal = {
                        'type': row['収支区分'],
                        'ref_number': row['管理番号'],
                        'issue_date': row['発生日'],
                        'partner_name': row['取引先'],
                        'details': [],
                        'settlement': {
                            'date': row['決済期日'],
                            'account': row['決済口座'],
                            'amount': self._parse_amount(row['決済金額'])
                        }
                    }
                
                # 明細行を追加
                if current_deal and row['勘定科目']:
                    detail = {
                        'account_item': row['勘定科目'],
                        'tax_type': row['税区分'],
                        'amount': self._parse_amount(row['金額']),
                        'tax_amount': self._parse_amount(row['税額']),
                        'description': row['備考']
                    }
                    current_deal['details'].append(detail)
            
            # 最後の取引を追加
            if current_deal:
                deals.append(current_deal)
        
        return deals
    
    def import_user_matchers(self) -> List[Dict]:
        """自動仕訳ルールをインポート"""
        matchers = []
        
        # 手動設定のマッチャー
        manual_file = self.csv_dir / "freee_user_matchers_20250712.csv"
        if manual_file.exists():
            matchers.extend(self._import_matchers_file(manual_file))
        
        # 自動生成のマッチャー
        auto_file = self.csv_dir / "freee_user_matchers_auto_generated.csv"
        if auto_file.exists():
            matchers.extend(self._import_matchers_file(auto_file))
        
        return matchers
    
    def _import_matchers_file(self, file_path: Path) -> List[Dict]:
        """マッチャーファイルをインポート"""
        matchers = []
        
        try:
            with codecs.open(file_path, 'r', encoding='shift_jis') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    matcher = {
                        'pattern': row.get('パターン', ''),
                        'account_item': row.get('勘定科目', ''),
                        'tax_code': row.get('税区分', ''),
                        'partner_name': row.get('取引先名', ''),
                        'priority': int(row.get('優先度', '0'))
                    }
                    if matcher['pattern']:
                        matchers.append(matcher)
        except Exception as e:
            print(f"マッチャーファイルの読み込みエラー: {e}")
        
        return matchers
    
    def _parse_amount(self, amount_str: str) -> int:
        """金額文字列を数値に変換"""
        if not amount_str:
            return 0
        # カンマを除去して数値に変換
        return int(amount_str.replace(',', '').replace('円', ''))
    
    def create_learning_context(self) -> Dict:
        """学習用コンテキストを生成"""
        context = {
            'account_items': self.import_account_items(),
            'partners': self.import_partners(),
            'deals': self.import_deals()[-100:],  # 直近100件
            'matchers': self.import_user_matchers()
        }
        
        # 統計情報を追加
        context['statistics'] = self._calculate_statistics(context['deals'])
        
        return context
    
    def _calculate_statistics(self, deals: List[Dict]) -> Dict:
        """取引の統計情報を計算"""
        from collections import defaultdict
        
        account_counts = defaultdict(int)
        partner_counts = defaultdict(int)
        tax_counts = defaultdict(int)
        
        for deal in deals:
            if deal['partner_name']:
                partner_counts[deal['partner_name']] += 1
            
            for detail in deal['details']:
                account_counts[detail['account_item']] += 1
                tax_counts[detail['tax_type']] += 1
        
        return {
            'top_accounts': sorted(account_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            'top_partners': sorted(partner_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            'top_tax_types': sorted(tax_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        }
    
    def export_for_claude(self, output_file: str = "claude_context.json"):
        """Claude用のコンテキストをエクスポート"""
        context = self.create_learning_context()
        
        # Claude用に整形
        claude_context = {
            "company_profile": {
                "frequent_accounts": context['statistics']['top_accounts'],
                "frequent_partners": context['statistics']['top_partners'],
                "tax_patterns": context['statistics']['top_tax_types']
            },
            "account_mappings": {
                item['name']: {
                    'id': account_id,
                    'category': item['category'],
                    'tax_type': item['tax_type']
                }
                for account_id, item in context['account_items'].items()
            },
            "recent_transactions": [
                {
                    'partner': deal['partner_name'],
                    'details': [
                        {
                            'account': detail['account_item'],
                            'tax': detail['tax_type'],
                            'amount': detail['amount']
                        }
                        for detail in deal['details']
                    ]
                }
                for deal in context['deals'][-20:]  # 直近20件
            ],
            "auto_rules": context['matchers']
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(claude_context, f, ensure_ascii=False, indent=2)
        
        print(f"Claudeコンテキストを {output_file} に保存しました")
        return claude_context


if __name__ == "__main__":
    # データインポートの実行例
    csv_dir = "/Users/matsufujiwataru/Library/Mobile Documents/iCloud~md~obsidian/Documents/2nd brain/99Attachment/CSV"
    importer = FreeeDataImporter(csv_dir)
    
    # データの確認
    print("=== 勘定科目マスタ ===")
    account_items = importer.import_account_items()
    print(f"登録数: {len(account_items)}件")
    for aid, item in list(account_items.items())[:5]:
        print(f"  {aid}: {item['name']} ({item['category']})")
    
    print("\n=== 過去の取引 ===")
    deals = importer.import_deals()
    print(f"取引数: {len(deals)}件")
    if deals:
        latest_deal = deals[-1]
        print(f"最新取引: {latest_deal['issue_date']} {latest_deal['partner_name']}")
    
    # Claude用コンテキストの生成
    print("\n=== Claudeコンテキスト生成 ===")
    claude_context = importer.export_for_claude("claude_context.json")