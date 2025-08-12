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
        url = f"{self.base_url}/receipts"
        params = {"company_id": self.company_id, "limit": limit}
        r = requests.get(url, headers=self.headers, params=params)
        r.raise_for_status()
        return r.json().get("receipts", [])

    def download_receipt(self, receipt_id: int) -> bytes:
        url = f"{self.base_url}/receipts/{receipt_id}/download"
        params = {"company_id": self.company_id}
        r = requests.get(url, headers=self.headers, params=params)
        r.raise_for_status()
        return r.content

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


