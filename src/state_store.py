import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Dict, Optional


def _get_db_path() -> str:
    """環境変数から毎回DBパスを取得（テストでの monkeypatch に追従するため）。"""
    return os.getenv("RECEIPT_STATE_DB", "receipt_state.db")


@contextmanager
def _conn():
    con = sqlite3.connect(_get_db_path())
    con.execute("PRAGMA journal_mode=WAL;")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with _conn() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS linked_hashes (
              receipt_hash TEXT PRIMARY KEY,
              meta_json TEXT,
              linked_at TEXT
            );
            """
        )
        # ファイル重複検出用（ファイルのSHA1ごとに、関連するreceipt_idの集合を保持）
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS file_digests (
              file_sha1 TEXT PRIMARY KEY,
              receipt_ids_json TEXT,
              first_seen_at TEXT
            );
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS pending (
              interaction_id TEXT PRIMARY KEY,
              receipt_id TEXT,
              tx_id TEXT,
              candidates_json TEXT,
              candidate_data TEXT,
              expire_at TEXT
            );
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
              ts TEXT,
              level TEXT,
              actor TEXT,
              action TEXT,
              target_ids TEXT,
              score INTEGER,
              result TEXT,
              error TEXT
            );
            """
        )


def is_duplicated(receipt_hash: str) -> bool:
    with _conn() as con:
        # 存在チェックのみ。テストで初期状態はFalseになることを期待
        cur = con.execute("SELECT 1 FROM linked_hashes WHERE receipt_hash=?", (receipt_hash,))
        return cur.fetchone() is not None


def mark_linked(receipt_hash: str, meta: Dict):
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO linked_hashes(receipt_hash, meta_json, linked_at) VALUES (?,?,?)",
            (receipt_hash, json.dumps(meta, ensure_ascii=False), datetime.utcnow().isoformat()),
        )


def put_pending(interaction_id: str, receipt_id: str, tx_id: str = None, candidates: list = None, candidate_data: dict = None, ttl_minutes: int = 120):
    with _conn() as con:
        expire_at = (datetime.utcnow() + timedelta(minutes=ttl_minutes)).isoformat()
        con.execute(
            "INSERT OR REPLACE INTO pending(interaction_id, receipt_id, tx_id, candidates_json, candidate_data, expire_at) VALUES (?,?,?,?,?,?)",
            (
                interaction_id, 
                receipt_id, 
                tx_id,
                json.dumps(candidates or [], ensure_ascii=False), 
                json.dumps(candidate_data or {}, ensure_ascii=False),
                expire_at
            ),
        )


def get_pending(interaction_id: str) -> Optional[Dict]:
    with _conn() as con:
        cur = con.execute("SELECT receipt_id, tx_id, candidates_json, candidate_data, expire_at FROM pending WHERE interaction_id=?", (interaction_id,))
        row = cur.fetchone()
        if not row:
            return None
        receipt_id, tx_id, candidates_json, candidate_data, expire_at = row
        return {
            "receipt_id": receipt_id,
            "tx_id": tx_id,
            "candidates": json.loads(candidates_json or "[]"),
            "candidate_data": json.loads(candidate_data or "{}"),
            "expire_at": expire_at,
        }


def write_audit(level: str, actor: str, action: str, target_ids: list, score: int, result: str, error: str | None = None):
    with _conn() as con:
        con.execute(
            "INSERT INTO audit_log(ts, level, actor, action, target_ids, score, result, error) VALUES (?,?,?,?,?,?,?,?)",
            (datetime.utcnow().isoformat(), level, actor, action, json.dumps(target_ids), score, result, error),
        )


def record_file_seen(file_sha1: str, receipt_id: str):
    """ファイルのSHA1に紐づくreceipt_idを記録する。重複は集合的に保持。
    """
    with _conn() as con:
        cur = con.execute("SELECT receipt_ids_json FROM file_digests WHERE file_sha1=?", (file_sha1,))
        row = cur.fetchone()
        if row and row[0]:
            try:
                ids = set(json.loads(row[0]))
            except Exception:
                ids = set()
        else:
            ids = set()
        ids.add(str(receipt_id))
        con.execute(
            "INSERT OR REPLACE INTO file_digests(file_sha1, receipt_ids_json, first_seen_at) VALUES (?,?,?)",
            (file_sha1, json.dumps(sorted(list(ids))), datetime.utcnow().isoformat()),
        )


def get_existing_for_file_sha1(file_sha1: str) -> list[str]:
    """同じファイルSHA1で既に登録済みのreceipt_idリストを返す。なければ空。
    """
    with _conn() as con:
        cur = con.execute("SELECT receipt_ids_json FROM file_digests WHERE file_sha1=?", (file_sha1,))
        row = cur.fetchone()
        if not row or not row[0]:
            return []
        try:
            return list(json.loads(row[0]))
        except Exception:
            return []


