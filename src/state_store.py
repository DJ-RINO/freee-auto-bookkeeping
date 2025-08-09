import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Dict, Optional


DB_PATH = os.getenv("RECEIPT_STATE_DB", "receipt_state.db")


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
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
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS pending (
              interaction_id TEXT PRIMARY KEY,
              receipt_id TEXT,
              candidates_json TEXT,
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
        cur = con.execute("SELECT 1 FROM linked_hashes WHERE receipt_hash=?", (receipt_hash,))
        return cur.fetchone() is not None


def mark_linked(receipt_hash: str, meta: Dict):
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO linked_hashes(receipt_hash, meta_json, linked_at) VALUES (?,?,?)",
            (receipt_hash, json.dumps(meta, ensure_ascii=False), datetime.utcnow().isoformat()),
        )


def put_pending(interaction_id: str, receipt_id: str, candidates: list, ttl_minutes: int = 120):
    with _conn() as con:
        expire_at = (datetime.utcnow() + timedelta(minutes=ttl_minutes)).isoformat()
        con.execute(
            "INSERT OR REPLACE INTO pending(interaction_id, receipt_id, candidates_json, expire_at) VALUES (?,?,?,?)",
            (interaction_id, receipt_id, json.dumps(candidates, ensure_ascii=False), expire_at),
        )


def get_pending(interaction_id: str) -> Optional[Dict]:
    with _conn() as con:
        cur = con.execute("SELECT receipt_id, candidates_json, expire_at FROM pending WHERE interaction_id=?", (interaction_id,))
        row = cur.fetchone()
        if not row:
            return None
        receipt_id, candidates_json, expire_at = row
        return {
            "receipt_id": receipt_id,
            "candidates": json.loads(candidates_json),
            "expire_at": expire_at,
        }


def write_audit(level: str, actor: str, action: str, target_ids: list, score: int, result: str, error: str | None = None):
    with _conn() as con:
        con.execute(
            "INSERT INTO audit_log(ts, level, actor, action, target_ids, score, result, error) VALUES (?,?,?,?,?,?,?,?)",
            (datetime.utcnow().isoformat(), level, actor, action, json.dumps(target_ids), score, result, error),
        )


