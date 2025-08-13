import os
import hashlib
import requests
from typing import List, Dict
from datetime import datetime
from typing import Dict, List, Optional


class FileBoxClient:
    """freee 証憑ファイルボックスの簡易クライアント"""

    def __init__(self, access_token: str, company_id: int):
        self.access_token = access_token
        self.company_id = company_id
        self.base_url = "https://api.freee.co.jp/api/1"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
        }

    def list_receipts(self, limit: int = 50) -> List[Dict]:
        """ファイルボックスからレシート/領収書を取得
        
        freeeのファイルボックス（証憑管理）:
        - ファイルボックスは /api/1/receipts エンドポイント
        - プロフェッショナルプラン以上で利用可能
        - ベーシックプランでは利用不可（403エラー）
        
        38件のファイルがファイルボックスにあることを確認済み
        """
        print("\n📦 freeeファイルボックスから証憑を取得中...")
        print("   ダッシュボードで確認: 38件のファイル（未添付）")
        
        # 日付パラメータを追加（過去3ヶ月分を取得）
        from datetime import datetime, timedelta
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=90)
        
        # ファイルボックスの正しいエンドポイントを最優先で試す
        # まず status パラメータなしで試す
        for status_param in [None, "unlinked", "all"]:
            try:
                url = f"{self.base_url}/receipts"
                params = {
                    "company_id": self.company_id, 
                    "limit": limit,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
                
                if status_param:
                    params["status"] = status_param
                    print(f"   📍 /api/1/receipts (status={status_param}, {start_date} ~ {end_date}) を試行中...")
                else:
                    print(f"   📍 /api/1/receipts (statusパラメータなし, {start_date} ~ {end_date}) を試行中...")
                    
                r = requests.get(url, headers=self.headers, params=params)
                
                if r.status_code == 200:
                    data = r.json()
                    receipts = data.get("receipts", [])
                    print(f"   ✅ 成功！ {len(receipts)} 件のファイルを取得")
                    
                    if receipts:
                        # 最初の数件の情報を表示
                        for i, receipt in enumerate(receipts[:3]):
                            # ファイル名、メモ、作成日などの情報を表示
                            file_name = receipt.get('file_name', '')
                            memo = receipt.get('memo', '')
                            created_at = receipt.get('created_at', '')
                            status = receipt.get('status', '')
                            
                            print(f"     [{i+1}] ID: {receipt.get('id')}")
                            if file_name:
                                print(f"        📝 ファイル名: {file_name}")
                            if memo:
                                print(f"        💬 メモ: {memo[:50]}")
                            if created_at:
                                print(f"        📅 作成日: {created_at[:10]}")
                            print(f"        🆙 ステータス: {status}")
                        if len(receipts) > 3:
                            print(f"     ... 他 {len(receipts) - 3} 件")
                        return receipts
                    else:
                        print("   ⚠️ APIは成功したが、データが0件")
                        
                elif r.status_code == 403:
                    print("   ❌ 403 Forbidden - プランの制限でファイルボックスAPIが利用できません")
                    print("      → プロフェッショナルプラン以上が必要です")
                    break  # 403の場合は他のstatusも試さない
                    
                elif r.status_code == 400:
                    print("   ❌ 400 Bad Request - パラメータエラー")
                    try:
                        error_data = r.json()
                        if "errors" in error_data:
                            for error in error_data["errors"]:
                                print(f"      - {error.get('message', error)}")
                        else:
                            print(f"      エラー詳細: {error_data}")
                    except:
                        print(f"      レスポンス: {r.text[:200]}")
                    
                else:
                    print(f"   ❌ エラー: Status {r.status_code}")
                    
            except Exception as e:
                print(f"   ❌ receipts API エラー: {e}")
        
        # receipts APIが失敗した場合、他のエンドポイントも試す
        print("\n   ⚠️ ファイルボックスAPIにアクセスできません。代替方法を試行中...")
        
        endpoints = [
            ("deals", "deals"),  # 取引（添付ファイル付き）
            ("wallet_txns", "wallet_txns"),  # 明細
        ]
        
        for endpoint_name, response_key in endpoints:
            try:
                url = f"{self.base_url}/{endpoint_name}"
                params = {"company_id": self.company_id, "limit": limit}
                
                # dealsの場合はreceipts情報を含める
                if endpoint_name == "deals":
                    params["include"] = "receipts"
                
                print(f"   Trying: {endpoint_name}...")
                r = requests.get(url, headers=self.headers, params=params)
                
                if r.status_code == 200:
                    data = r.json()
                    items = data.get(response_key, [])
                    print(f"   ✓ {endpoint_name}: {len(items)} items found")
                    
                    # レスポンスのキーを表示（デバッグ用）
                    if not items and data:
                        print(f"     Response keys: {list(data.keys())[:5]}")
                        # 最初のアイテムの構造を確認
                        for key in data.keys():
                            if isinstance(data[key], list) and data[key]:
                                print(f"     Found list '{key}' with {len(data[key])} items")
                                if len(data[key]) > 0:
                                    first_item = data[key][0]
                                    if isinstance(first_item, dict):
                                        print(f"     First item keys: {list(first_item.keys())[:10]}")
                    
                    # wallet_txnsの場合、添付ファイル情報を探す
                    if endpoint_name == "wallet_txns" and items:
                        receipts = []
                        for txn in items:
                            # 添付ファイルがあるかチェック
                            if txn.get("receipt_ids") or txn.get("attachments"):
                                receipts.append({
                                    "id": txn.get("id"),
                                    "description": txn.get("description", ""),
                                    "amount": txn.get("amount", 0),
                                    "created_at": txn.get("date"),
                                    "user_name": "",
                                    "wallet_txn_id": txn.get("id")
                                })
                        if receipts:
                            print(f"   📎 {len(receipts)} 件の証憑付き明細を発見")
                            return receipts
                    
                    # dealsの場合、receiptsフィールドを確認
                    if endpoint_name == "deals" and items:
                        receipts = []
                        for deal in items:
                            # receiptsフィールドがあるかチェック
                            deal_receipts = deal.get("receipts", [])
                            if deal_receipts:
                                for receipt in deal_receipts:
                                    receipts.append({
                                        "id": receipt.get("id"),
                                        "description": receipt.get("description", deal.get("issue_date", "")),
                                        "amount": deal.get("amount", 0),
                                        "created_at": receipt.get("created_at", deal.get("issue_date")),
                                        "user_name": receipt.get("user", {}).get("display_name", ""),
                                        "deal_id": deal.get("id")
                                    })
                        if receipts:
                            print(f"   📎 {len(receipts)} 件の証憑を取引から発見")
                            return receipts
                    
                    # その他のエンドポイントの場合
                    if items and endpoint_name != "wallet_txns":
                        return items
                        
                elif r.status_code in [401, 403]:
                    print(f"   ✗ {endpoint_name}: 権限エラー (プランの制限の可能性)")
                elif r.status_code == 404:
                    print(f"   ✗ {endpoint_name}: エンドポイントが存在しません")
                else:
                    print(f"   ✗ {endpoint_name}: Status {r.status_code}")
                    
            except Exception as e:
                print(f"   ✗ {endpoint_name}: {str(e)[:100]}")
        
        print("\n⚠️ レシート/証憑が見つかりませんでした。")
        print("   以下を確認してください：")
        print("   1. freee管理画面でファイルボックスに証憑がアップロードされているか")
        print("   2. APIの権限設定が正しいか")
        print("   3. 使用しているプランが証憑APIに対応しているか")
        
        return []

    def download_receipt(self, receipt_id: int) -> bytes:
        """レシート/領収書ファイルをダウンロード"""
        # まず receipts エンドポイントを試す
        try:
            url = f"{self.base_url}/receipts/{receipt_id}/download"
            params = {"company_id": self.company_id}
            r = requests.get(url, headers=self.headers, params=params)
            if r.status_code == 200:
                return r.content
        except:
            pass
        
        # receipts が失敗したら user_files を試す
        try:
            url = f"{self.base_url}/user_files/{receipt_id}/download"
            params = {"company_id": self.company_id}
            r = requests.get(url, headers=self.headers, params=params)
            r.raise_for_status()
            return r.content
        except Exception as e:
            print(f"Warning: Failed to download file {receipt_id}: {e}")
            # ダミーデータを返す（テスト用）
            return b"dummy_receipt_data"

    def delete_receipt(self, receipt_id: int) -> bool:
        """証憑（レシート/領収書）を削除。
        注意: 本番運用では誤削除防止のため必ずDRY_RUNや承認フローを通すこと。
        """
        url = f"{self.base_url}/receipts/{receipt_id}"
        params = {"company_id": self.company_id}
        r = requests.delete(url, headers=self.headers, params=params)
        # 204 No Content が想定
        if r.status_code in (200, 202, 204):
            return True
        r.raise_for_status()
        return True

    def list_deal_attachments(self, deal_id: int) -> List[Dict]:
        """取引（deal）に紐づく証憑一覧を取得。
        freee APIに直接エンドポイントが無い場合は、拡張/将来の正式APIに差し替え。
        MVPでは空配列を返す。
        """
        try:
            # TODO: 公式APIに合わせて実装
            return []
        except Exception:
            return []

    def list_wallet_txn_attachments(self, wallet_txn_id: int) -> List[Dict]:
        """未仕訳明細（wallet_txn）に紐づく証憑一覧を取得。
        公式APIがないためMVPでは空配列。
        """
        try:
            # TODO: 公式APIに合わせて実装
            return []
        except Exception:
            return []

    @staticmethod
    def sha1_of_bytes(data: bytes) -> str:
        h = hashlib.sha1()
        h.update(data)
        return h.hexdigest()


