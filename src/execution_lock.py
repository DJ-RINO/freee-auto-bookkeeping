#!/usr/bin/env python
"""
実行ロック管理システム
重複実行の防止とプロセス管理を行う
"""

import json
import os
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

class ExecutionLock:
    """実行ロック管理クラス"""
    
    def __init__(self, lock_name: str, timeout: int = 3600):
        """
        Args:
            lock_name: ロック名
            timeout: ロックのタイムアウト時間（秒）
        """
        self.lock_name = lock_name
        self.timeout = timeout
        self.lock_file = f".{lock_name}_lock.json"
        
    def acquire_lock(self, process_id: str, metadata: Dict[str, Any]) -> bool:
        """ロックを取得する
        
        Args:
            process_id: プロセスID
            metadata: メタデータ
            
        Returns:
            bool: ロック取得成功時True
        """
        # 既存のロックを確認
        existing_lock = self._load_lock()
        
        if existing_lock:
            # タイムアウトチェック
            lock_time = datetime.fromisoformat(existing_lock.get('timestamp', ''))
            if datetime.now() - lock_time < timedelta(seconds=self.timeout):
                # まだ有効なロック
                return False
            else:
                # タイムアウトしたロックは削除
                print(f"⏰ ロックがタイムアウトしました: {existing_lock.get('process_id')}")
                self._remove_lock()
        
        # 新しいロックを作成
        lock_data = {
            'process_id': process_id,
            'timestamp': datetime.now().isoformat(),
            'timeout': self.timeout,
            'metadata': metadata
        }
        
        self._save_lock(lock_data)
        print(f"🔒 ロックを取得しました: {process_id}")
        return True
    
    def release_lock(self, process_id: str) -> bool:
        """ロックを解除する
        
        Args:
            process_id: プロセスID
            
        Returns:
            bool: ロック解除成功時True
        """
        existing_lock = self._load_lock()
        
        if not existing_lock:
            print(f"⚠️ ロックが存在しません: {process_id}")
            return False
        
        if existing_lock.get('process_id') != process_id:
            print(f"❌ ロックの所有者が異なります: {process_id}")
            return False
        
        self._remove_lock()
        print(f"🔓 ロックを解除しました: {process_id}")
        return True
    
    def get_lock_info(self) -> Optional[Dict[str, Any]]:
        """現在のロック情報を取得"""
        return self._load_lock()
    
    def _load_lock(self) -> Optional[Dict[str, Any]]:
        """ロックファイルを読み込み"""
        try:
            if os.path.exists(self.lock_file):
                with open(self.lock_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return None
    
    def _save_lock(self, lock_data: Dict[str, Any]):
        """ロックファイルを保存"""
        with open(self.lock_file, 'w', encoding='utf-8') as f:
            json.dump(lock_data, f, ensure_ascii=False, indent=2)
    
    def _remove_lock(self):
        """ロックファイルを削除"""
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except FileNotFoundError:
            pass


class NotificationDeduplicator:
    """通知重複防止クラス"""
    
    def __init__(self, cache_duration: int = 300):
        """
        Args:
            cache_duration: キャッシュ有効時間（秒）
        """
        self.cache_duration = cache_duration
        self.cache_file = ".notification_cache.json"
    
    def should_send_notification(self, notifications: List[Any]) -> tuple[bool, str]:
        """通知を送信すべきかチェック
        
        Args:
            notifications: 通知リスト
            
        Returns:
            tuple: (送信すべきか, バッチハッシュ)
        """
        # 通知内容からハッシュを生成
        batch_hash = self._generate_batch_hash(notifications)
        
        # キャッシュを確認
        cache = self._load_cache()
        
        if batch_hash in cache:
            cache_time = datetime.fromisoformat(cache[batch_hash]['timestamp'])
            if datetime.now() - cache_time < timedelta(seconds=self.cache_duration):
                return False, batch_hash
        
        return True, batch_hash
    
    def record_notification_sent(self, notifications: List[Any], batch_hash: str):
        """通知送信を記録
        
        Args:
            notifications: 通知リスト
            batch_hash: バッチハッシュ
        """
        cache = self._load_cache()
        
        cache[batch_hash] = {
            'timestamp': datetime.now().isoformat(),
            'count': len(notifications)
        }
        
        # 古いキャッシュを削除
        self._cleanup_cache(cache)
        
        self._save_cache(cache)
    
    def _generate_batch_hash(self, notifications: List[Any]) -> str:
        """通知リストからハッシュを生成"""
        # 通知の内容を文字列化してハッシュ化
        content = ""
        for notification in notifications:
            if hasattr(notification, 'receipt_id'):
                content += f"{notification.receipt_id}_{notification.vendor}_{notification.amount}"
            else:
                content += str(notification)
        
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
    
    def _load_cache(self) -> Dict[str, Any]:
        """キャッシュファイルを読み込み"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return {}
    
    def _save_cache(self, cache: Dict[str, Any]):
        """キャッシュファイルを保存"""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    
    def _cleanup_cache(self, cache: Dict[str, Any]):
        """古いキャッシュエントリを削除"""
        cutoff_time = datetime.now() - timedelta(seconds=self.cache_duration)
        
        to_remove = []
        for key, value in cache.items():
            try:
                cache_time = datetime.fromisoformat(value['timestamp'])
                if cache_time < cutoff_time:
                    to_remove.append(key)
            except (KeyError, ValueError):
                to_remove.append(key)
        
        for key in to_remove:
            del cache[key]