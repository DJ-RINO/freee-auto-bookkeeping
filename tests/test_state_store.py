from src.state_store import init_db, is_duplicated, mark_linked, put_pending, get_pending


def test_dedup_and_pending(tmp_path, monkeypatch):
    db = tmp_path / "state.db"
    monkeypatch.setenv("RECEIPT_STATE_DB", str(db))
    init_db()

    assert not is_duplicated("h1")
    mark_linked("h1", {"x": 1})
    assert is_duplicated("h1")

    put_pending("i1", "r1", [{"tx_id": "1"}])
    p = get_pending("i1")
    assert p["receipt_id"] == "r1"
    assert p["candidates"][0]["tx_id"] == "1"


