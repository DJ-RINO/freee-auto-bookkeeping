"""
token_manager.py の改善テスト（TDD和田流）
まず失敗するテストを書いて、実装の問題点を明らかにする
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import os
import json
from datetime import datetime, timedelta
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from token_manager import FreeeTokenManager, integrate_with_main


class TestTokenRefreshReliability:
    """トークンリフレッシュの確実性をテストする"""
    
    def test_新しいリフレッシュトークンが返されない場合でもエラーにならない(self):
        """freee APIが新しいリフレッシュトークンを返さない場合の対応"""
        # Arrange
        token_manager = FreeeTokenManager("id", "secret", "github")
        
        with patch('requests.post') as mock_post:
            # freee APIが refresh_token を含まないレスポンスを返す
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "new_access_token",
                # "refresh_token" が含まれていない！
                "expires_in": 86400,
                "token_type": "bearer"
            }
            mock_post.return_value = mock_response
            
            # Act
            result = token_manager.refresh_token("old_refresh")
            
            # Assert
            # 新しいリフレッシュトークンがなくても処理は成功すべき
            assert result["access_token"] == "new_access_token"
            # refresh_token は None または存在しない
            assert result.get("refresh_token") is None
    
    def test_リフレッシュトークンの更新が失敗しても処理は続行される(self):
        """GitHub Secrets更新失敗時でも処理が中断されない"""
        # Arrange
        with patch.dict(os.environ, {
            'FREEE_CLIENT_ID': 'test_id',
            'FREEE_CLIENT_SECRET': 'test_secret',
            'FREEE_REFRESH_TOKEN': 'old_refresh',
            'FREEE_ACCESS_TOKEN': 'old_access',
            'GITHUB_TOKEN': 'test_github',
            'GITHUB_REPOSITORY': 'test/repo'
        }):
            with patch('token_manager.FreeeTokenManager') as mock_class:
                mock_instance = Mock()
                mock_class.return_value = mock_instance
                
                # 新しいトークンを返す
                mock_instance.auto_refresh_if_needed.return_value = {
                    'access_token': 'new_access',
                    'refresh_token': 'new_refresh'
                }
                
                # GitHub Secrets更新が失敗
                mock_instance.update_github_secret.side_effect = Exception("GitHub API Error")
                
                # Act
                # エラーが発生してもクラッシュしない
                result = integrate_with_main()
                
                # Assert
                assert result == 'new_access'  # 新しいトークンは返される
    
    def test_リフレッシュトークンが空文字の場合の処理(self):
        """リフレッシュトークンが空文字でもエラーハンドリングされる"""
        # Arrange
        token_manager = FreeeTokenManager("id", "secret", "github")
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.json.return_value = {"error": "invalid_grant"}
            mock_response.raise_for_status.side_effect = Exception("401 Client Error")
            mock_post.return_value = mock_response
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                token_manager.refresh_token("")  # 空文字
            
            # エラーメッセージが適切
            assert "401 Client Error" in str(exc_info.value)


class TestTokenManagerErrorRecovery:
    """エラーからの回復能力をテスト"""
    
    @patch('builtins.print')
    def test_リフレッシュトークン更新失敗時に明確な警告が表示される(self, mock_print):
        """GitHub Secrets更新失敗時の警告メッセージ"""
        # Arrange
        with patch.dict(os.environ, {
            'FREEE_CLIENT_ID': 'test_id',
            'FREEE_CLIENT_SECRET': 'test_secret',
            'FREEE_REFRESH_TOKEN': 'old_refresh',
            'FREEE_ACCESS_TOKEN': 'old_access',
            'GITHUB_TOKEN': 'test_github',
            'GITHUB_REPOSITORY': 'test/repo'
        }):
            with patch('token_manager.FreeeTokenManager') as mock_class:
                mock_instance = Mock()
                mock_class.return_value = mock_instance
                
                # 新しいトークンを返す
                new_tokens = {
                    'access_token': 'new_access',
                    'refresh_token': 'critical_new_refresh'  # これが失われると次回失敗する
                }
                mock_instance.auto_refresh_if_needed.return_value = new_tokens
                
                # リフレッシュトークンの更新だけ失敗
                def update_side_effect(repo, name, value):
                    if name == "FREEE_REFRESH_TOKEN":
                        raise Exception("Permission denied")
                    return True
                
                mock_instance.update_github_secret.side_effect = update_side_effect
                
                # Act
                result = integrate_with_main()
                
                # Assert
                # 重要な警告が表示されること
                print_calls = [str(call) for call in mock_print.call_args_list]
                assert any("critical_new_refresh" in str(call) for call in print_calls)
                assert any("手動" in str(call) for call in print_calls)
    
    def test_ローカルバックアップファイルが常に作成される(self):
        """トークン更新時は必ずローカルバックアップが作成される"""
        # Arrange
        with patch.dict(os.environ, {
            'FREEE_CLIENT_ID': 'test_id',
            'FREEE_CLIENT_SECRET': 'test_secret',
            'FREEE_REFRESH_TOKEN': 'old_refresh',
            'FREEE_ACCESS_TOKEN': 'old_access',
            'GITHUB_TOKEN': '',  # GitHub tokenなし
            'GITHUB_REPOSITORY': 'test/repo'
        }):
            with patch('token_manager.FreeeTokenManager') as mock_class:
                mock_instance = Mock()
                mock_class.return_value = mock_instance
                
                new_tokens = {
                    'access_token': 'new_access',
                    'refresh_token': 'new_refresh',
                    'expires_at': '2025-07-28T10:00:00'
                }
                mock_instance.auto_refresh_if_needed.return_value = new_tokens
                
                # Act
                result = integrate_with_main()
                
                # Assert
                # save_tokens_locally が呼ばれることを確認
                mock_instance.save_tokens_locally.assert_called_once_with(new_tokens)


class TestTokenExpirationHandling:
    """トークン有効期限の扱いをテスト"""
    
    def test_expires_atが正しく計算される(self):
        """expires_at が現在時刻 + expires_in で計算される"""
        # Arrange
        token_manager = FreeeTokenManager("id", "secret", "github")
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "new_token",
                "refresh_token": "new_refresh",
                "expires_in": 86400  # 24時間
            }
            mock_post.return_value = mock_response
            
            # 現在時刻を固定
            fixed_now = datetime(2025, 7, 27, 10, 0, 0)
            with patch('token_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = fixed_now
                mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
                
                # Act
                result = token_manager.refresh_token("refresh")
                
                # Assert
                expected_expires = fixed_now + timedelta(seconds=86400)
                assert result["expires_at"] == expected_expires.isoformat()


class TestCriticalPathProtection:
    """クリティカルパスの保護をテスト"""
    
    def test_リフレッシュトークンは必ず更新を試みる(self):
        """新旧のリフレッシュトークンが同じでも更新を試みる"""
        # Arrange
        with patch.dict(os.environ, {
            'FREEE_CLIENT_ID': 'test_id',
            'FREEE_CLIENT_SECRET': 'test_secret',
            'FREEE_REFRESH_TOKEN': 'same_refresh',
            'FREEE_ACCESS_TOKEN': 'old_access',
            'GITHUB_TOKEN': 'test_github',
            'GITHUB_REPOSITORY': 'test/repo'
        }):
            with patch('token_manager.FreeeTokenManager') as mock_class:
                mock_instance = Mock()
                mock_class.return_value = mock_instance
                
                # 同じリフレッシュトークンが返される
                new_tokens = {
                    'access_token': 'new_access',
                    'refresh_token': 'same_refresh'  # 同じ値
                }
                mock_instance.auto_refresh_if_needed.return_value = new_tokens
                mock_instance.update_github_secret.return_value = True
                
                # Act
                integrate_with_main()
                
                # Assert
                # リフレッシュトークンも必ず更新される
                calls = mock_instance.update_github_secret.call_args_list
                refresh_token_calls = [c for c in calls if c[0][1] == 'FREEE_REFRESH_TOKEN']
                assert len(refresh_token_calls) == 1
                assert refresh_token_calls[0][0][2] == 'same_refresh'
    
    def test_PAT_TOKENが優先的に使用される(self):
        """PAT_TOKENが設定されている場合は優先される"""
        # Arrange
        with patch.dict(os.environ, {
            'FREEE_CLIENT_ID': 'test_id',
            'FREEE_CLIENT_SECRET': 'test_secret',
            'FREEE_REFRESH_TOKEN': 'test_refresh',
            'FREEE_ACCESS_TOKEN': 'test_access',
            'GITHUB_TOKEN': 'default_github_token',
            'PAT_TOKEN': 'personal_access_token',  # PATが設定されている
            'GITHUB_REPOSITORY': 'test/repo'
        }):
            with patch('token_manager.FreeeTokenManager') as mock_class:
                # Act
                integrate_with_main()
                
                # Assert
                # PAT_TOKENが使用されることを確認
                mock_class.assert_called_once()
                args = mock_class.call_args[0]
                assert args[2] == 'personal_access_token'  # GITHUB_TOKENではなくPAT_TOKEN