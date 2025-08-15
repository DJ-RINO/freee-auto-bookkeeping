#!/usr/bin/env python3
"""
実行支援スクリプト - freee 自動経理システム用

このスクリプトは推奨実行コマンドと実行前のヘルスチェックを提供します。
CLAUDE.mdのガイドラインに従った正しい実行方法をサポートします。

主要機能:
1. 環境変数の自動読み込み
2. 実行前ヘルスチェック
3. 推奨コマンドのガイド
4. ドライランモードのサポート
5. エラー時の自動診断
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime
from typing import Dict, List, Optional
import json

# プロジェクトルートディレクトリの追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 内部モジュールのインポート
try:
    from src.environment_validator import validate_environment_full
    from src.system_health_checker import quick_health_check
    from src.token_manager import integrate_with_main
except ImportError as e:
    print(f"⚠️  内部モジュールのインポートに失敗: {e}")
    print("プロジェクトルートディレクトリから実行してください")
    sys.exit(1)


class EnhancedExecutionHelper:
    """実行支援機能を提供するクラス"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.execution_log = []
        
        # 推奨実行コマンド定義
        self.recommended_commands = {
            "health_check": {
                "description": "システム全体のヘルスチェック",
                "command": "python -m src.system_health_checker",
                "env_required": True,
                "dry_run_safe": True
            },
            "env_validation": {
                "description": "環境変数の完全性チェック",
                "command": "python -m src.environment_validator",
                "env_required": False,
                "dry_run_safe": True
            },
            "process_receipts_dry": {
                "description": "レシート処理（ドライラン）",
                "command": "python scripts/process_receipts_main.py",
                "env_vars": {"DRY_RUN": "true", "RECEIPT_LIMIT": "5"},
                "env_required": True,
                "dry_run_safe": True
            },
            "process_receipts_live": {
                "description": "レシート処理（本実行）",
                "command": "python scripts/process_receipts_main.py",
                "env_vars": {"DRY_RUN": "false"},
                "env_required": True,
                "dry_run_safe": False,
                "warning": "本実行モードです。事前にドライランでテストしてください。"
            },
            "token_refresh": {
                "description": "トークンの手動リフレッシュ",
                "command": "python -c \"from src.token_manager import integrate_with_main; print('新しいトークン:', integrate_with_main())\"",
                "env_required": True,
                "dry_run_safe": True
            },
            "test_api": {
                "description": "freee API接続テスト",
                "command": "python scripts/test_freee_api.py",
                "env_required": True,
                "dry_run_safe": True
            }
        }
    
    def load_env_file(self, env_file: str = ".env") -> bool:
        """環境変数ファイルの読み込み"""
        if not os.path.exists(env_file):
            print(f"⚠️  環境変数ファイルが見つかりません: {env_file}")
            return False
        
        print(f"📁 環境変数ファイルを読み込み中: {env_file}")
        
        try:
            # CLAUDLMDで推奨されている方法を使用
            result = subprocess.run(
                f"export $(cat {env_file} | grep -v '^#' | xargs) && env",
                shell=True,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # 環境変数を現在のプロセスに設定
                for line in result.stdout.strip().split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
                
                print(f"✅ 環境変数を正常に読み込みました")
                return True
            else:
                print(f"❌ 環境変数読み込み失敗: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ 環境変数読み込みエラー: {e}")
            return False
    
    def run_pre_execution_check(self) -> bool:
        """実行前の包括的チェック"""
        print("\n" + "="*60)
        print("🔍 実行前チェック開始")
        print("="*60)
        
        all_checks_passed = True
        
        # 1. 環境変数チェック
        print("\n1️⃣ 環境変数検証...")
        try:
            env_results = validate_environment_full()
            if env_results["status"] != "pass":
                print("❌ 環境変数検証失敗")
                all_checks_passed = False
            else:
                print("✅ 環境変数検証成功")
        except Exception as e:
            print(f"❌ 環境変数検証エラー: {e}")
            all_checks_passed = False
        
        # 2. システムヘルスチェック
        print("\n2️⃣ システムヘルスチェック...")
        try:
            is_healthy, health_message = quick_health_check()
            if not is_healthy:
                print(f"❌ システムヘルスチェック失敗: {health_message}")
                all_checks_passed = False
            else:
                print(f"✅ システムヘルスチェック成功: {health_message}")
        except Exception as e:
            print(f"❌ システムヘルスチェックエラー: {e}")
            all_checks_passed = False
        
        # 3. トークン有効性チェック
        print("\n3️⃣ トークン有効性チェック...")
        try:
            access_token = integrate_with_main()
            if access_token:
                print("✅ トークン取得成功")
            else:
                print("❌ トークン取得失敗")
                all_checks_passed = False
        except Exception as e:
            print(f"❌ トークンチェックエラー: {e}")
            all_checks_passed = False
        
        # 結果の表示
        print("\n" + "="*60)
        if all_checks_passed:
            print("🎉 実行前チェック: すべて正常")
            print("   システムは実行準備完了です")
        else:
            print("❌ 実行前チェック: 問題あり")
            print("   問題を修正してから再実行してください")
        print("="*60)
        
        return all_checks_passed
    
    def display_recommended_commands(self):
        """推奨コマンドの表示"""
        print("\n" + "="*60)
        print("📋 推奨実行コマンド一覧")
        print("="*60)
        
        for cmd_key, cmd_info in self.recommended_commands.items():
            print(f"\n🔹 {cmd_key}: {cmd_info['description']}")
            
            # 環境変数設定
            env_vars = cmd_info.get('env_vars', {})
            if env_vars:
                env_str = ' '.join([f"{k}={v}" for k, v in env_vars.items()])
                full_command = f"export {env_str} && {cmd_info['command']}"
            else:
                full_command = cmd_info['command']
            
            # CLAUDE.mdの推奨方法を適用
            if cmd_info['env_required']:
                full_command = f"export $(cat .env | grep -v '^#' | xargs) && {full_command}"
            
            print(f"   コマンド: {full_command}")
            
            # 警告表示
            if cmd_info.get('warning'):
                print(f"   ⚠️  警告: {cmd_info['warning']}")
            
            # 安全性表示
            safety = "ドライラン対応" if cmd_info.get('dry_run_safe') else "本実行のみ"
            print(f"   安全性: {safety}")
    
    def execute_command(self, command_key: str, confirm: bool = True) -> bool:
        """推奨コマンドの実行"""
        if command_key not in self.recommended_commands:
            print(f"❌ 不明なコマンド: {command_key}")
            return False
        
        cmd_info = self.recommended_commands[command_key]
        
        # 警告の表示と確認
        if cmd_info.get('warning') and confirm:
            print(f"\n⚠️  警告: {cmd_info['warning']}")
            response = input("続行しますか？ (y/N): ")
            if response.lower() not in ['y', 'yes']:
                print("実行をキャンセルしました")
                return False
        
        # 実行前チェック
        if cmd_info['env_required']:
            print("\n🔍 実行前チェックを実行中...")
            if not self.run_pre_execution_check():
                print("❌ 実行前チェックに失敗しました")
                if confirm:
                    response = input("チェックに失敗しましたが続行しますか？ (y/N): ")
                    if response.lower() not in ['y', 'yes']:
                        print("実行をキャンセルしました")
                        return False
        
        # コマンドの構築
        env_vars = cmd_info.get('env_vars', {})
        base_command = cmd_info['command']
        
        # 環境変数設定
        env_setup = ""
        if env_vars:
            env_str = ' '.join([f"{k}={v}" for k, v in env_vars.items()])
            env_setup = f"export {env_str} && "
        
        # CLAUDE.mdの推奨方法を適用
        if cmd_info['env_required']:
            full_command = f"export $(cat .env | grep -v '^#' | xargs) && {env_setup}{base_command}"
        else:
            full_command = f"{env_setup}{base_command}"
        
        # 実行
        print(f"\n🚀 実行中: {cmd_info['description']}")
        print(f"コマンド: {full_command}")
        print("-" * 60)
        
        try:
            start_time = datetime.now()
            result = subprocess.run(full_command, shell=True, text=True)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 実行ログに記録
            self.execution_log.append({
                "command": command_key,
                "description": cmd_info['description'],
                "start_time": start_time.isoformat(),
                "duration": duration,
                "exit_code": result.returncode,
                "success": result.returncode == 0
            })
            
            print("-" * 60)
            if result.returncode == 0:
                print(f"✅ 実行成功 (実行時間: {duration:.2f}秒)")
                return True
            else:
                print(f"❌ 実行失敗 (終了コード: {result.returncode})")
                return False
                
        except Exception as e:
            print(f"❌ 実行エラー: {e}")
            return False
    
    def save_execution_log(self, file_path: str = "execution_log.json"):
        """実行ログの保存"""
        log_data = {
            "session_start": self.start_time.isoformat(),
            "session_end": datetime.now().isoformat(),
            "executions": self.execution_log
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 実行ログを {file_path} に保存しました")
    
    def interactive_mode(self):
        """インタラクティブモード"""
        print("\n🎮 インタラクティブ実行モード")
        print("数字を入力してコマンドを選択してください (q で終了)")
        
        while True:
            # コマンド一覧表示
            print("\n" + "="*50)
            print("利用可能なコマンド:")
            cmd_list = list(self.recommended_commands.items())
            
            for i, (cmd_key, cmd_info) in enumerate(cmd_list, 1):
                safety = "🔒" if cmd_info.get('dry_run_safe') else "⚠️ "
                print(f"  {i}. {safety} {cmd_info['description']}")
            
            print(f"  0. 🔍 実行前チェックのみ")
            print(f"  q. 終了")
            
            # ユーザー入力
            choice = input("\n選択してください: ").strip()
            
            if choice.lower() == 'q':
                print("インタラクティブモードを終了します")
                break
            
            try:
                if choice == '0':
                    print("\n🔍 実行前チェックを実行中...")
                    self.run_pre_execution_check()
                else:
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(cmd_list):
                        cmd_key = cmd_list[choice_num - 1][0]
                        self.execute_command(cmd_key, confirm=True)
                    else:
                        print("❌ 無効な選択です")
            except ValueError:
                print("❌ 数字を入力してください")
            except KeyboardInterrupt:
                print("\n\n操作がキャンセルされました")
                break


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="freee自動経理システム実行支援スクリプト",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python scripts/enhanced_execution_helper.py --interactive
  python scripts/enhanced_execution_helper.py --list
  python scripts/enhanced_execution_helper.py --execute health_check
  python scripts/enhanced_execution_helper.py --check
        """
    )
    
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='インタラクティブモードで実行')
    parser.add_argument('--list', '-l', action='store_true',
                       help='利用可能なコマンド一覧を表示')
    parser.add_argument('--execute', '-e', type=str,
                       help='指定されたコマンドを実行')
    parser.add_argument('--check', '-c', action='store_true',
                       help='実行前チェックのみ実行')
    parser.add_argument('--env-file', type=str, default='.env',
                       help='環境変数ファイルのパス (デフォルト: .env)')
    parser.add_argument('--no-confirm', action='store_true',
                       help='確認なしで実行（注意して使用）')
    
    args = parser.parse_args()
    
    # 実行支援ヘルパーの初期化
    helper = EnhancedExecutionHelper()
    
    # 環境変数ファイルの読み込み
    if os.path.exists(args.env_file):
        helper.load_env_file(args.env_file)
    
    # コマンドラインオプションに応じた処理
    if args.interactive:
        helper.interactive_mode()
    elif args.list:
        helper.display_recommended_commands()
    elif args.execute:
        success = helper.execute_command(args.execute, confirm=not args.no_confirm)
        helper.save_execution_log()
        sys.exit(0 if success else 1)
    elif args.check:
        success = helper.run_pre_execution_check()
        sys.exit(0 if success else 1)
    else:
        # デフォルト: 使用方法を表示
        print("🚀 freee自動経理システム実行支援スクリプト")
        print("\n推奨使用方法:")
        print("1. python scripts/enhanced_execution_helper.py --check")
        print("2. python scripts/enhanced_execution_helper.py --interactive")
        print("\nまたは、直接コマンド実行:")
        print("3. python scripts/enhanced_execution_helper.py --execute process_receipts_dry")
        print("\nヘルプ: python scripts/enhanced_execution_helper.py --help")
        
        helper.display_recommended_commands()


if __name__ == "__main__":
    main()