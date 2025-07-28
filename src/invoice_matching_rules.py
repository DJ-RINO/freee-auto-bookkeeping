"""
請求書消込の拡張ルール
同金額や日付パターンなど、より柔軟な消込を実現
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

class InvoiceMatchingRules:
    """請求書と入金のマッチングルール"""
    
    def __init__(self):
        # 会社名の表記ゆれ辞書
        self.company_variations = {
            "株式会社": ["(株)", "カブシキガイシャ", "ｶﾌﾞｼｷｶﾞｲｼｬ", "カ）", "（カ", "カ)"],
            "有限会社": ["(有)", "ユウゲンガイシャ", "ﾕｳｹﾞﾝｶﾞｲｼｬ", "ユ）", "（ユ", "ユ)"],
            "合同会社": ["(合)", "ゴウドウガイシャ", "ｺﾞｳﾄﾞｳｶﾞｲｼｬ", "ゴ）", "（ゴ", "ゴ)"],
            "一般社団法人": ["(一社)", "イッパンシャダンホウジン"],
            "公益社団法人": ["(公社)", "コウエキシャダンホウジン"],
            "特定非営利活動法人": ["NPO", "エヌピーオー"],
        }
        
        # 省略されやすい単語
        self.removable_words = [
            "様", "さま", "サマ", "御中", "殿",
            "より", "から", "カラ", "ヨリ",
            "振込", "振り込み", "フリコミ", "ﾌﾘｺﾐ",
            "入金", "ニュウキン", "ﾆｭｳｷﾝ",
            "支払", "シハライ", "ｼﾊﾗｲ",
            " ", "　", "\t", "\n",  # 空白文字
        ]
    
    def match_invoice_with_payment(self, payment: Dict, invoices: List[Dict]) -> List[Tuple[Dict, float]]:
        """
        入金と請求書をマッチング
        
        Args:
            payment: 入金明細
            invoices: 未消込請求書リスト
            
        Returns:
            [(請求書, マッチ度)] のリスト（マッチ度順）
        """
        matches = []
        payment_amount = payment.get("amount", 0)
        payment_description = payment.get("description", "")
        payment_date = self._parse_date(payment.get("date", ""))
        
        for invoice in invoices:
            match_score = 0.0
            reasons = []
            
            # 1. 金額の一致チェック（最重要）
            invoice_amount = invoice.get("total_amount", 0)
            if payment_amount == invoice_amount:
                match_score += 0.5
                reasons.append("金額完全一致")
            elif abs(payment_amount - invoice_amount) <= 10:  # 10円以内の誤差
                match_score += 0.3
                reasons.append("金額ほぼ一致（誤差10円以内）")
            
            # 2. 会社名のマッチング
            partner_name = invoice.get("partner_display_name", "")
            name_similarity = self._calculate_name_similarity(payment_description, partner_name)
            if name_similarity > 0.8:
                match_score += 0.3
                reasons.append(f"会社名一致（類似度{name_similarity:.0%}）")
            elif name_similarity > 0.5:
                match_score += 0.15
                reasons.append(f"会社名部分一致（類似度{name_similarity:.0%}）")
            
            # 3. 請求書番号のマッチング
            invoice_number = invoice.get("invoice_number", "")
            if invoice_number and invoice_number in payment_description:
                match_score += 0.2
                reasons.append("請求書番号一致")
            
            # 4. 日付の近さ
            invoice_date = self._parse_date(invoice.get("issue_date", ""))
            if payment_date and invoice_date:
                days_diff = abs((payment_date - invoice_date).days)
                if days_diff <= 7:  # 1週間以内
                    match_score += 0.1
                    reasons.append(f"日付が近い（{days_diff}日差）")
                elif days_diff <= 30:  # 1ヶ月以内
                    match_score += 0.05
                    reasons.append(f"日付が比較的近い（{days_diff}日差）")
            
            # 5. 支払い条件のパターン
            # 月末締め翌月末払いなどのパターンをチェック
            if self._check_payment_terms_pattern(invoice_date, payment_date):
                match_score += 0.1
                reasons.append("支払条件パターン一致")
            
            # 6. 金額の組み合わせチェック（複数請求書の合算）
            # この実装は後述のメソッドで
            
            if match_score > 0:
                matches.append((invoice, match_score, reasons))
        
        # マッチ度順にソート
        matches.sort(key=lambda x: x[1], reverse=True)
        
        # 複数請求書の合算もチェック
        combined_matches = self._find_combined_invoice_matches(payment_amount, invoices)
        matches.extend(combined_matches)
        
        return [(m[0], m[1]) for m in matches]
    
    def _normalize_company_name(self, name: str) -> str:
        """会社名を正規化"""
        normalized = name.upper()
        
        # 表記ゆれを統一
        for standard, variations in self.company_variations.items():
            for var in variations:
                normalized = normalized.replace(var.upper(), standard)
        
        # 不要な単語を削除
        for word in self.removable_words:
            normalized = normalized.replace(word.upper(), "")
        
        # 全角英数字を半角に
        normalized = self._zenkaku_to_hankaku(normalized)
        
        # 連続する空白を1つに
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _calculate_name_similarity(self, desc: str, company_name: str) -> float:
        """会社名の類似度を計算"""
        if not desc or not company_name:
            return 0.0
        
        # 正規化
        normalized_desc = self._normalize_company_name(desc)
        normalized_company = self._normalize_company_name(company_name)
        
        # 完全一致
        if normalized_company in normalized_desc:
            return 1.0
        
        # 部分一致（会社名の主要部分）
        # 株式会社などを除いた部分で比較
        core_company = re.sub(r'(株式会社|有限会社|合同会社)', '', normalized_company).strip()
        if core_company and core_company in normalized_desc:
            return 0.9
        
        # 単語分割して共通単語の割合を計算
        desc_words = set(re.findall(r'\w+', normalized_desc))
        company_words = set(re.findall(r'\w+', normalized_company))
        
        if not company_words:
            return 0.0
        
        common_words = desc_words & company_words
        similarity = len(common_words) / len(company_words)
        
        return similarity
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """日付文字列をパース"""
        if not date_str:
            return None
        
        try:
            # YYYY-MM-DD形式
            return datetime.strptime(date_str, "%Y-%m-%d")
        except:
            try:
                # YYYY/MM/DD形式
                return datetime.strptime(date_str, "%Y/%m/%d")
            except:
                return None
    
    def _check_payment_terms_pattern(self, invoice_date: Optional[datetime], 
                                    payment_date: Optional[datetime]) -> bool:
        """支払条件のパターンをチェック"""
        if not invoice_date or not payment_date:
            return False
        
        # よくある支払パターン
        patterns = [
            # 月末締め翌月末払い
            lambda i, p: (i.month == p.month - 1 or (i.month == 12 and p.month == 1)) and p.day >= 25,
            # 月末締め翌々月10日払い
            lambda i, p: (i.month == p.month - 2 or (i.month == 11 and p.month == 1) or (i.month == 12 and p.month == 2)) and 8 <= p.day <= 12,
            # 15日締め当月末払い
            lambda i, p: i.month == p.month and i.day <= 15 and p.day >= 25,
            # 請求書発行から30日後
            lambda i, p: 28 <= (p - i).days <= 32,
            # 請求書発行から60日後
            lambda i, p: 58 <= (p - i).days <= 62,
        ]
        
        return any(pattern(invoice_date, payment_date) for pattern in patterns)
    
    def _find_combined_invoice_matches(self, payment_amount: float, 
                                      invoices: List[Dict]) -> List[Tuple[List[Dict], float, List[str]]]:
        """複数請求書の合算でマッチするものを探す"""
        matches = []
        
        # 2-3枚の請求書の組み合わせをチェック
        for i in range(len(invoices)):
            for j in range(i + 1, len(invoices)):
                # 2枚の組み合わせ
                total = invoices[i].get("total_amount", 0) + invoices[j].get("total_amount", 0)
                if abs(total - payment_amount) <= 10:  # 10円以内の誤差
                    match_score = 0.8  # 金額一致で高スコア
                    reasons = [f"2件の請求書合計が一致（{invoices[i].get('invoice_number', 'No.不明')} + {invoices[j].get('invoice_number', 'No.不明')}）"]
                    matches.append(([invoices[i], invoices[j]], match_score, reasons))
                
                # 3枚の組み合わせ
                for k in range(j + 1, min(len(invoices), j + 5)):  # 計算量を抑えるため制限
                    total3 = total + invoices[k].get("total_amount", 0)
                    if abs(total3 - payment_amount) <= 10:
                        match_score = 0.75
                        reasons = [f"3件の請求書合計が一致"]
                        matches.append(([invoices[i], invoices[j], invoices[k]], match_score, reasons))
        
        return matches
    
    def _zenkaku_to_hankaku(self, text: str) -> str:
        """全角英数字を半角に変換"""
        # 全角→半角変換テーブル
        zen = "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
        han = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        
        trans_table = str.maketrans(zen, han)
        return text.translate(trans_table)
    
    def suggest_matching_rules(self, unmatched_payments: List[Dict], 
                              unmatched_invoices: List[Dict]) -> List[Dict]:
        """
        未消込の入金と請求書から、新しいマッチングルールを提案
        """
        suggestions = []
        
        # 金額グループごとに分析
        amount_groups = defaultdict(list)
        for payment in unmatched_payments:
            amount = payment.get("amount", 0)
            amount_groups[amount].append(payment)
        
        for amount, payments in amount_groups.items():
            # 同じ金額の請求書を探す
            matching_invoices = [inv for inv in unmatched_invoices 
                               if inv.get("total_amount", 0) == amount]
            
            if matching_invoices:
                # パターンを分析
                common_patterns = self._analyze_common_patterns(payments, matching_invoices)
                
                if common_patterns:
                    suggestion = {
                        "amount": amount,
                        "payment_count": len(payments),
                        "invoice_count": len(matching_invoices),
                        "patterns": common_patterns,
                        "confidence": min(len(payments) / 5.0, 1.0)  # 5件以上で信頼度MAX
                    }
                    suggestions.append(suggestion)
        
        return suggestions
    
    def _analyze_common_patterns(self, payments: List[Dict], 
                                invoices: List[Dict]) -> List[str]:
        """共通パターンを分析"""
        patterns = []
        
        # 日付パターンの分析
        payment_dates = [self._parse_date(p.get("date", "")) for p in payments if p.get("date")]
        invoice_dates = [self._parse_date(i.get("issue_date", "")) for i in invoices if i.get("issue_date")]
        
        if payment_dates and invoice_dates:
            # 平均的な支払日数を計算
            date_diffs = []
            for pd in payment_dates:
                for id in invoice_dates:
                    if pd and id and pd > id:
                        date_diffs.append((pd - id).days)
            
            if date_diffs:
                avg_days = sum(date_diffs) / len(date_diffs)
                if 25 <= avg_days <= 35:
                    patterns.append("月末締め翌月末払いパターン")
                elif 55 <= avg_days <= 65:
                    patterns.append("月末締め翌々月末払いパターン")
        
        # 会社名パターンの分析
        payment_descs = [p.get("description", "") for p in payments]
        invoice_partners = [i.get("partner_display_name", "") for i in invoices]
        
        # 共通する単語を抽出
        common_words = set()
        for desc in payment_descs:
            words = set(re.findall(r'\w{2,}', desc))  # 2文字以上の単語
            for partner in invoice_partners:
                partner_words = set(re.findall(r'\w{2,}', partner))
                common = words & partner_words
                common_words.update(common)
        
        if common_words:
            patterns.append(f"共通キーワード: {', '.join(list(common_words)[:3])}")
        
        return patterns


def test_matching():
    """マッチングルールのテスト"""
    matcher = InvoiceMatchingRules()
    
    # テスト用の入金データ
    payment = {
        "amount": 110000,
        "description": "振込 カ）サークル",
        "date": "2024-01-31"
    }
    
    # テスト用の請求書データ
    invoices = [
        {
            "total_amount": 110000,
            "partner_display_name": "株式会社サークル",
            "invoice_number": "INV-2024-001",
            "issue_date": "2024-01-15"
        },
        {
            "total_amount": 110000,
            "partner_display_name": "合同会社テスト",
            "invoice_number": "INV-2024-002",
            "issue_date": "2024-01-10"
        }
    ]
    
    # マッチング実行
    matches = matcher.match_invoice_with_payment(payment, invoices)
    
    print("マッチング結果:")
    for invoice, score in matches:
        print(f"  - {invoice.get('partner_display_name')}: スコア {score:.2f}")


if __name__ == "__main__":
    test_matching()