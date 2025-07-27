"""
会社固有の仕訳ルール定義
このファイルを編集して、自社の取引パターンに合わせたルールを追加してください
"""

# 取引先名から勘定科目を判定するルール
PARTNER_RULES = {
    # 交通費関連
    "JAPAN AIRLINES": {"account_item_id": 607, "tax_code": 21, "confidence": 1.0},
    "JAL": {"account_item_id": 607, "tax_code": 21, "confidence": 1.0},
    "日本航空": {"account_item_id": 607, "tax_code": 21, "confidence": 1.0},
    "SOLASEED": {"account_item_id": 607, "tax_code": 21, "confidence": 1.0},
    "ソラシドエア": {"account_item_id": 607, "tax_code": 21, "confidence": 1.0},
    "ANA": {"account_item_id": 607, "tax_code": 21, "confidence": 1.0},
    "全日空": {"account_item_id": 607, "tax_code": 21, "confidence": 1.0},
    
    # 通信費・サブスクリプション
    "ANTHROPIC": {"account_item_id": 604, "tax_code": 21, "confidence": 1.0},
    "CURSOR": {"account_item_id": 604, "tax_code": 21, "confidence": 1.0},
    "CURSOR AI": {"account_item_id": 604, "tax_code": 21, "confidence": 1.0},
    "ABEMATV": {"account_item_id": 604, "tax_code": 21, "confidence": 1.0},
    "ABEMA": {"account_item_id": 604, "tax_code": 21, "confidence": 1.0},
    "SLACK": {"account_item_id": 604, "tax_code": 21, "confidence": 1.0},
    "ZOOM": {"account_item_id": 604, "tax_code": 21, "confidence": 1.0},
    "GITHUB": {"account_item_id": 604, "tax_code": 21, "confidence": 1.0},
    "OPENAI": {"account_item_id": 604, "tax_code": 21, "confidence": 1.0},
    
    # 売上関連（振込元）
    "サークル": {"account_item_id": 101, "tax_code": 21, "confidence": 1.0},
    "キクチヒデタカ": {"account_item_id": 101, "tax_code": 21, "confidence": 0.95},
    
    # 飲食費
    "にくの十八屋": {"account_item_id": 815, "tax_code": 24, "confidence": 1.0},  # 会議費（軽減税率）
    
    # その他
    "SUPERULTRA": {"account_item_id": 831, "tax_code": 21, "confidence": 0.9},  # 雑費
}

# 金額による判定ルール
AMOUNT_RULES = [
    {
        "min_amount": 3000000,  # 300万円以上
        "max_amount": None,
        "type": "income",
        "account_item_id": 101,  # 売上高
        "tax_code": 21,
        "confidence_boost": 0.1
    },
    {
        "min_amount": 5000,
        "max_amount": 10000,
        "keywords": ["飲食", "レストラン", "カフェ"],
        "account_item_id": 815,  # 会議費
        "tax_code": 24,  # 軽減税率
        "confidence_boost": 0.05
    }
]

# キーワードによる判定ルール
KEYWORD_RULES = {
    "航空": {"account_item_id": 607, "tax_code": 21, "confidence_boost": 0.2},
    "AIR": {"account_item_id": 607, "tax_code": 21, "confidence_boost": 0.2},
    "AIRLINES": {"account_item_id": 607, "tax_code": 21, "confidence_boost": 0.2},
    "振込": {"type": "income", "confidence_boost": 0.1},
    "Vデビット": {"type": "expense", "confidence_boost": 0.05},
}


def apply_custom_rules(description: str, amount: int, claude_result: dict) -> dict:
    """
    カスタムルールを適用して仕訳を判定
    
    Args:
        description: 取引の摘要
        amount: 金額（マイナスは支出）
        claude_result: Claudeの推論結果
    
    Returns:
        修正された推論結果
    """
    result = claude_result.copy()
    description_upper = description.upper()
    
    # 1. 取引先名での完全一致チェック
    for partner, rule in PARTNER_RULES.items():
        if partner in description_upper:
            # ルールが完全一致した場合は上書き
            result.update(rule)
            result["matched_rule"] = f"partner:{partner}"
            return result
    
    # 2. キーワードルールでの信頼度調整
    confidence_boost = 0
    for keyword, rule in KEYWORD_RULES.items():
        if keyword in description_upper:
            if "account_item_id" in rule:
                result["account_item_id"] = rule["account_item_id"]
            if "tax_code" in rule:
                result["tax_code"] = rule["tax_code"]
            confidence_boost += rule.get("confidence_boost", 0)
    
    # 3. 金額ルールの適用
    for amount_rule in AMOUNT_RULES:
        min_amt = amount_rule.get("min_amount", 0)
        max_amt = amount_rule.get("max_amount", float('inf'))
        
        if min_amt <= abs(amount) <= max_amt:
            # タイプが一致するか確認
            if "type" in amount_rule:
                if (amount_rule["type"] == "income" and amount > 0) or \
                   (amount_rule["type"] == "expense" and amount < 0):
                    if "account_item_id" in amount_rule:
                        result["account_item_id"] = amount_rule["account_item_id"]
                    if "tax_code" in amount_rule:
                        result["tax_code"] = amount_rule["tax_code"]
                    confidence_boost += amount_rule.get("confidence_boost", 0)
    
    # 信頼度の調整
    result["confidence"] = min(result.get("confidence", 0) + confidence_boost, 1.0)
    
    return result


def get_rule_explanation(matched_rule: str) -> str:
    """マッチしたルールの説明を返す"""
    if matched_rule.startswith("partner:"):
        partner = matched_rule.replace("partner:", "")
        return f"取引先名 '{partner}' の固定ルールを適用"
    return "カスタムルールを適用"