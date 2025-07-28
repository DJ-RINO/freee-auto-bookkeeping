"""
setup_freee_rules.py のテスト（TDD流）
まずテストを書いて、期待する動作を定義
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os
import sys
import json
from datetime import datetime, timedelta

# テスト対象をインポート
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from setup_freee_rules import (
    get_all_historical_deals,
    extract_keywords,
    generate_optimal_rules,
    calculate_confidence,
    analyze_wallet_patterns
)


class TestGetAllHistoricalDeals:
    """全期間の取引取得のテスト"""
    
    def test_過去10年分の取引を取得できること(self):
        """10年分のデータを正しく取得できるか"""
        # Arrange
        mock_client = Mock()
        mock_client.base_url = "https://api.freee.co.jp/api/1"
        mock_client.company_id = 123
        mock_client.headers = {"Authorization": "Bearer test"}
        
        # 各年のモックデータ
        mock_deals_by_year = {
            2025: [{"id": 1, "issue_date": "2025-01-15"}] * 50,
            2024: [{"id": 2, "issue_date": "2024-06-15"}] * 200,
            2023: [{"id": 3, "issue_date": "2023-06-15"}] * 180,
            2022: [{"id": 4, "issue_date": "2022-06-15"}] * 150,
            2021: [{"id": 5, "issue_date": "2021-06-15"}] * 100,
            2020: [],  # データなし
            2019: [],  # データなし
        }
        
        with patch('setup_freee_rules.get_deals_for_period') as mock_get_deals:
            def side_effect(client, start_date, end_date):
                year = start_date.year
                if year in mock_deals_by_year:
                    # その年の該当四半期のデータを返す
                    return mock_deals_by_year[year][:50]  # 四半期ごとに50件
                return []
            
            mock_get_deals.side_effect = side_effect
            
            # Act
            result = get_all_historical_deals(mock_client)
            
            # Assert
            # 2021-2025の5年分のデータが取得されること
            assert len(result) > 0
            # 2020年以降はデータがないので、そこで取得を停止すること
            assert mock_get_deals.call_count > 20  # 最低でも5年×4四半期
    
    def test_API制限エラーでリトライすること(self):
        """Rate limitエラーの場合、待機してリトライする"""
        # これは実装で確認
        pass


class TestExtractKeywords:
    """キーワード抽出のテスト"""
    
    def test_航空会社のキーワードを正しく抽出(self):
        """航空会社名から正しいキーワードを抽出"""
        # Arrange
        descriptions = [
            "Vデビット　JAPAN AIRLINES　1A208004",
            "日本航空チケット代",
            "JAL12345",
            "SOLASEED AIR",
            "ANA 羽田-福岡"
        ]
        
        # Act & Assert
        assert "JAL" in extract_keywords(descriptions[0])
        assert "JAL" in extract_keywords(descriptions[1])
        assert "JAL" in extract_keywords(descriptions[2])
        assert "SOLASEED" in extract_keywords(descriptions[3])
        assert "ANA" in extract_keywords(descriptions[4])
    
    def test_サブスクリプションサービスを正しく抽出(self):
        """IT系サービスのキーワードを抽出"""
        descriptions = [
            "ANTHROPIC PBC",
            "CURSOR AI POWERED IDE",
            "GITHUB.COM",
            "SLACK SUBSCRIPTION"
        ]
        
        for desc in descriptions:
            keywords = extract_keywords(desc)
            assert len(keywords) > 0
            assert any(kw in ["ANTHROPIC", "CURSOR", "GITHUB", "SLACK"] for kw in keywords)
    
    def test_振込パターンを正しく抽出(self):
        """振込の場合、振込元を抽出"""
        # Arrange
        descriptions = [
            "振込 サークル（カ",
            "振込 キクチヒデタカ",
            "振り込み タナカタロウ"
        ]
        
        # Act & Assert
        assert "振込_サークル（カ" in extract_keywords(descriptions[0])
        assert "振込_キクチヒデタカ" in extract_keywords(descriptions[1])
        # 振り込みも振込として扱う
        keywords = extract_keywords(descriptions[2])
        assert any("振込" in kw for kw in keywords)


class TestGenerateOptimalRules:
    """最適ルール生成のテスト"""
    
    def test_頻出パターンから高信頼度ルールを生成(self):
        """10回以上出現するパターンは高信頼度になる"""
        # Arrange
        pattern_stats = {
            "JAL": {
                "count": 15,
                "account_items": {607: 14, 831: 1},  # 旅費交通費が14回、雑費が1回
                "tax_codes": {21: 15},  # 全て課税仕入10%
                "amounts": [30000] * 15,
                "descriptions": ["JAL航空券"] * 15,
                "success_rate": 14/15  # 93.3%
            }
        }
        
        # Act
        rules = generate_optimal_rules(pattern_stats)
        
        # Assert
        assert len(rules) == 1
        assert rules[0]["keyword"] == "JAL"
        assert rules[0]["account_item_id"] == 607  # 最頻出の旅費交通費
        assert rules[0]["tax_code"] == 21
        assert rules[0]["confidence"] >= 0.9  # 高信頼度
        assert rules[0]["occurrence_count"] == 15
    
    def test_低頻度パターンは除外される(self):
        """1回しか出現しないパターンは除外"""
        # Arrange
        pattern_stats = {
            "RARE_COMPANY": {
                "count": 1,
                "account_items": {831: 1},
                "tax_codes": {21: 1},
                "amounts": [1000],
                "descriptions": ["レア会社"],
                "success_rate": 1.0
            }
        }
        
        # Act
        rules = generate_optimal_rules(pattern_stats)
        
        # Assert
        assert len(rules) == 0  # 2回未満は除外


class TestCalculateConfidence:
    """信頼度計算のテスト"""
    
    def test_高頻度高成功率は高信頼度(self):
        """出現回数が多く成功率も高い場合"""
        stats = {
            "count": 20,
            "success_rate": 0.95
        }
        
        confidence = calculate_confidence(stats)
        assert confidence >= 0.95  # ほぼ100%
    
    def test_低頻度でも成功率100なら中信頼度(self):
        """出現回数が少なくても成功率が高い場合"""
        stats = {
            "count": 3,
            "success_rate": 1.0
        }
        
        confidence = calculate_confidence(stats)
        assert 0.7 <= confidence < 0.95  # 中程度の信頼度


class TestAnalyzeWalletPatterns:
    """取引パターン分析のテスト"""
    
    def test_同じパターンの取引を正しく集計(self):
        """同じ会社の取引を正しくグループ化"""
        # Arrange
        mock_client = Mock()
        deals = [
            {
                "ref_number": "ANTHROPIC 月額料金",
                "details": [{
                    "account_item_id": 604,  # 通信費
                    "tax_code": 21,
                    "amount": 3000
                }]
            },
            {
                "ref_number": "ANTHROPIC PBC 利用料",
                "details": [{
                    "account_item_id": 604,  # 通信費
                    "tax_code": 21,
                    "amount": 3000
                }]
            },
            {
                "ref_number": "ANTHROPIC API",
                "details": [{
                    "account_item_id": 604,  # 通信費
                    "tax_code": 21,
                    "amount": 5000
                }]
            }
        ]
        
        # Act
        patterns = analyze_wallet_patterns(mock_client, deals)
        
        # Assert
        assert "ANTHROPIC" in patterns
        assert patterns["ANTHROPIC"]["count"] == 3
        assert patterns["ANTHROPIC"]["account_items"][604] == 3
        assert patterns["ANTHROPIC"]["success_rate"] == 1.0  # 全て同じ勘定科目


class TestIntegration:
    """統合テスト"""
    
    @patch('setup_freee_rules.get_all_historical_deals')
    @patch('setup_freee_rules.FreeeClient')
    def test_全体の処理フローが正しく動作すること(self, mock_client_class, mock_get_deals):
        """メイン処理が正しく動作する"""
        # Arrange
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # モックデータ
        mock_deals = [
            {
                "ref_number": "JAL航空券",
                "details": [{"account_item_id": 607, "tax_code": 21, "amount": 30000}]
            }
        ] * 10  # 10件の同じパターン
        
        mock_get_deals.return_value = mock_deals
        
        with patch.dict(os.environ, {
            'FREEE_ACCESS_TOKEN': 'test_token',
            'FREEE_COMPANY_ID': '123'
        }):
            # Act
            from setup_freee_rules import analyze_all_transactions
            with patch('setup_freee_rules.output_rules_to_csv'):
                with patch('setup_freee_rules.output_implementation_guide'):
                    rules, stats = analyze_all_transactions()
            
            # Assert
            assert len(rules) > 0
            assert rules[0]["keyword"] == "JAL"
            assert rules[0]["confidence"] >= 0.9


if __name__ == "__main__":
    # TDD流: まずテストを実行（失敗することを確認）
    pytest.main([__file__, "-v"])
    
    print("\n" + "="*50)
    print("テスト完了！")
    print("次は実際のデータで実行してみましょう")
    print("python src/setup_freee_rules.py")