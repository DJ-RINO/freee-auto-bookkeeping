"""
環境変数検証システム - freee 自動経理システム用

このモジュールはシステム起動時の環境変数完全性チェックと
自動修復提案機能を提供します。

主要機能:
1. 必須環境変数の存在確認
2. 値の妥当性検証
3. 詳細な設定状況レポート
4. 自動修復提案
"""

import os
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json


class EnvironmentValidator:
    """環境変数の完全性チェックと検証を行うクラス"""
    
    # 必須環境変数の定義
    REQUIRED_VARS = {
        "FREEE_CLIENT_ID": {
            "description": "freee OAuth Client ID",
            "pattern": r"^[a-f0-9]{64}$",
            "example": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        },
        "FREEE_CLIENT_SECRET": {
            "description": "freee OAuth Client Secret",
            "pattern": r"^[a-f0-9]{64}$",
            "example": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        },
        "FREEE_REFRESH_TOKEN": {
            "description": "freee OAuth Refresh Token",
            "pattern": r"^[A-Za-z0-9_-]{40,}$",
            "example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        },
        "FREEE_COMPANY_ID": {
            "description": "freee Company ID",
            "pattern": r"^\d+$",
            "example": "1234567"
        }
    }
    
    # オプション環境変数
    OPTIONAL_VARS = {
        "FREEE_ACCESS_TOKEN": {
            "description": "freee OAuth Access Token (自動更新されます)",
            "pattern": r"^[A-Za-z0-9_-]{40,}$"
        },
        "PAT_TOKEN": {
            "description": "GitHub Personal Access Token (GitHub Secrets自動更新用)",
            "pattern": r"^(ghp_|github_pat_)[A-Za-z0-9_]{20,}$"
        },
        "GITHUB_TOKEN": {
            "description": "GitHub Token (Actions環境で自動設定)",
            "pattern": r"^(ghp_|ghs_)[A-Za-z0-9_]{20,}$"
        },
        "SLACK_BOT_TOKEN": {
            "description": "Slack Bot Token (通知機能用)",
            "pattern": r"^xoxb-[0-9]+-[0-9]+-[A-Za-z0-9]+$"
        },
        "DRY_RUN": {
            "description": "ドライランモード (true/false)",
            "pattern": r"^(true|false|1|0)$"
        },
        "RECEIPT_LIMIT": {
            "description": "処理レシート件数制限",
            "pattern": r"^\d+$"
        }
    }
    
    def __init__(self):
        self.validation_results = {}
        self.missing_vars = []
        self.invalid_vars = []
        self.warnings = []
        
    def validate_all(self) -> Dict:
        """全環境変数の検証を実行"""
        print("\n" + "="*60)
        print("🔍 環境変数完全性チェック開始")
        print("="*60)
        
        # 必須変数の検証
        self._validate_required_vars()
        
        # オプション変数の検証
        self._validate_optional_vars()
        
        # 結果の集計
        results = self._compile_results()
        
        # レポートの表示
        self._display_report(results)
        
        return results
    
    def _validate_required_vars(self):
        """必須環境変数の検証"""
        print("\n📋 必須環境変数の確認:")
        
        for var_name, config in self.REQUIRED_VARS.items():
            value = os.getenv(var_name)
            
            if not value:
                self.missing_vars.append(var_name)
                print(f"  ❌ {var_name}: 未設定")
                continue
            
            # パターンマッチング検証
            if not re.match(config["pattern"], value):
                self.invalid_vars.append({
                    "name": var_name,
                    "issue": "フォーマット不正",
                    "expected": config["example"]
                })
                print(f"  ⚠️  {var_name}: 設定済み (⚠️フォーマット検証失敗)")
            else:
                print(f"  ✅ {var_name}: 設定済み・検証OK")
            
            # 値の詳細情報
            self.validation_results[var_name] = {
                "status": "ok" if value and re.match(config["pattern"], value) else "invalid",
                "length": len(value) if value else 0,
                "description": config["description"]
            }
    
    def _validate_optional_vars(self):
        """オプション環境変数の検証"""
        print("\n🔧 オプション環境変数の確認:")
        
        for var_name, config in self.OPTIONAL_VARS.items():
            value = os.getenv(var_name)
            
            if not value:
                print(f"  ⚪ {var_name}: 未設定 (オプション)")
                self.validation_results[var_name] = {
                    "status": "optional_missing",
                    "description": config["description"]
                }
                continue
            
            # パターンマッチング検証
            if not re.match(config["pattern"], value):
                self.warnings.append({
                    "name": var_name,
                    "issue": "フォーマット警告",
                    "description": config["description"]
                })
                print(f"  ⚠️  {var_name}: 設定済み (⚠️フォーマット警告)")
            else:
                print(f"  ✅ {var_name}: 設定済み・検証OK")
            
            self.validation_results[var_name] = {
                "status": "ok" if re.match(config["pattern"], value) else "warning",
                "length": len(value) if value else 0,
                "description": config["description"]
            }
    
    def _compile_results(self) -> Dict:
        """検証結果の集計"""
        return {
            "timestamp": datetime.now().isoformat(),
            "status": "pass" if not self.missing_vars and not self.invalid_vars else "fail",
            "missing_required": self.missing_vars,
            "invalid_format": self.invalid_vars,
            "warnings": self.warnings,
            "details": self.validation_results,
            "summary": {
                "required_ok": len([v for v in self.REQUIRED_VARS.keys() 
                                  if self.validation_results.get(v, {}).get("status") == "ok"]),
                "required_total": len(self.REQUIRED_VARS),
                "optional_set": len([v for v in self.OPTIONAL_VARS.keys() 
                                   if self.validation_results.get(v, {}).get("status") in ["ok", "warning"]])
            }
        }
    
    def _display_report(self, results: Dict):
        """検証結果レポートの表示"""
        print("\n" + "="*60)
        print("📊 検証結果サマリー")
        print("="*60)
        
        summary = results["summary"]
        print(f"✅ 必須変数: {summary['required_ok']}/{summary['required_total']} 正常")
        print(f"🔧 オプション変数: {summary['optional_set']} 設定済み")
        
        if results["status"] == "pass":
            print("\n🎉 環境変数検証: 合格")
            print("   システムは正常に動作する準備ができています")
        else:
            print("\n❌ 環境変数検証: 失敗")
            self._display_remediation_guide()
    
    def _display_remediation_guide(self):
        """修復ガイドの表示"""
        print("\n" + "="*60)
        print("🔧 修復ガイド")
        print("="*60)
        
        if self.missing_vars:
            print("\n❌ 未設定の必須環境変数:")
            for var in self.missing_vars:
                config = self.REQUIRED_VARS[var]
                print(f"\n  {var}:")
                print(f"    説明: {config['description']}")
                print(f"    例: {config['example']}")
                print(f"    設定方法: export {var}=\"実際の値\"")
        
        if self.invalid_vars:
            print("\n⚠️  フォーマット不正の環境変数:")
            for var_info in self.invalid_vars:
                print(f"\n  {var_info['name']}:")
                print(f"    問題: {var_info['issue']}")
                print(f"    期待値例: {var_info['expected']}")
        
        print("\n💡 推奨修復手順:")
        print("1. freee Developersで新しいOAuthアプリケーションを作成")
        print("2. Client IDとClient Secretを取得")
        print("3. 認証フローを実行してRefresh Tokenを取得")
        print("4. GitHub SecretsまたはローカルのE.env fileに設定")
        print("5. 再度このスクリプトを実行して検証")
    
    def save_report(self, file_path: str = "environment_validation_report.json"):
        """検証結果をJSONファイルに保存"""
        results = self._compile_results()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 検証レポートを {file_path} に保存しました")
        return file_path
    
    def check_basic_requirements(self) -> bool:
        """基本要件のクイックチェック（他のモジュールから呼び出し用）"""
        missing = [var for var in self.REQUIRED_VARS.keys() if not os.getenv(var)]
        
        if missing:
            raise EnvironmentError(
                f"必須環境変数が未設定です: {', '.join(missing)}\n"
                f"詳細な修復ガイドは environment_validator.py を実行してください"
            )
        
        return True


def validate_environment_quick() -> Tuple[bool, List[str]]:
    """他のモジュールから呼び出すためのクイック検証関数"""
    validator = EnvironmentValidator()
    
    missing = []
    for var_name in validator.REQUIRED_VARS.keys():
        if not os.getenv(var_name):
            missing.append(var_name)
    
    return len(missing) == 0, missing


def validate_environment_full() -> Dict:
    """完全な環境変数検証を実行"""
    validator = EnvironmentValidator()
    return validator.validate_all()


if __name__ == "__main__":
    # スタンドアロン実行時の処理
    print("🚀 freee自動経理システム - 環境変数検証ツール")
    
    # 完全検証の実行
    validator = EnvironmentValidator()
    results = validator.validate_all()
    
    # レポートファイルの保存
    report_file = validator.save_report()
    
    # 終了コードの設定
    exit_code = 0 if results["status"] == "pass" else 1
    
    print(f"\n{'='*60}")
    print(f"検証完了 - 終了コード: {exit_code}")
    print(f"{'='*60}")
    
    exit(exit_code)