import argparse
import os
import sys
import time
from typing import Optional
import json
from datetime import datetime

import requests

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from state_store import get_pending, write_audit, init_db, put_pending
from token_manager import integrate_with_main


def _refresh_access_token() -> str:
    # Minimal refresh using env tokens already managed by workflow
    # Here we assume FREEE_ACCESS_TOKEN is either already valid or Freee client in main handles it.
    return os.getenv("FREEE_ACCESS_TOKEN", "")


def _call_with_backoff(method, url, headers=None, json=None, params=None, max_retries=5):
    backoff = 1
    for i in range(max_retries):
        r = requests.request(method, url, headers=headers, json=json, params=params)
        if r.status_code not in (429, 500, 502, 503, 504):
            r.raise_for_status()
            return r
        time.sleep(backoff)
        backoff = min(backoff * 2, 16)
    r.raise_for_status()


def apply_decision(interaction_id: str, action: str, amount: Optional[int], date: Optional[str], vendor: Optional[str]):
    """
    Slackインタラクションからの決定を適用
    """
    print(f"🎯 決定適用処理: {interaction_id} → {action}")
    
    # データベース初期化
    init_db()
    
    # pending情報を取得
    pending = get_pending(interaction_id)
    if not pending:
        print(f"⚠️ 該当する待機中インタラクションが見つかりません: {interaction_id}")
        # 代替手段: interaction_idからreceipt_idを抽出
        if "receipt_" in interaction_id:
            receipt_id = interaction_id.split("receipt_")[1].split("_")[0]
            print(f"📄 レシートID {receipt_id} として処理を試行")
            pending = {"receipt_id": receipt_id, "tx_id": None, "candidate_data": {}}
        else:
            print("❌ レシートIDが特定できません")
            return
    
    receipt_id = pending.get("receipt_id")
    tx_id = pending.get("tx_id")
    
    # アクセストークン取得
    try:
        access_token = integrate_with_main()
        company_id = int(os.getenv("FREEE_COMPANY_ID"))
        print(f"✅ アクセストークン取得完了")
    except Exception as e:
        print(f"❌ トークン取得エラー: {e}")
        write_audit("ERROR", "slack", f"decision:{action}", [receipt_id], 0, "token_error", str(e))
        return
    
    # 決定に基づく処理
    if action == "approve":
        # 自動紐付けを実行
        print(f"✅ 承認: レシート {receipt_id} を取引 {tx_id} に紐付け")
        
        if tx_id:
            try:
                # freee APIで実際に紐付け実行
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                
                url = f"https://api.freee.co.jp/api/1/wallet_txns/{tx_id}/receipts/{receipt_id}"
                params = {"company_id": company_id}
                
                response = requests.put(url, headers=headers, params=params)
                
                if response.status_code in (200, 201):
                    print(f"✅ 紐付け成功: レシート {receipt_id} → 取引 {tx_id}")
                    write_audit("INFO", "slack", f"decision:approve", [receipt_id], tx_id, "linked")
                else:
                    print(f"❌ 紐付けAPI失敗: {response.status_code} - {response.text[:200]}")
                    write_audit("ERROR", "slack", f"decision:approve", [receipt_id], tx_id, "api_error", response.text[:200])
                    
            except Exception as e:
                print(f"❌ 紐付け処理エラー: {e}")
                write_audit("ERROR", "slack", f"decision:approve", [receipt_id], tx_id, "exception", str(e))
        else:
            print("⚠️ 取引IDが不明のため紐付けスキップ")
            write_audit("WARNING", "slack", f"decision:approve", [receipt_id], 0, "no_tx_id")
            
    elif action == "edit":
        # 修正後の値で再マッチング
        print(f"✏️ 修正: レシート {receipt_id} の情報を更新")
        
        edit_info = {}
        if amount:
            edit_info["amount"] = amount
        if date:
            edit_info["date"] = date
        if vendor:
            edit_info["vendor"] = vendor
            
        print(f"   修正内容: {edit_info}")
        write_audit("INFO", "slack", f"decision:edit", [receipt_id], 0, "modified", json.dumps(edit_info))
        
        # TODO: 修正された情報で再マッチングを実行
        # この機能は今後の拡張で実装
        
    elif action == "reject":
        # 拒否 - 手動対応待ちにマーク
        print(f"❌ 拒否: レシート {receipt_id} は手動対応")
        write_audit("INFO", "slack", f"decision:reject", [receipt_id], 0, "manual_required")
    
    # 処理完了
    print(f"🎉 決定適用完了: {action} for receipt {receipt_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interaction-id", required=True)
    parser.add_argument("--action", required=True, choices=["approve", "edit", "reject"])
    parser.add_argument("--amount", type=int, help="修正後の金額")
    parser.add_argument("--date", help="修正後の日付 (YYYY-MM-DD)")
    parser.add_argument("--vendor", help="修正後の店舗名")
    args = parser.parse_args()

    apply_decision(args.interaction_id, args.action, args.amount, args.date, args.vendor)


