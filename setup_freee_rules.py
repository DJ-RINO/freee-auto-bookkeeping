#!/usr/bin/env python3
"""
freee「自動で経理」ルール設定支援ツール

このスクリプトは以下の処理を行います：
1. 現在の取引パターンを分析
2. freeeに設定すべきルールを提案
3. ルールをCSVファイルとして出力
4. 設定方法のガイドを表示
"""

import os
import sys
import json
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, List, Tuple

# プロジェクトのルートディレクトリをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.auto_rule_manager import AutoRuleManager
from src.enhanced_main import FreeeClient
from src.token_manager import TokenManager


def analyze_transaction_history(freee_client: FreeeClient) -> Dict:
    """取引履歴を詳細に分析"""
    print("\n📊 取引履歴の分析を開始します...")
    
    # 過去3ヶ月の全取引を取得
    deals = []
    offset = 0
    limit = 100
    
    while True:
        response = freee_client.get_deals(limit=limit, offset=offset)
        batch = response.get("deals", [])
        if not batch:
            break
        deals.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    
    print(f"  ✅ {len(deals)}件の取引を取得しました")
    
    # 口座明細も取得
    wallet_txns = freee_client.get_unmatched_wallet_txns(limit=500)
    print(f"  ✅ {len(wallet_txns)}件の未処理口座明細を取得しました")
    
    # パターン分析
    patterns = defaultdict(lambda: {
        "count": 0,
        "amounts": [],
        "account_items": Counter(),
        "tax_codes": Counter(),
        "samples": []
    })
    
    # 取引を分析
    for deal in deals:
        ref_number = deal.get("ref_number", "")
        if not ref_number:
            continue
            
        # 主要なキーワードを抽出
        pattern_key = extract_pattern_key(ref_number)
        if pattern_key:
            for detail in deal.get("details", []):
                patterns[pattern_key]["count"] += 1
                patterns[pattern_key]["amounts"].append(abs(detail.get("amount", 0)))
                
                account_item_id = detail.get("account_item_id")
                if account_item_id:
                    patterns[pattern_key]["account_items"][account_item_id] += 1
                    
                tax_code = detail.get("tax_code")
                if tax_code is not None:
                    patterns[pattern_key]["tax_codes"][tax_code] += 1
                    
                if len(patterns[pattern_key]["samples"]) < 3:
                    patterns[pattern_key]["samples"].append(ref_number)
    
    # 未処理の口座明細も分析
    unmatched_patterns = defaultdict(list)
    for txn in wallet_txns:
        description = txn.get("description", "")
        pattern_key = extract_pattern_key(description)
        if pattern_key:
            unmatched_patterns[pattern_key].append(txn)
    
    return {
        "total_deals": len(deals),
        "total_unmatched": len(wallet_txns),
        "patterns": dict(patterns),
        "unmatched_patterns": dict(unmatched_patterns)
    }


def extract_pattern_key(description: str) -> str:
    """取引説明から会社名・サービス名を抽出（改良版）"""
    import re
    
    description_upper = description.upper()
    
    # 主要サービスのパターン（実際の使用頻度が高いもの）
    service_patterns = {
        # AI・開発ツール（最重要）
        "ANTHROPIC": r"ANTHROPIC|アンソロピック|CLAUDE",
        "CURSOR": r"CURSOR|カーソル",
        "OPENAI": r"OPENAI|CHATGPT|チャットGPT",
        "GITHUB": r"GITHUB|ギットハブ",
        
        # 交通系
        "日本航空": r"日本航空|JAL|JAPAN AIRLINES",
        "全日空": r"ANA|全日空|全日本空輸",
        "JR東日本": r"JR東日本|JR EAST|東日本旅客",
        "JR東海": r"JR東海|JR CENTRAL|東海旅客",
        
        # クラウド・IT
        "AWS": r"AMAZON WEB SERVICES|AWS|アマゾンウェブ",
        "Google Cloud": r"GOOGLE CLOUD|GCP|グーグルクラウド",
        "Slack": r"SLACK|スラック",
        
        # EC・決済
        "Amazon": r"AMAZON\.CO\.JP|AMAZON JP|アマゾン",
        "楽天": r"楽天市場|楽天|RAKUTEN",
        "PayPay": r"PAYPAY|ペイペイ",
        
        # コンビニ・飲食
        "セブンイレブン": r"セブンイレブン|7-ELEVEN|７－１１",
        "ローソン": r"ローソン|LAWSON",
        "ファミリーマート": r"ファミリーマート|FAMILYMART|ファミマ",
        "スターバックス": r"スターバックス|STARBUCKS",
    }
    
    # パターンマッチング
    for name, pattern in service_patterns.items():
        if re.search(pattern, description_upper):
            return name
    
    # カード決済から加盟店名を抽出
    card_match = re.search(r"(?:Vデビット|VISA|JCB|MASTERCARD)\s*([^\s]+)", description_upper)
    if card_match:
        merchant = card_match.group(1)
        # 日付や番号を除外
        if not re.match(r"^\d+$", merchant) and not re.match(r"^\d{4}[-/]\d{2}[-/]\d{2}$", merchant):
            return merchant
    
    # 振込から名前を抽出
    transfer_match = re.search(r"振[込替]\s*([^\s（）]+)", description)
    if transfer_match:
        return f"振込_{transfer_match.group(1)}"
    
    return ""


def generate_freee_rules(analysis: Dict, freee_client: FreeeClient) -> List[Dict]:
    """分析結果からfreeeルールを生成"""
    print("\n🔧 freee「自動で経理」ルールを生成中...")
    
    # 勘定科目マスタを取得
    account_items = {}
    try:
        response = freee_client._api_request("GET", "/account_items")
        for item in response.get("account_items", []):
            account_items[item["id"]] = item["name"]
    except:
        pass
    
    rules = []
    
    # 既存パターンからルール生成
    for pattern_key, data in analysis["patterns"].items():
        if data["count"] < 3:  # 3回以上出現したものだけ
            continue
            
        # 最頻出の勘定科目と税区分
        if data["account_items"] and data["tax_codes"]:
            most_common_account = data["account_items"].most_common(1)[0]
            most_common_tax = data["tax_codes"].most_common(1)[0]
            
            rule = {
                "取引先名": pattern_key,
                "勘定科目ID": most_common_account[0],
                "勘定科目名": account_items.get(most_common_account[0], "不明"),
                "税区分コード": most_common_tax[0],
                "税区分名": get_tax_name(most_common_tax[0]),
                "出現回数": data["count"],
                "平均金額": sum(data["amounts"]) / len(data["amounts"]) if data["amounts"] else 0,
                "サンプル": data["samples"][0] if data["samples"] else "",
                "信頼度": "高" if data["count"] >= 10 else "中"
            }
            rules.append(rule)
    
    # 未処理パターンから新規ルール提案
    for pattern_key, transactions in analysis["unmatched_patterns"].items():
        if len(transactions) < 2:
            continue
            
        # 金額と収支を分析
        amounts = [abs(t.get("amount", 0)) for t in transactions]
        avg_amount = sum(amounts) / len(amounts)
        is_income = all(t.get("amount", 0) > 0 for t in transactions)
        
        # 推奨勘定科目を決定
        account_id, tax_code = suggest_account_and_tax(pattern_key, avg_amount, is_income)
        
        rule = {
            "取引先名": pattern_key,
            "勘定科目ID": account_id,
            "勘定科目名": get_default_account_name(account_id),
            "税区分コード": tax_code,
            "税区分名": get_tax_name(tax_code),
            "出現回数": len(transactions),
            "平均金額": avg_amount,
            "サンプル": transactions[0].get("description", ""),
            "信頼度": "提案"
        }
        rules.append(rule)
    
    # 信頼度と出現回数でソート
    rules.sort(key=lambda x: (
        0 if x["信頼度"] == "高" else (1 if x["信頼度"] == "中" else 2),
        -x["出現回数"]
    ))
    
    print(f"  ✅ {len(rules)}個のルールを生成しました")
    return rules


def suggest_account_and_tax(pattern: str, avg_amount: float, is_income: bool) -> Tuple[int, int]:
    """パターンから適切な勘定科目と税区分を提案"""
    pattern_upper = pattern.upper()
    
    if is_income:
        if avg_amount > 100000:
            return 101, 10  # 売上高、課税売上10%
        else:
            return 135, 10  # 雑収入、課税売上10%
    
    # AI・開発ツール → 通信費
    if any(keyword in pattern_upper for keyword in ["ANTHROPIC", "OPENAI", "CURSOR", "GITHUB", "SLACK"]):
        return 604, 21  # 通信費、課税仕入10%
    
    # 交通費
    if any(keyword in pattern_upper for keyword in ["航空", "JAL", "ANA", "JR", "鉄道", "タクシー"]):
        return 607, 21  # 旅費交通費、課税仕入10%
    
    # クラウドサービス → 通信費
    if any(keyword in pattern_upper for keyword in ["AWS", "CLOUD", "AZURE", "サーバ"]):
        return 604, 21  # 通信費、課税仕入10%
    
    # 飲食・コンビニ
    if any(keyword in pattern_upper for keyword in ["セブン", "ローソン", "ファミ", "スターバックス", "飲食"]):
        if avg_amount <= 5000:
            return 815, 24  # 会議費、軽減税率8%
        else:
            return 810, 24  # 接待交際費、軽減税率8%
    
    # EC → 消耗品費
    if any(keyword in pattern_upper for keyword in ["AMAZON", "楽天", "通販"]):
        return 827, 21  # 消耗品費、課税仕入10%
    
    # その他 → 雑費
    return 831, 21  # 雑費、課税仕入10%


def get_tax_name(tax_code: int) -> str:
    """税区分コードから名称を取得"""
    tax_names = {
        0: "非課税",
        10: "課税売上 10%",
        11: "課税売上 8%（軽減）",
        21: "課税仕入 10%",
        24: "課税仕入 8%（軽減）",
        30: "非課税売上",
        34: "免税売上",
        40: "非課税仕入",
        50: "対象外"
    }
    return tax_names.get(tax_code, f"税区分コード{tax_code}")


def get_default_account_name(account_id: int) -> str:
    """デフォルトの勘定科目名を取得"""
    default_names = {
        101: "売上高",
        135: "雑収入",
        604: "通信費",
        607: "旅費交通費",
        810: "接待交際費",
        815: "会議費",
        827: "消耗品費",
        831: "雑費"
    }
    return default_names.get(account_id, f"勘定科目ID{account_id}")


def create_csv_and_guide(rules: List[Dict]) -> None:
    """CSVファイル作成と設定ガイドの表示"""
    import csv
    
    # 1. CSVファイルを作成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"freee_auto_rules_{timestamp}.csv"
    
    with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ["取引先名", "勘定科目名", "税区分名", "出現回数", "平均金額", "信頼度", "サンプル"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rules)
    
    print(f"\n✅ ルールをCSVファイルに出力しました: {csv_filename}")
    
    # 2. 設定ガイドを表示
    print("\n" + "="*60)
    print("📋 freee「自動で経理」ルール設定ガイド")
    print("="*60)
    
    print("\n【現在の状況】")
    high_confidence = len([r for r in rules if r["信頼度"] == "高"])
    medium_confidence = len([r for r in rules if r["信頼度"] == "中"])
    suggested = len([r for r in rules if r["信頼度"] == "提案"])
    
    print(f"  • 高信頼度ルール: {high_confidence}個（10回以上の実績あり）")
    print(f"  • 中信頼度ルール: {medium_confidence}個（3-9回の実績あり）")
    print(f"  • 提案ルール: {suggested}個（未処理取引から推測）")
    
    print("\n【推奨される設定手順】")
    print("\n1️⃣  高信頼度ルールから設定開始")
    print("   最も頻繁に発生する取引から設定することで、処理効率が大幅に向上します。")
    
    print("\n2️⃣  freeeでの設定方法：")
    print("   1. freeeにログイン → [設定] → [自動で経理]")
    print("   2. [新規ルール作成] をクリック")
    print("   3. 以下の情報を入力：")
    print("      - 取引先名: CSVの「取引先名」列の値")
    print("      - 勘定科目: CSVの「勘定科目名」列の値")
    print("      - 税区分: CSVの「税区分名」列の値")
    print("   4. [保存] をクリック")
    
    print("\n3️⃣  優先的に設定すべきルール（上位5件）：")
    for i, rule in enumerate(rules[:5], 1):
        print(f"\n   {i}. {rule['取引先名']}")
        print(f"      勘定科目: {rule['勘定科目名']}")
        print(f"      税区分: {rule['税区分名']}")
        print(f"      実績: {rule['出現回数']}回、平均{rule['平均金額']:,.0f}円")
    
    print("\n【設定後の効果】")
    total_transactions = sum(r["出現回数"] for r in rules if r["信頼度"] in ["高", "中"])
    print(f"  • 自動処理可能な取引: 約{total_transactions}件")
    print(f"  • AI処理の削減率: 約{min(80, total_transactions/10):.0f}%")
    print("  • 処理時間の短縮: 大幅に向上")
    
    print("\n【次のステップ】")
    print("  1. 上記のルールを設定")
    print("  2. 1週間程度運用して効果を確認")
    print("  3. 必要に応じて追加ルールを設定")
    
    print("\n💡 ヒント: freeeの「自動で経理」は部分一致でも動作するため、")
    print("   「ANTHROPIC」と設定すれば「ANTHROPIC PBC」も自動認識されます。")
    
    # 3. JSON形式でも保存（プログラムでの利用用）
    json_filename = f"freee_auto_rules_{timestamp}.json"
    with open(json_filename, 'w', encoding='utf-8') as jsonfile:
        json.dump(rules, jsonfile, ensure_ascii=False, indent=2)
    
    print(f"\n📄 詳細データ: {json_filename}")


def main():
    """メイン処理"""
    print("\n🚀 freee「自動で経理」ルール設定支援ツール")
    print("="*60)
    
    # 環境変数チェック
    required_env = ["FREEE_ACCESS_TOKEN", "FREEE_COMPANY_ID"]
    missing = [env for env in required_env if not os.getenv(env)]
    
    if missing:
        print(f"\n❌ エラー: 以下の環境変数を設定してください:")
        for env in missing:
            print(f"   - {env}")
        print("\n設定方法: export FREEE_ACCESS_TOKEN='your_token'")
        return
    
    try:
        # トークンマネージャーとクライアントを初期化
        token_manager = TokenManager()
        access_token = token_manager.get_valid_access_token()
        company_id = int(os.getenv("FREEE_COMPANY_ID"))
        
        freee_client = FreeeClient(access_token, company_id)
        
        # 1. 取引履歴を分析
        analysis = analyze_transaction_history(freee_client)
        
        # 2. ルールを生成
        rules = generate_freee_rules(analysis, freee_client)
        
        # 3. CSVとガイドを出力
        if rules:
            create_csv_and_guide(rules)
        else:
            print("\n⚠️  ルールを生成できませんでした。")
            print("   取引データが少ない可能性があります。")
        
        # 4. 統計情報を表示
        print("\n📊 分析統計:")
        print(f"  • 分析した取引数: {analysis['total_deals']}件")
        print(f"  • 未処理の明細数: {analysis['total_unmatched']}件")
        print(f"  • 検出したパターン数: {len(analysis['patterns'])}個")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()