import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
from datetime import datetime, timedelta
import sys
import os

# srcディレクトリをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from token_manager import FreeeTokenManager


class TestFreeeTokenManager(unittest.TestCase):
    """freeeトークン管理のテストケース"""
    
    def setUp(self):
        """各テストの前に実行される初期化"""
        self.client_id = "test_client_id"
        self.client_secret = "test_client_secret"
        self.github_token = "test_github_token"
        self.manager = FreeeTokenManager(
            self.client_id,
            self.client_secret,
            self.github_token
        )
    
    @patch('token_manager.requests.post')
    def test_refresh_token_success(self, mock_post):
        """リフレッシュトークンで新しいアクセストークンを取得できる"""
        # Arrange
        refresh_token = "test_refresh_token"
        expected_access_token = "new_access_token"
        expected_refresh_token = "new_refresh_token"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": expected_access_token,
            "refresh_token": expected_refresh_token,
            "expires_in": 86400,
            "token_type": "bearer"
        }
        mock_post.return_value = mock_response
        
        # Act
        result = self.manager.refresh_token(refresh_token)
        
        # Assert
        self.assertEqual(result["access_token"], expected_access_token)
        self.assertEqual(result["refresh_token"], expected_refresh_token)
        self.assertIn("expires_at", result)
        
        # POSTリクエストの検証
        mock_post.assert_called_once_with(
            self.manager.token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
        )
    
    @patch('token_manager.requests.post')
    def test_refresh_token_failure(self, mock_post):
        """リフレッシュトークンが無効な場合はエラーになる"""
        # Arrange
        refresh_token = "invalid_refresh_token"
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
        mock_post.return_value = mock_response
        
        # Act & Assert
        with self.assertRaises(Exception) as context:
            self.manager.refresh_token(refresh_token)
        
        self.assertIn("401", str(context.exception))
    
    @patch('token_manager.requests.get')
    def test_auto_refresh_when_token_expired(self, mock_get):
        """アクセストークンが期限切れの場合、自動的にリフレッシュされる"""
        # Arrange
        current_token = "expired_token"
        refresh_token = "valid_refresh_token"
        
        # 最初のGETは401を返す（トークン無効）
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        # リフレッシュトークンのモック
        with patch.object(self.manager, 'refresh_token') as mock_refresh:
            new_token_data = {
                "access_token": "new_token",
                "refresh_token": "new_refresh",
                "expires_in": 86400
            }
            mock_refresh.return_value = new_token_data
            
            # Act
            result = self.manager.auto_refresh_if_needed(current_token, refresh_token)
            
            # Assert
            self.assertEqual(result, new_token_data)
            mock_refresh.assert_called_once_with(refresh_token)
    
    @patch('token_manager.requests.get')
    def test_auto_refresh_when_token_valid(self, mock_get):
        """アクセストークンが有効な場合、リフレッシュされない"""
        # Arrange
        current_token = "valid_token"
        refresh_token = "valid_refresh_token"
        
        # GETは200を返す（トークン有効）
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Act
        result = self.manager.auto_refresh_if_needed(current_token, refresh_token)
        
        # Assert
        self.assertIsNone(result)
    
    @patch('builtins.open', mock_open())
    def test_save_tokens_locally(self):
        """トークンをローカルファイルに保存できる"""
        # Arrange
        token_data = {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
            "expires_at": "2025-07-15T10:00:00"
        }
        file_path = ".tokens.json"
        
        # Act
        self.manager.save_tokens_locally(token_data, file_path)
        
        # Assert
        handle = open.return_value
        handle.write.assert_called()
        
        # 書き込まれた内容を検証
        written_content = ''.join(call.args[0] for call in handle.write.call_args_list)
        written_data = json.loads(written_content)
        self.assertEqual(written_data["access_token"], token_data["access_token"])
    
    @patch('builtins.open', mock_open(read_data='{"access_token": "loaded_token"}'))
    def test_load_tokens_locally(self):
        """ローカルファイルからトークンを読み込める"""
        # Act
        result = self.manager.load_tokens_locally(".tokens.json")
        
        # Assert
        self.assertEqual(result["access_token"], "loaded_token")
    
    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_load_tokens_locally_file_not_found(self, mock_file):
        """ファイルが存在しない場合はNoneを返す"""
        # Act
        result = self.manager.load_tokens_locally("nonexistent.json")
        
        # Assert
        self.assertIsNone(result)
    
    @patch('token_manager.requests.put')
    @patch('token_manager.requests.get')
    def test_update_github_secret(self, mock_get, mock_put):
        """GitHub Secretsを更新できる"""
        # Arrange
        repo = "test/repo"
        secret_name = "TEST_SECRET"
        secret_value = "secret_value"
        
        # 公開鍵の取得をモック
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "key": "base64_encoded_public_key",
            "key_id": "12345"
        }
        mock_get.return_value = mock_get_response
        
        # Secret更新のモック
        mock_put_response = MagicMock()
        mock_put_response.status_code = 204
        mock_put.return_value = mock_put_response
        
        # naclライブラリのモック
        with patch('token_manager.public.PublicKey'), \
             patch('token_manager.public.SealedBox') as mock_sealed_box, \
             patch('token_manager.base64.b64encode') as mock_b64encode:
            
            # 暗号化のモック
            mock_sealed_box.return_value.encrypt.return_value = b"encrypted"
            mock_b64encode.return_value.decode.return_value = "encrypted_base64"
            
            # Act
            result = self.manager.update_github_secret(repo, secret_name, secret_value)
            
            # Assert
            self.assertTrue(result)
            mock_put.assert_called_once()
    
    def test_update_github_secret_without_token(self):
        """GitHubトークンがない場合はFalseを返す"""
        # Arrange
        manager_without_token = FreeeTokenManager(self.client_id, self.client_secret, None)
        
        # Act
        result = manager_without_token.update_github_secret("repo", "secret", "value")
        
        # Assert
        self.assertFalse(result)


class TestIntegrationWithMain(unittest.TestCase):
    """main.pyとの統合テスト"""
    
    @patch.dict(os.environ, {
        'FREEE_CLIENT_ID': 'test_id',
        'FREEE_CLIENT_SECRET': 'test_secret',
        'FREEE_REFRESH_TOKEN': 'test_refresh',
        'FREEE_ACCESS_TOKEN': 'test_access',
        'GITHUB_TOKEN': 'test_github',
        'GITHUB_REPOSITORY': 'test/repo'
    })
    @patch('token_manager.FreeeTokenManager.auto_refresh_if_needed')
    def test_integrate_with_main_no_refresh_needed(self, mock_refresh):
        """トークンが有効な場合は更新されない"""
        # Arrange
        mock_refresh.return_value = None  # リフレッシュ不要
        
        # Act
        from token_manager import integrate_with_main
        result = integrate_with_main()
        
        # Assert
        self.assertEqual(result, 'test_access')
        mock_refresh.assert_called_once()
    
    @patch.dict(os.environ, {
        'FREEE_CLIENT_ID': 'test_id',
        'FREEE_CLIENT_SECRET': 'test_secret',
        'FREEE_REFRESH_TOKEN': 'test_refresh',
        'FREEE_ACCESS_TOKEN': 'old_access',
        'GITHUB_TOKEN': 'test_github',
        'GITHUB_REPOSITORY': 'test/repo'
    })
    @patch('token_manager.FreeeTokenManager.update_github_secret')
    @patch('token_manager.FreeeTokenManager.save_tokens_locally')
    @patch('token_manager.FreeeTokenManager.auto_refresh_if_needed')
    def test_integrate_with_main_with_refresh(self, mock_refresh, mock_save, mock_update):
        """トークンが無効な場合は更新される"""
        # Arrange
        new_tokens = {
            'access_token': 'new_access',
            'refresh_token': 'new_refresh',
            'expires_in': 86400
        }
        mock_refresh.return_value = new_tokens
        mock_update.return_value = True
        
        # Act
        from token_manager import integrate_with_main
        result = integrate_with_main()
        
        # Assert
        self.assertEqual(result, 'new_access')
        mock_refresh.assert_called_once()
        mock_save.assert_called_once_with(new_tokens)
        # GitHub Secretsが更新される
        self.assertEqual(mock_update.call_count, 2)  # access_tokenとrefresh_token


if __name__ == '__main__':
    unittest.main()