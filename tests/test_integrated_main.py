import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# srcディレクトリをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# 統合版のインポート
try:
    from integrated_main import (
        IntegratedFreeeClient, 
        IntegratedClaudeClient, 
        SlackNotifier,
        integrated_process_wallet_txn
    )
    INTEGRATED_AVAILABLE = True
except ImportError as e:
    print(f"Warning: integrated_main.py could not be imported: {e}")
    INTEGRATED_AVAILABLE = False

class TestIntegratedSystem(unittest.TestCase):
    
    def setUp(self):
        if not INTEGRATED_AVAILABLE:
            self.skipTest("integrated_main.py is not available")
            
        # Mock clients
        self.freee_client = MagicMock(spec=IntegratedFreeeClient)
        self.claude_client = MagicMock(spec=IntegratedClaudeClient)
        self.slack_notifier = MagicMock(spec=SlackNotifier)
        self.learning_system = MagicMock()
        
        # Sample transaction
        self.txn = {
            "id": 1,
            "description": "テスト取引",
            "amount": 1000,
            "date": "2025-01-26"
        }

    def test_duplicate_check_prevents_registration(self):
        """重複チェックが正常に動作することをテスト"""
        # 重複取引が見つかった場合
        self.freee_client.check_duplicate_transactions.return_value = [
            {"id": 999, "amount": 1000}
        ]
        
        result = integrated_process_wallet_txn(
            self.txn, self.freee_client, self.claude_client, 
            self.slack_notifier, self.learning_system
        )
        
        self.assertEqual(result["status"], "duplicate_skipped")
        self.assertEqual(result["duplicate_count"], 1)
        self.freee_client.create_deal.assert_not_called()

    def test_high_confidence_auto_registration(self):
        """高信頼度での自動登録をテスト"""
        # 重複なし
        self.freee_client.check_duplicate_transactions.return_value = []
        
        # 高信頼度の分析結果
        self.claude_client.analyze_transaction_with_context.return_value = {
            "account_item_id": 101,
            "tax_code": 21,
            "partner_name": "テスト先",
            "confidence": 0.95
        }
        
        # 請求書消し込みなし
        self.freee_client.clear_related_invoice_transactions.return_value = []
        
        # 取引登録成功
        self.freee_client.create_deal.return_value = {"deal": {"id": 123}}
        
        # DRY_RUNモードではない
        with patch.dict(os.environ, {"DRY_RUN": "false"}):
            result = integrated_process_wallet_txn(
                self.txn, self.freee_client, self.claude_client, 
                self.slack_notifier, self.learning_system
            )
        
        self.assertEqual(result["status"], "registered")
        self.assertEqual(result["deal_id"], 123)
        self.freee_client.create_deal.assert_called_once()
        self.learning_system.record_transaction.assert_called_once()

    def test_low_confidence_slack_notification(self):
        """低信頼度でのSlack通知をテスト"""
        # 重複なし
        self.freee_client.check_duplicate_transactions.return_value = []
        
        # 低信頼度の分析結果
        self.claude_client.analyze_transaction_with_context.return_value = {
            "account_item_id": 101,
            "tax_code": 21,
            "partner_name": "テスト先",
            "confidence": 0.75
        }
        
        # 請求書消し込みなし
        self.freee_client.clear_related_invoice_transactions.return_value = []
        
        # DRY_RUNモードではない
        with patch.dict(os.environ, {"DRY_RUN": "false"}):
            result = integrated_process_wallet_txn(
                self.txn, self.freee_client, self.claude_client, 
                self.slack_notifier, self.learning_system
            )
        
        self.assertEqual(result["status"], "needs_confirmation")
        self.slack_notifier.send_confirmation.assert_called_once()
        self.freee_client.create_deal.assert_not_called()
        self.learning_system.record_transaction.assert_called_once()

    def test_invoice_clearing_for_income(self):
        """収入取引での請求書消し込みをテスト"""
        # 収入取引
        income_txn = self.txn.copy()
        income_txn["amount"] = 10000  # 正の値（収入）
        
        # 重複なし
        self.freee_client.check_duplicate_transactions.return_value = []
        
        # 高信頼度の分析結果
        self.claude_client.analyze_transaction_with_context.return_value = {
            "account_item_id": 101,
            "tax_code": 21,
            "partner_name": "テスト先",
            "confidence": 0.95
        }
        
        # 請求書消し込みあり
        self.freee_client.clear_related_invoice_transactions.return_value = [
            {"id": 888, "amount": 10000}
        ]
        
        # 取引登録成功
        self.freee_client.create_deal.return_value = {"deal": {"id": 123}}
        
        # DRY_RUNモードではない
        with patch.dict(os.environ, {"DRY_RUN": "false"}):
            result = integrated_process_wallet_txn(
                income_txn, self.freee_client, self.claude_client, 
                self.slack_notifier, self.learning_system
            )
        
        self.assertEqual(result["status"], "registered")
        self.assertEqual(len(result["cleared_invoices"]), 1)
        self.freee_client.clear_related_invoice_transactions.assert_called_once_with("テスト先", 10000)

    def test_dry_run_mode(self):
        """DRY_RUNモードのテスト"""
        # 重複なし
        self.freee_client.check_duplicate_transactions.return_value = []
        
        # 高信頼度の分析結果
        self.claude_client.analyze_transaction_with_context.return_value = {
            "account_item_id": 101,
            "tax_code": 21,
            "partner_name": "テスト先",
            "confidence": 0.95
        }
        
        # DRY_RUNモード
        with patch.dict(os.environ, {"DRY_RUN": "true"}):
            result = integrated_process_wallet_txn(
                self.txn, self.freee_client, self.claude_client, 
                self.slack_notifier, self.learning_system
            )
        
        self.assertEqual(result["status"], "dry_run")
        self.freee_client.create_deal.assert_not_called()
        self.freee_client.clear_related_invoice_transactions.assert_not_called()

class TestFreeeClientEnhancements(unittest.TestCase):
    
    def setUp(self):
        if not INTEGRATED_AVAILABLE:
            self.skipTest("integrated_main.py is not available")
            
        # Mock the requests
        self.mock_client = IntegratedFreeeClient("test_token", 12345)
        self.mock_client.headers = {"Authorization": "Bearer test_token"}

    def test_similarity_check(self):
        """摘要の類似性チェックをテスト"""
        # 完全一致
        self.assertTrue(self.mock_client._is_similar_description("Amazon", "Amazon"))
        
        # 一方が他方を含む
        self.assertTrue(self.mock_client._is_similar_description("Amazon Web Services", "Amazon"))
        
        # Jaccard係数による類似性
        self.assertTrue(self.mock_client._is_similar_description("セブンイレブン 渋谷店", "セブンイレブン 新宿店"))
        
        # 類似しない
        self.assertFalse(self.mock_client._is_similar_description("Amazon", "楽天"))

if __name__ == "__main__":
    # 基本的なインポートテスト
    print("=== 基本インポートテスト ===")
    try:
        import integrated_main
        print("✅ integrated_main.py のインポートが成功しました")
    except Exception as e:
        print(f"❌ integrated_main.py のインポートエラー: {e}")
    
    try:
        import enhanced_main
        print("✅ enhanced_main.py のインポートが成功しました")
    except Exception as e:
        print(f"❌ enhanced_main.py のインポートエラー: {e}")
    
    # ユニットテスト実行
    print("\n=== ユニットテスト実行 ===")
    unittest.main()