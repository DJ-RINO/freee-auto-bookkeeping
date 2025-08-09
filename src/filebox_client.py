import os
import hashlib
import requests
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

    @staticmethod
    def sha1_of_bytes(data: bytes) -> str:
        h = hashlib.sha1()
        h.update(data)
        return h.hexdigest()


