import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from collections import defaultdict

class TransactionLearningSystem:
    """取引の学習データを管理するシステム"""
    
    def __init__(self, data_dir: str = "./learning_data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.history_file = os.path.join(data_dir, "transaction_history.json")
        self.patterns_file = os.path.join(data_dir, "learned_patterns.json")
        self.feedback_file = os.path.join(data_dir, "user_feedback.json")
        
    def record_transaction(self, txn: Dict, analysis: Dict, result: Dict):
        """取引の処理結果を記録"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "transaction": txn,
            "ai_analysis": analysis,
            "result": result,
            "feedback": None  # 後でユーザーフィードバックを追加
        }
        
        # 履歴に追加
        history = self._load_json(self.history_file, [])
        history.append(record)
        self._save_json(self.history_file, history)
        
        # パターンを更新
        self._update_patterns(txn, analysis)
        
    def record_feedback(self, txn_id: str, feedback: Dict):
        """ユーザーフィードバックを記録"""
        feedback_record = {
            "timestamp": datetime.now().isoformat(),
            "txn_id": txn_id,
            "feedback": feedback
        }
        
        # フィードバック履歴に追加
        feedbacks = self._load_json(self.feedback_file, [])
        feedbacks.append(feedback_record)
        self._save_json(self.feedback_file, feedbacks)
        
        # 履歴も更新
        history = self._load_json(self.history_file, [])
        for record in history:
            if record["transaction"].get("id") == txn_id:
                record["feedback"] = feedback
                break
        self._save_json(self.history_file, history)
        
    def get_similar_transactions(self, txn: Dict, limit: int = 5) -> List[Dict]:
        """類似の過去取引を取得"""
        history = self._load_json(self.history_file, [])
        
        # 類似度を計算
        similarities = []
        for record in history:
            past_txn = record["transaction"]
            similarity = self._calculate_similarity(txn, past_txn)
            similarities.append((similarity, record))
        
        # 類似度でソート
        similarities.sort(key=lambda x: x[0], reverse=True)
        
        # 上位N件を返す
        return [record for _, record in similarities[:limit]]
    
    def get_patterns_for_partner(self, partner_name: str) -> Optional[Dict]:
        """取引先のパターンを取得"""
        patterns = self._load_json(self.patterns_file, {})
        return patterns.get("partners", {}).get(partner_name)
    
    def get_patterns_for_description(self, description: str) -> List[Dict]:
        """摘要に基づくパターンを取得"""
        patterns = self._load_json(self.patterns_file, {})
        keyword_patterns = patterns.get("keywords", {})
        
        matched_patterns = []
        for keyword, pattern in keyword_patterns.items():
            if keyword.lower() in description.lower():
                matched_patterns.append(pattern)
        
        return matched_patterns
    
    def generate_learning_context(self, txn: Dict) -> str:
        """Claude用の学習コンテキストを生成"""
        # 類似取引を取得
        similar_txns = self.get_similar_transactions(txn, limit=10)
        
        # 取引先パターンを取得
        partner_patterns = None
        if "partner_name" in txn:
            partner_patterns = self.get_patterns_for_partner(txn["partner_name"])
        
        # 摘要パターンを取得
        description_patterns = []
        if "description" in txn:
            description_patterns = self.get_patterns_for_description(txn["description"])
        
        # コンテキストを構築
        context = "過去の類似取引パターン:\n\n"
        
        # 成功した類似取引を追加
        successful_txns = [
            r for r in similar_txns 
            if r["result"]["status"] == "registered" and 
            (r["feedback"] is None or r["feedback"].get("correct", True))
        ]
        
        for i, record in enumerate(successful_txns[:5], 1):
            past_txn = record["transaction"]
            analysis = record["ai_analysis"]
            context += f"例{i}:\n"
            context += f"  摘要: {past_txn.get('description', '')}\n"
            context += f"  金額: {past_txn.get('amount', 0)}円\n"
            context += f"  勘定科目ID: {analysis['account_item_id']}\n"
            context += f"  税区分: {analysis['tax_code']}\n"
            context += f"  取引先: {analysis['partner_name']}\n\n"
        
        # 取引先固有のパターンを追加
        if partner_patterns:
            context += f"\n取引先「{txn.get('partner_name', '')}」の過去の傾向:\n"
            context += f"  よく使う勘定科目: {partner_patterns.get('common_account_items', [])}\n"
            context += f"  よく使う税区分: {partner_patterns.get('common_tax_codes', [])}\n"
        
        return context
    
    def _calculate_similarity(self, txn1: Dict, txn2: Dict) -> float:
        """2つの取引の類似度を計算"""
        score = 0.0
        
        # 取引先の一致
        if txn1.get("partner_name") == txn2.get("partner_name"):
            score += 0.4
        
        # 金額の類似性
        amount1 = abs(txn1.get("amount", 0))
        amount2 = abs(txn2.get("amount", 0))
        if amount1 > 0 and amount2 > 0:
            amount_ratio = min(amount1, amount2) / max(amount1, amount2)
            score += 0.2 * amount_ratio
        
        # 摘要の類似性
        desc1 = txn1.get("description", "").lower()
        desc2 = txn2.get("description", "").lower()
        if desc1 and desc2:
            # 簡易的な単語一致率
            words1 = set(desc1.split())
            words2 = set(desc2.split())
            if words1 and words2:
                jaccard = len(words1 & words2) / len(words1 | words2)
                score += 0.4 * jaccard
        
        return score
    
    def _update_patterns(self, txn: Dict, analysis: Dict):
        """パターンを更新"""
        patterns = self._load_json(self.patterns_file, {
            "partners": {},
            "keywords": {},
            "account_items": {}
        })
        
        # 取引先パターンを更新
        partner_name = analysis.get("partner_name")
        if partner_name:
            if partner_name not in patterns["partners"]:
                patterns["partners"][partner_name] = {
                    "common_account_items": defaultdict(int),
                    "common_tax_codes": defaultdict(int),
                    "transaction_count": 0
                }
            
            partner_pattern = patterns["partners"][partner_name]
            partner_pattern["common_account_items"][str(analysis["account_item_id"])] += 1
            partner_pattern["common_tax_codes"][str(analysis["tax_code"])] += 1
            partner_pattern["transaction_count"] += 1
        
        self._save_json(self.patterns_file, patterns)
    
    def _load_json(self, filename: str, default=None):
        """JSONファイルを読み込む"""
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        return default if default is not None else {}
    
    def _save_json(self, filename: str, data):
        """JSONファイルに保存"""
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def export_training_data(self, output_file: str = "training_data.jsonl"):
        """学習用データをエクスポート"""
        history = self._load_json(self.history_file, [])
        
        # 成功した取引のみを抽出
        training_data = []
        for record in history:
            if record["result"]["status"] == "registered":
                # フィードバックがない、または正しいと判定されたもの
                if record["feedback"] is None or record["feedback"].get("correct", True):
                    training_data.append({
                        "input": {
                            "description": record["transaction"].get("description", ""),
                            "amount": record["transaction"].get("amount", 0),
                            "date": record["transaction"].get("date", "")
                        },
                        "output": {
                            "account_item_id": record["ai_analysis"]["account_item_id"],
                            "tax_code": record["ai_analysis"]["tax_code"],
                            "partner_name": record["ai_analysis"]["partner_name"]
                        }
                    })
        
        # JSONL形式で保存
        with open(output_file, "w", encoding="utf-8") as f:
            for item in training_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        
        return len(training_data)