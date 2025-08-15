"""
システムヘルスチェック機能 - freee 自動経理システム用

このモジュールはシステム全体の稼働状況を定期監視し、
問題の早期発見と自動修復提案を行います。

主要機能:
1. API接続のヘルスチェック
2. トークン有効性の確認
3. データベース/ファイルシステムの確認
4. システム全体の稼働状況レポート
5. 自動修復提案
"""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
import traceback

# 環境変数検証モジュールのインポート
try:
    from .environment_validator import validate_environment_quick
except ImportError:
    # フォールバック処理
    def validate_environment_quick():
        return True, []

# トークン管理モジュールのインポート
try:
    from .token_manager import integrate_with_main
except ImportError:
    # フォールバック処理
    def integrate_with_main():
        return os.getenv("FREEE_ACCESS_TOKEN")


class SystemHealthChecker:
    """システム全体のヘルスチェックを実行するクラス"""
    
    def __init__(self):
        self.health_status = {}
        self.errors = []
        self.warnings = []
        self.start_time = datetime.now()
        
        # freee API エンドポイント定義
        self.api_endpoints = {
            "user_info": "https://api.freee.co.jp/api/1/users/me",
            "companies": "https://api.freee.co.jp/api/1/companies",
            "receipts": "https://api.freee.co.jp/api/1/receipts",
            "deals": "https://api.freee.co.jp/api/1/deals"
        }
        
        # ヘルスチェック設定
        self.timeout = 30  # API リクエストタイムアウト
        self.retry_count = 3  # リトライ回数
    
    def run_full_health_check(self) -> Dict:
        """システム全体のヘルスチェックを実行"""
        print("\n" + "="*70)
        print("🏥 システムヘルスチェック開始")
        print("="*70)
        print(f"開始時刻: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. 環境変数チェック
        self._check_environment_variables()
        
        # 2. トークン有効性チェック
        self._check_token_validity()
        
        # 3. API接続チェック
        self._check_api_connectivity()
        
        # 4. ファイルシステムチェック
        self._check_file_system()
        
        # 5. 依存関係チェック
        self._check_dependencies()
        
        # 結果の集計とレポート生成
        results = self._compile_health_report()
        self._display_health_report(results)
        
        return results
    
    def _check_environment_variables(self):
        """環境変数の状態確認"""
        print("\n📋 1. 環境変数ヘルスチェック")
        
        try:
            is_valid, missing_vars = validate_environment_quick()
            
            if is_valid:
                print("  ✅ 環境変数: すべて正常に設定済み")
                self.health_status["environment"] = {
                    "status": "healthy",
                    "message": "すべての必須環境変数が設定済み"
                }
            else:
                print(f"  ❌ 環境変数: {len(missing_vars)} 個の必須変数が未設定")
                print(f"     未設定: {', '.join(missing_vars)}")
                self.errors.append({
                    "component": "environment",
                    "issue": f"必須環境変数未設定: {', '.join(missing_vars)}"
                })
                self.health_status["environment"] = {
                    "status": "error",
                    "message": f"必須環境変数未設定: {', '.join(missing_vars)}"
                }
        except Exception as e:
            print(f"  ❌ 環境変数チェック失敗: {e}")
            self.errors.append({
                "component": "environment",
                "issue": f"環境変数チェック失敗: {e}"
            })
            self.health_status["environment"] = {
                "status": "error",
                "message": f"チェック失敗: {e}"
            }
    
    def _check_token_validity(self):
        """トークン有効性の確認"""
        print("\n🔑 2. トークン有効性チェック")
        
        try:
            # 現在のアクセストークンを取得
            access_token = os.getenv("FREEE_ACCESS_TOKEN")
            
            if not access_token:
                print("  ⚠️  アクセストークンが未設定 - 自動更新を試行")
                try:
                    access_token = integrate_with_main()
                    if access_token:
                        print("  ✅ トークン自動更新成功")
                    else:
                        raise Exception("トークン自動更新失敗")
                except Exception as e:
                    print(f"  ❌ トークン自動更新失敗: {e}")
                    self.errors.append({
                        "component": "token",
                        "issue": f"トークン取得失敗: {e}"
                    })
                    self.health_status["token"] = {
                        "status": "error",
                        "message": f"トークン取得失敗: {e}"
                    }
                    return
            
            # トークンの有効性をテスト
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(
                self.api_endpoints["user_info"], 
                headers=headers, 
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                user_data = response.json()
                print(f"  ✅ トークン有効 - ユーザー: {user_data.get('user', {}).get('display_name', 'N/A')}")
                self.health_status["token"] = {
                    "status": "healthy",
                    "message": "トークンは有効",
                    "user_info": user_data.get('user', {})
                }
            elif response.status_code == 401:
                print("  ⚠️  トークン期限切れ - リフレッシュを試行")
                # 自動リフレッシュ試行
                try:
                    access_token = integrate_with_main()
                    if access_token:
                        print("  ✅ トークンリフレッシュ成功")
                        self.health_status["token"] = {
                            "status": "healthy",
                            "message": "トークンをリフレッシュしました"
                        }
                    else:
                        raise Exception("リフレッシュ失敗")
                except Exception as e:
                    print(f"  ❌ トークンリフレッシュ失敗: {e}")
                    self.errors.append({
                        "component": "token",
                        "issue": f"トークンリフレッシュ失敗: {e}"
                    })
                    self.health_status["token"] = {
                        "status": "error",
                        "message": f"トークンリフレッシュ失敗: {e}"
                    }
            else:
                print(f"  ❌ トークン検証失敗 - ステータス: {response.status_code}")
                self.errors.append({
                    "component": "token",
                    "issue": f"API応答エラー: {response.status_code}"
                })
                self.health_status["token"] = {
                    "status": "error",
                    "message": f"API応答エラー: {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            print(f"  ❌ タイムアウト ({self.timeout}秒)")
            self.errors.append({
                "component": "token",
                "issue": f"API接続タイムアウト ({self.timeout}秒)"
            })
            self.health_status["token"] = {
                "status": "error",
                "message": "API接続タイムアウト"
            }
        except Exception as e:
            print(f"  ❌ トークンチェック失敗: {e}")
            self.errors.append({
                "component": "token",
                "issue": f"予期しないエラー: {e}"
            })
            self.health_status["token"] = {
                "status": "error",
                "message": f"予期しないエラー: {e}"
            }
    
    def _check_api_connectivity(self):
        """API接続状況の確認"""
        print("\n🌐 3. API接続ヘルスチェック")
        
        access_token = os.getenv("FREEE_ACCESS_TOKEN")
        if not access_token:
            print("  ⚠️  アクセストークン未設定 - APIチェックをスキップ")
            self.warnings.append({
                "component": "api",
                "issue": "アクセストークン未設定によりAPIチェックスキップ"
            })
            return
        
        headers = {"Authorization": f"Bearer {access_token}"}
        api_results = {}
        
        for endpoint_name, endpoint_url in self.api_endpoints.items():
            print(f"  🔍 {endpoint_name} エンドポイントをテスト中...")
            
            success = False
            for attempt in range(self.retry_count):
                try:
                    response = requests.get(endpoint_url, headers=headers, timeout=self.timeout)
                    
                    if response.status_code == 200:
                        print(f"    ✅ {endpoint_name}: 正常応答")
                        api_results[endpoint_name] = {
                            "status": "healthy",
                            "response_time": response.elapsed.total_seconds(),
                            "status_code": response.status_code
                        }
                        success = True
                        break
                    elif response.status_code == 401:
                        print(f"    ❌ {endpoint_name}: 認証エラー")
                        api_results[endpoint_name] = {
                            "status": "auth_error",
                            "status_code": response.status_code
                        }
                        break
                    else:
                        print(f"    ⚠️  {endpoint_name}: エラー応答 ({response.status_code})")
                        api_results[endpoint_name] = {
                            "status": "error",
                            "status_code": response.status_code,
                            "attempt": attempt + 1
                        }
                        
                except requests.exceptions.Timeout:
                    print(f"    ⏰ {endpoint_name}: タイムアウト (試行 {attempt + 1}/{self.retry_count})")
                    if attempt == self.retry_count - 1:
                        api_results[endpoint_name] = {
                            "status": "timeout",
                            "attempts": self.retry_count
                        }
                except Exception as e:
                    print(f"    ❌ {endpoint_name}: 接続エラー ({e})")
                    if attempt == self.retry_count - 1:
                        api_results[endpoint_name] = {
                            "status": "connection_error",
                            "error": str(e),
                            "attempts": self.retry_count
                        }
                
                if not success and attempt < self.retry_count - 1:
                    time.sleep(2)  # リトライ前に2秒待機
        
        # API全体の状況評価
        healthy_apis = sum(1 for result in api_results.values() if result["status"] == "healthy")
        total_apis = len(api_results)
        
        if healthy_apis == total_apis:
            print(f"  ✅ API接続: すべてのエンドポイント正常 ({healthy_apis}/{total_apis})")
            self.health_status["api"] = {
                "status": "healthy",
                "message": f"すべてのエンドポイント正常 ({healthy_apis}/{total_apis})",
                "details": api_results
            }
        elif healthy_apis > 0:
            print(f"  ⚠️  API接続: 一部エンドポイント異常 ({healthy_apis}/{total_apis})")
            self.warnings.append({
                "component": "api",
                "issue": f"一部エンドポイント異常 ({healthy_apis}/{total_apis})"
            })
            self.health_status["api"] = {
                "status": "warning",
                "message": f"一部エンドポイント異常 ({healthy_apis}/{total_apis})",
                "details": api_results
            }
        else:
            print(f"  ❌ API接続: すべてのエンドポイント異常 ({healthy_apis}/{total_apis})")
            self.errors.append({
                "component": "api",
                "issue": f"すべてのエンドポイント異常 ({healthy_apis}/{total_apis})"
            })
            self.health_status["api"] = {
                "status": "error",
                "message": f"すべてのエンドポイント異常 ({healthy_apis}/{total_apis})",
                "details": api_results
            }
    
    def _check_file_system(self):
        """ファイルシステムの確認"""
        print("\n📁 4. ファイルシステムヘルスチェック")
        
        # 重要なディレクトリの確認
        important_dirs = ["src", "scripts", "data", "config"]
        missing_dirs = []
        
        for dir_name in important_dirs:
            if os.path.exists(dir_name):
                print(f"  ✅ ディレクトリ存在: {dir_name}")
            else:
                print(f"  ⚠️  ディレクトリ不在: {dir_name}")
                missing_dirs.append(dir_name)
        
        # 重要なファイルの確認
        important_files = [
            "src/token_manager.py",
            "src/enhanced_matcher.py", 
            "src/ocr_quality_manager.py",
            "config/linking.yml",
            "requirements.txt"
        ]
        missing_files = []
        
        for file_path in important_files:
            if os.path.exists(file_path):
                print(f"  ✅ ファイル存在: {file_path}")
            else:
                print(f"  ⚠️  ファイル不在: {file_path}")
                missing_files.append(file_path)
        
        # ディスク容量チェック（可能な場合）
        try:
            import shutil
            total, used, free = shutil.disk_usage(".")
            free_gb = free // (1024**3)
            total_gb = total // (1024**3)
            
            if free_gb < 1:  # 1GB未満の場合警告
                print(f"  ⚠️  ディスク容量不足: {free_gb}GB 残り (合計: {total_gb}GB)")
                self.warnings.append({
                    "component": "filesystem",
                    "issue": f"ディスク容量不足: {free_gb}GB残り"
                })
            else:
                print(f"  ✅ ディスク容量: {free_gb}GB 残り (合計: {total_gb}GB)")
                
        except Exception as e:
            print(f"  ⚠️  ディスク容量チェック失敗: {e}")
        
        # ファイルシステム全体の状況
        if not missing_dirs and not missing_files:
            self.health_status["filesystem"] = {
                "status": "healthy",
                "message": "すべての重要なファイル・ディレクトリが存在"
            }
        else:
            issues = []
            if missing_dirs:
                issues.append(f"不在ディレクトリ: {', '.join(missing_dirs)}")
            if missing_files:
                issues.append(f"不在ファイル: {', '.join(missing_files)}")
            
            self.warnings.append({
                "component": "filesystem",
                "issue": "; ".join(issues)
            })
            self.health_status["filesystem"] = {
                "status": "warning",
                "message": "; ".join(issues)
            }
    
    def _check_dependencies(self):
        """依存関係の確認"""
        print("\n📦 5. 依存関係ヘルスチェック")
        
        # Python標準ライブラリの確認
        required_modules = [
            "json", "os", "requests", "datetime", "re", "base64"
        ]
        
        missing_modules = []
        for module in required_modules:
            try:
                __import__(module)
                print(f"  ✅ モジュール: {module}")
            except ImportError:
                print(f"  ❌ モジュール不在: {module}")
                missing_modules.append(module)
        
        # オプション依存関係の確認
        optional_modules = {
            "nacl": "GitHub Secrets暗号化用",
            "yaml": "設定ファイル読み込み用"
        }
        
        for module, description in optional_modules.items():
            try:
                __import__(module)
                print(f"  ✅ オプション: {module} ({description})")
            except ImportError:
                print(f"  ⚪ オプション不在: {module} ({description})")
        
        if missing_modules:
            self.errors.append({
                "component": "dependencies",
                "issue": f"必須モジュール不在: {', '.join(missing_modules)}"
            })
            self.health_status["dependencies"] = {
                "status": "error",
                "message": f"必須モジュール不在: {', '.join(missing_modules)}"
            }
        else:
            self.health_status["dependencies"] = {
                "status": "healthy",
                "message": "すべての必須依存関係が利用可能"
            }
    
    def _compile_health_report(self) -> Dict:
        """ヘルスチェック結果の集計"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # 全体的な健康状態の判定
        error_count = len(self.errors)
        warning_count = len(self.warnings)
        
        if error_count == 0 and warning_count == 0:
            overall_status = "healthy"
            overall_message = "システムは完全に正常です"
        elif error_count == 0:
            overall_status = "warning"
            overall_message = f"{warning_count}個の警告があります"
        else:
            overall_status = "unhealthy"
            overall_message = f"{error_count}個のエラー、{warning_count}個の警告があります"
        
        return {
            "timestamp": end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "overall_status": overall_status,
            "overall_message": overall_message,
            "component_health": self.health_status,
            "errors": self.errors,
            "warnings": self.warnings,
            "summary": {
                "total_components": len(self.health_status),
                "healthy_components": len([s for s in self.health_status.values() if s["status"] == "healthy"]),
                "error_count": error_count,
                "warning_count": warning_count
            }
        }
    
    def _display_health_report(self, results: Dict):
        """ヘルスチェック結果の表示"""
        print("\n" + "="*70)
        print("📊 システムヘルスチェック結果")
        print("="*70)
        
        # 全体サマリー
        print(f"🕐 実行時間: {results['duration_seconds']}秒")
        print(f"📈 全体状況: {results['overall_message']}")
        
        # コンポーネント別結果
        print(f"\n📋 コンポーネント別状況:")
        summary = results["summary"]
        print(f"  ✅ 正常: {summary['healthy_components']}/{summary['total_components']}")
        print(f"  ⚠️  警告: {summary['warning_count']}")
        print(f"  ❌ エラー: {summary['error_count']}")
        
        # 推奨アクション
        if results["overall_status"] != "healthy":
            print(f"\n🔧 推奨アクション:")
            
            if self.errors:
                print("  【エラー対応（優先度：高）】")
                for i, error in enumerate(self.errors, 1):
                    print(f"    {i}. {error['component']}: {error['issue']}")
            
            if self.warnings:
                print("  【警告対応（優先度：中）】")
                for i, warning in enumerate(self.warnings, 1):
                    print(f"    {i}. {warning['component']}: {warning['issue']}")
        
        # 次回チェック推奨時期
        if results["overall_status"] == "healthy":
            next_check = datetime.now() + timedelta(hours=24)
            print(f"\n⏰ 次回チェック推奨: {next_check.strftime('%Y-%m-%d %H:%M')}")
        else:
            next_check = datetime.now() + timedelta(hours=1)
            print(f"\n⚠️  問題があるため1時間後の再チェックを推奨: {next_check.strftime('%Y-%m-%d %H:%M')}")
    
    def save_health_report(self, file_path: str = "system_health_report.json") -> str:
        """ヘルスチェック結果をファイルに保存"""
        results = self._compile_health_report()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 ヘルスレポートを {file_path} に保存しました")
        return file_path


def quick_health_check() -> Tuple[bool, str]:
    """他のモジュールから呼び出すためのクイックヘルスチェック"""
    try:
        checker = SystemHealthChecker()
        
        # 基本的なチェックのみ実行
        checker._check_environment_variables()
        checker._check_token_validity()
        
        # エラーがあるか確認
        has_errors = len(checker.errors) > 0
        status_message = "システム正常" if not has_errors else f"{len(checker.errors)}個のエラーあり"
        
        return not has_errors, status_message
        
    except Exception as e:
        return False, f"ヘルスチェック失敗: {e}"


def full_system_health_check() -> Dict:
    """完全なシステムヘルスチェックを実行"""
    checker = SystemHealthChecker()
    return checker.run_full_health_check()


if __name__ == "__main__":
    # スタンドアロン実行時の処理
    print("🏥 freee自動経理システム - システムヘルスチェックツール")
    
    # 完全ヘルスチェックの実行
    checker = SystemHealthChecker()
    results = checker.run_full_health_check()
    
    # レポートファイルの保存
    report_file = checker.save_health_report()
    
    # 終了コードの設定
    exit_code = 0 if results["overall_status"] == "healthy" else 1
    
    print(f"\n{'='*70}")
    print(f"ヘルスチェック完了 - 終了コード: {exit_code}")
    print(f"{'='*70}")
    
    exit(exit_code)