#!/usr/bin/env python
"""
レシート紐付けスクリプトのテスト
TDD和田流アプローチで段階的にテスト
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

class TestReceiptLinkingIntegration(unittest.TestCase):
    """レシート紐付け処理の統合テスト"""
    
    def setUp(self):
        """テスト環境のセットアップ"""
        self.env_vars = {
            'FREEE_CLIENT_ID': 'test_client_id',
            'FREEE_CLIENT_SECRET': 'test_client_secret',
            'FREEE_REFRESH_TOKEN': 'test_refresh_token',
            'FREEE_ACCESS_TOKEN': 'test_access_token',
            'FREEE_COMPANY_ID': '123456',
            'GITHUB_TOKEN': 'test_github_token',
            'DRY_RUN': 'true',
            'RECEIPT_LIMIT': '5',
            'TARGET_TYPE': 'both'
        }
    
    def test_1_import_modules(self):
        """STEP 1: 必要なモジュールがインポートできるか"""
        try:
            from token_manager import integrate_with_main
            from state_store import init_db, write_audit
            from config_loader import load_linking_config
            from filebox_client import FileBoxClient
            from ocr_models import ReceiptRecord
            from linker import find_best_target, normalize_targets, ensure_not_duplicated_and_link, decide_action
            print("✅ STEP 1: 全モジュールのインポート成功")
        except ImportError as e:
            self.fail(f"❌ インポートエラー: {e}")
    
    def test_2_token_manager_integration(self):
        """STEP 2: integrate_with_main関数が正しく動作するか"""
        with patch.dict(os.environ, self.env_vars):
            from token_manager import integrate_with_main
            
            # integrate_with_main の戻り値を確認
            with patch('token_manager.FreeeTokenManager') as mock_manager:
                mock_instance = Mock()
                mock_instance.auto_refresh_if_needed.return_value = None
                mock_manager.return_value = mock_instance
                
                # integrate_with_mainは access_token を返す
                with patch.dict(os.environ, {'FREEE_ACCESS_TOKEN': 'test_token'}):
                    result = integrate_with_main()
                    self.assertEqual(result, 'test_token')
                    print("✅ STEP 2: integrate_with_main関数の動作確認成功")
    
    def test_3_main_function_dry_run(self):
        """STEP 3: main関数がDRY_RUNモードで動作するか"""
        with patch.dict(os.environ, self.env_vars):
            # 必要なモックを準備
            with patch('process_receipts_main.integrate_with_main') as mock_integrate:
                mock_integrate.return_value = 'test_access_token'
                
                with patch('process_receipts_main.init_db'):
                    with patch('process_receipts_main.load_linking_config') as mock_config:
                        mock_config.return_value = {
                            'thresholds': {'auto': 85, 'assist_min': 65, 'assist_max': 84}
                        }
                        
                        with patch('process_receipts_main.FileBoxClient') as mock_filebox:
                            mock_fb_instance = Mock()
                            mock_fb_instance.list_receipts.return_value = []
                            mock_filebox.return_value = mock_fb_instance
                            
                            # main関数をインポートして実行
                            from process_receipts_main import main
                            
                            # エラーなく実行できることを確認
                            try:
                                main()
                                print("✅ STEP 3: main関数のDRY_RUN実行成功")
                            except Exception as e:
                                self.fail(f"❌ main関数実行エラー: {e}")
    
    def test_4_receipt_processing(self):
        """STEP 4: レシート処理のフロー全体をテスト"""
        with patch.dict(os.environ, self.env_vars):
            # モックレシートデータ
            mock_receipts = [
                {
                    'id': '1',
                    'description': 'テスト店舗',
                    'amount': 1000,
                    'created_at': '2024-01-01T10:00:00'
                }
            ]
            
            # モック取引データ
            mock_targets = [
                {
                    'id': 'tx_1',
                    'amount': 1000,
                    'date': '2024-01-01',
                    'description': 'テスト店舗',
                    'type': 'wallet_txn'
                }
            ]
            
            with patch('process_receipts_main.integrate_with_main') as mock_integrate:
                mock_integrate.return_value = 'test_access_token'
                
                with patch('process_receipts_main.init_db'):
                    with patch('process_receipts_main.load_linking_config') as mock_config:
                        mock_config.return_value = {
                            'thresholds': {'auto': 85, 'assist_min': 65, 'assist_max': 84}
                        }
                        
                        with patch('process_receipts_main.FileBoxClient') as mock_filebox_class:
                            mock_fb = Mock()
                            mock_fb.list_receipts.return_value = mock_receipts
                            mock_fb.download_receipt.return_value = b'test_data'
                            mock_filebox_class.return_value = mock_fb
                            mock_filebox_class.sha1_of_bytes.return_value = 'test_sha1'
                            
                            with patch('process_receipts_main.normalize_targets') as mock_normalize:
                                mock_normalize.return_value = mock_targets
                                
                                with patch('process_receipts_main.find_best_target') as mock_find:
                                    mock_find.return_value = {
                                        'id': 'tx_1',
                                        'score': 90,
                                        'type': 'wallet_txn',
                                        'amount': 1000
                                    }
                                    
                                    with patch('process_receipts_main.decide_action') as mock_decide:
                                        mock_decide.return_value = 'AUTO'
                                        
                                        with patch('process_receipts_main.ensure_not_duplicated_and_link'):
                                            from process_receipts_main import main
                                            
                                            # DRY_RUNモードで実行
                                            try:
                                                main()
                                                print("✅ STEP 4: レシート処理フロー全体のテスト成功")
                                            except Exception as e:
                                                self.fail(f"❌ レシート処理エラー: {e}")


def run_tests():
    """テストを実行"""
    print("\n" + "="*60)
    print("🧪 TDD和田流でレシート紐付けスクリプトをテスト")
    print("="*60 + "\n")
    
    # テストスイートを作成
    suite = unittest.TestLoader().loadTestsFromTestCase(TestReceiptLinkingIntegration)
    
    # テストを実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 結果サマリー
    print("\n" + "="*60)
    if result.wasSuccessful():
        print("✅ 全テスト成功！")
    else:
        print(f"❌ テスト失敗: {len(result.failures)} 件のエラー")
        for test, traceback in result.failures:
            print(f"\n失敗したテスト: {test}")
            print(traceback)
    print("="*60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)