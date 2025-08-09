from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class ReceiptRecord:
    receipt_id: str
    file_hash: str
    vendor: str
    date: date
    amount: int
    tax_rate: Optional[float] = None
    ocr_confidence: Optional[float] = None


@dataclass
class MatchCandidate:
    tx_id: str
    score: int
    reasons: list[str]
    deltas: dict


@dataclass
class Decision:
    interaction_id: str
    action: str  # approve|edit|reject
    patch: dict
    decided_by: str
    decided_at: str


@dataclass
class AuditLog:
    ts: str
    actor: str
    action: str
    target_ids: list[str]
    score: Optional[int]
    result: str
    error: Optional[str] = None


