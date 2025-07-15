import sys
import os
import unittest
from unittest.mock import MagicMock

# srcディレクトリをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from main import process_wallet_txn, FreeeClient, ClaudeClient, SlackNotifier

class TestAutoBookkeepingMain(unittest.TestCase):
    def setUp(self):
        self.freee_client = MagicMock(spec=FreeeClient)
        self.claude_client = MagicMock(spec=ClaudeClient)
        self.slack_notifier = MagicMock(spec=SlackNotifier)
        self.txn = {"id": 1, "description": "テスト取引", "amount": 1000}

    def test_auto_register_when_confidence_90_or_higher(self):
        self.claude_client.analyze_transaction.return_value = {
            "account_item_id": 101,
            "tax_code": 21,
            "partner_name": "テスト先",
            "confidence": 0.91
        }
        self.freee_client.create_deal.return_value = {"deal": {"id": 123}}
        result = process_wallet_txn(self.txn, self.freee_client, self.claude_client, self.slack_notifier)
        self.assertEqual(result["status"], "registered")
        self.freee_client.create_deal.assert_called_once()
        self.slack_notifier.send_confirmation.assert_not_called()

    def test_slack_notify_when_confidence_below_90(self):
        self.claude_client.analyze_transaction.return_value = {
            "account_item_id": 101,
            "tax_code": 21,
            "partner_name": "テスト先",
            "confidence": 0.89
        }
        result = process_wallet_txn(self.txn, self.freee_client, self.claude_client, self.slack_notifier)
        self.assertEqual(result["status"], "needs_confirmation")
        self.slack_notifier.send_confirmation.assert_called_once()
        self.freee_client.create_deal.assert_not_called()

if __name__ == "__main__":
    unittest.main() 