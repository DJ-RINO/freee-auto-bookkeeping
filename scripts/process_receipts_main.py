#!/usr/bin/env python
"""
レシート紐付け専用のメインスクリプト
ファイルボックスのレシート/領収書を取引に紐付ける
"""

import os
import sys
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from token_manager import integrate_with_main
from state_store import init_db, write_audit
from config_loader import load_linking_config
from filebox_client import FileBoxClient
from ocr_models import ReceiptRecord
from linker import find_best_target, normalize_targets, ensure_not_duplicated_and_link, decide_action
from slack_notifier import SlackInteractiveNotifier, ReceiptNotification, send_batch_summary
from state_store import put_pending

def send_slack_notification(webhook_url: str, message: dict):
    """Slackに通知を送信"""
    if not webhook_url:
        return
    
    import requests
    try:
        response = requests.post(webhook_url, json=message)
        response.raise_for_status()
    except Exception as e:
        print(f"Slack通知エラー: {e}")

class FreeeClient:
    """freee APIクライアント（レシート処理用）"""
    
    def __init__(self, access_token: str, company_id: int):
        self.access_token = access_token
        self.company_id = company_id
        self.base_url = "https://api.freee.co.jp/api/1"
        
    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def get_wallet_transactions(self, limit: int = 100):
        """明細一覧を取得（未仕訳・仕訳済み両方）"""
        import requests
        from datetime import datetime, timedelta
        
        url = f"{self.base_url}/wallet_txns"
        # 直近180日間のデータを取得（証憑の日付範囲をカバー）
        now = datetime.now()
        start_date = (now - timedelta(days=180)).strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')
        
        params = {
            "company_id": self.company_id,
            "limit": limit,
            "walletable_type": "bank_account",
            "start_date": start_date,
            "end_date": end_date
        }
        
        print(f"  📊 wallet_txns API呼び出し: {start_date} 〜 {end_date}")
        print(f"    URL: {url}")
        print(f"    Params: {params}")
        response = requests.get(url, headers=self.get_headers(), params=params)
        if response.status_code == 200:
            data = response.json()
            result = data.get("wallet_txns", [])
            print(f"  ✅ wallet_txns取得成功: {len(result)}件")
            # レスポンスキーを確認
            if not result:
                print(f"    レスポンスキー: {list(data.keys())[:5]}")
                if "meta" in data:
                    print(f"    Meta情報: total_count={data['meta'].get('total_count', 0)}")
                print(f"    検索条件: 日付={start_date}~{end_date}, walletable_type=bank_account")
            return result
        else:
            print(f"  ⚠️ wallet_txns APIエラー: {response.status_code}")
            if response.text:
                print(f"    詳細: {response.text[:500]}")
        return []
    
    def get_deals(self, limit: int = 100):
        """登録済み取引を取得"""
        import requests
        from datetime import datetime, timedelta
        
        url = f"{self.base_url}/deals"
        # 直近180日間のデータを取得（証憑の日付範囲をカバー）
        now = datetime.now()
        start_date = (now - timedelta(days=180)).strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')
        
        params = {
            "company_id": self.company_id,
            "limit": limit,
            "start_issue_date": start_date,
            "end_issue_date": end_date
        }
        
        print(f"  📊 deals API呼び出し: {start_date} 〜 {end_date}")
        print(f"    URL: {url}")
        print(f"    Params: {params}")
        response = requests.get(url, headers=self.get_headers(), params=params)
        if response.status_code == 200:
            data = response.json()
            result = data.get("deals", [])
            print(f"  ✅ deals取得成功: {len(result)}件")
            # レスポンスキーを確認
            if not result:
                print(f"    レスポンスキー: {list(data.keys())[:5]}")
                if "meta" in data:
                    print(f"    Meta情報: total_count={data['meta'].get('total_count', 0)}")
                print(f"    検索条件: 日付={start_date}~{end_date}")
                # 空の場合のヒント
                print("    ヒント: freee管理画面でこの期間に取引があるか確認してください")
            return result
        else:
            print(f"  ⚠️ deals APIエラー: {response.status_code}")
            if response.text:
                print(f"    詳細: {response.text[:500]}")
        return []
    
    def attach_receipt_to_tx(self, tx_id: int, receipt_id: int):
        """レシートを明細に紐付け"""
        import requests
        url = f"{self.base_url}/wallet_txns/{tx_id}/receipts/{receipt_id}"
        params = {"company_id": self.company_id}
        
        response = requests.put(url, headers=self.get_headers(), params=params)
        return response.json() if response.status_code in (200, 201) else None
    
    def attach_receipt_to_deal(self, deal_id: int, receipt_id: int):
        """レシートを取引に紐付け"""
        # TODO: API実装待ち
        print(f"[INFO] 取引への紐付けAPI未実装: deal_id={deal_id}, receipt_id={receipt_id}")
        return None


def main():
    """メイン処理"""
    print("=== レシート紐付け処理を開始 ===")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 環境変数取得
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    receipt_limit = int(os.getenv("RECEIPT_LIMIT", "50"))
    target_type = os.getenv("TARGET_TYPE", "both")
    
    if dry_run:
        print("⚠️ DRY_RUNモード: 実際の紐付けは行いません")
    
    # データベース初期化
    init_db()
    
    # トークン管理（integrate_with_main関数を使用）
    try:
        access_token = integrate_with_main()
        print("✅ アクセストークンを取得しました")
    except Exception as e:
        print(f"❌ トークン取得エラー: {e}")
        return
    
    company_id = int(os.getenv("FREEE_COMPANY_ID"))
    
    # クライアント初期化
    print(f"\n🆔 会社ID: {company_id}")
    freee_client = FreeeClient(access_token, company_id)
    filebox_client = FileBoxClient(access_token, company_id)
    
    # 設定読み込み
    linking_cfg = load_linking_config()
    
    # Slack通知準備
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    slack_notifier = SlackInteractiveNotifier()
    assist_notifications = []
    
    # ファイルボックスからレシート取得
    print("\n📎 ファイルボックスからレシート取得中...")
    try:
        receipts = filebox_client.list_receipts(limit=receipt_limit)
        print(f"  {len(receipts)}件のレシートを取得")
    except Exception as e:
        print(f"❌ レシート取得エラー: {e}")
        return
    
    if not receipts:
        print("  処理対象のレシートはありません")
        if slack_url:
            send_slack_notification(slack_url, {
                "text": "📎 レシート紐付け: 処理対象なし",
                "blocks": [{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "ファイルボックスに未処理のレシートがありません"
                    }
                }]
            })
        return
    
    # 紐付け対象の取引を取得
    print("\n💳 紐付け対象の取引を取得中...")
    
    wallet_txns = []
    deals = []
    
    if target_type in ("both", "wallet_txn"):
        print("  🔍 wallet_txnsを取得中...")
        wallet_txns = freee_client.get_wallet_transactions(limit=100)
        print(f"  明細: {len(wallet_txns)}件")
    
    if target_type in ("both", "deal"):
        print("  🔍 dealsを取得中...")
        deals = freee_client.get_deals(limit=100)
        print(f"  取引: {len(deals)}件")
    
    # normalize_targetsでまとめて正規化
    targets = normalize_targets(wallet_txns, deals)
    
    if not targets:
        print("❌ 紐付け対象の取引がありません")
        print("  考えられる原因:")
        print("    1. 直近90日間に取引が登録されていない")
        print("    2. APIの権限が不足している")
        print("    3. 会社IDが正しく設定されていない")
        print(f"  環境変数: FREEE_COMPANY_ID={os.getenv('FREEE_COMPANY_ID', '未設定')}")
        print("  ヒント: freee管理画面で取引が登録されているか確認してください")
        # 取引がなくてもレシート情報を表示するため処理を続行
        # returnをコメントアウトして処理を続行
        # return
    
    # レシート処理
    print("\n🔄 レシート紐付け処理中...")
    results = {
        "auto": 0,
        "assist": 0,
        "manual": 0,
        "error": 0,
        "skipped": 0
    }
    
    for i, receipt in enumerate(receipts, 1):
        receipt_id = str(receipt.get("id"))
        print(f"\n[{i}/{len(receipts)}] レシートID: {receipt_id}")
        
        try:
            # レシートデータダウンロード
            data = filebox_client.download_receipt(int(receipt_id))
            file_sha1 = FileBoxClient.sha1_of_bytes(data)
            
            # レシート情報の取得
            file_name = receipt.get("file_name", "")
            memo = receipt.get("memo", "")
            description = receipt.get("description", "")
            created_at = receipt.get("created_at", "")
            receipt_amount = receipt.get("amount", 0)  # 証憑自体の金額
            user_name = receipt.get("user_name", "")
            receipt_status = receipt.get("status", "")
            
            # receipt_metadatumからOCR情報を取得
            receipt_metadatum = receipt.get("receipt_metadatum", {})
            ocr_vendor = ""
            if receipt_metadatum:
                # OCRで読み取った金額と店舗名を取得
                # freee APIは 'amount' フィールドに金額を格納している
                receipt_amount = receipt_metadatum.get("amount", receipt_amount) or receipt_metadatum.get("total_amount", receipt_amount) or receipt_amount
                # partner_name（取引先名）も店舗名の候補として追加
                ocr_vendor = receipt_metadatum.get("partner_name", "") or receipt_metadatum.get("payee_name", "") or receipt_metadatum.get("vendor", "") or receipt_metadatum.get("issuer", "")
                ocr_date = receipt_metadatum.get("issue_date", "") or receipt_metadatum.get("transaction_date", "")
                if i == 1:
                    print(f"  [デバッグ] receipt_metadatum キー: {list(receipt_metadatum.keys())}")
                    print(f"  [デバッグ] OCR amount={receipt_metadatum.get('amount')}, partner_name='{receipt_metadatum.get('partner_name')}'")
                    print(f"  [デバッグ] OCR issue_date='{receipt_metadatum.get('issue_date')}'")
            
            # qualified_invoiceからも情報を取得
            qualified_invoice = receipt.get("qualified_invoice", {})
            if qualified_invoice:
                if i == 1:
                    print(f"  [デバッグ] qualified_invoice キー: {list(qualified_invoice.keys())}")
                # qualified_invoiceからも金額と発行者名を取得
                qi_amount = qualified_invoice.get("amount", 0) or qualified_invoice.get("total_amount", 0)
                qi_vendor = qualified_invoice.get("issuer_name", "") or qualified_invoice.get("issuer", "")
                if qi_amount and not receipt_amount:
                    receipt_amount = qi_amount
                if qi_vendor and not ocr_vendor:
                    ocr_vendor = qi_vendor
                if i == 1:
                    print(f"  [デバッグ] QI amount={qi_amount}, issuer_name='{qi_vendor}'")
            
            # デバッグ: レシートデータを表示
            if i == 1:  # 最初の1件だけ詳細表示
                print(f"  [デバッグ] レシートデータキー: {list(receipt.keys())}")
                print(f"  [デバッグ] amount={receipt_amount}, file_name='{file_name}', memo='{memo}', description='{description}'")
                print(f"  [デバッグ] user_name='{user_name}', status='{receipt_status}'")
            
            # 金額の取得（優先順位： receipt_amount > ファイル名/メモから抽出）
            amount = receipt_amount
            
            # receipt_amountが0の場合、ファイル名やメモから金額を抽出
            if amount == 0:
                import re
                amount_patterns = [
                    r'([0-9,]+)円',
                    r'¥([0-9,]+)',
                    r'\$([0-9,]+)',
                    r'([0-9,]+)\s*JPY',
                ]
                
                search_text = f"{file_name} {memo} {description}"
                for pattern in amount_patterns:
                    match = re.search(pattern, search_text)
                    if match:
                        amount_str = match.group(1).replace(',', '')
                        try:
                            amount = int(amount_str)
                            break
                        except ValueError:
                            pass
            
            # 日付を取得（OCRの日付を優先）
            try:
                # OCRの日付を優先的に使用
                if 'ocr_date' in locals() and ocr_date:
                    date_obj = datetime.fromisoformat(ocr_date.replace('Z', '+00:00'))
                elif created_at:
                    date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    date_obj = datetime.now()
            except:
                date_obj = datetime.now()
            
            # vendor情報はOCR結果、ファイル名、メモ、説明、ユーザー名の優先順位で取得
            vendor = ocr_vendor or file_name or memo or description or user_name or ""
            
            # vendorが空の場合はレシートIDを使用
            if not vendor:
                vendor = f"レシート#{receipt_id}"
                
            # 金額が0円の場合の警告
            if amount == 0 and i == 1:
                print("  ⚠️ 金額情報が取得できませんでした。freee管理画面で証憑のOCR処理が完了しているか確認してください。")
            
            # レシートレコード作成
            rec = ReceiptRecord(
                receipt_id=receipt_id,
                file_hash=file_sha1,
                vendor=vendor,
                date=date_obj.date(),
                amount=amount
            )
            
            print(f"  🏪 店舗: {rec.vendor[:30] if rec.vendor else 'N/A'}")
            print(f"  💰 金額: ¥{rec.amount:,}")
            print(f"  📅 日付: {rec.date}")
            print(f"  🆔 ID: {receipt_id}, SHA1: {file_sha1[:8]}...")
            
            # targetsが空の場合はスキップ
            if not targets:
                print("  ⚠️ 取引がないためスキップ")
                results["manual"] += 1
                continue
            
            # 最適な取引を検索
            best = find_best_target(rec, targets, linking_cfg)
            
            if not best:
                print("  ⚠️ 適合する取引が見つかりません")
                results["manual"] += 1
                continue
            
            score = best.get("score", 0)
            ocr_quality_score = best.get("ocr_quality_score")
            action = decide_action(score, linking_cfg, ocr_quality_score)
            
            print(f"  マッチング: スコア {score}点 → {action}")
            if ocr_quality_score is not None:
                print(f"  OCR品質: {ocr_quality_score:.2f} ({'高品質' if ocr_quality_score >= 0.7 else '低品質'})")
            print(f"  対象取引: ID={best.get('id')}, 金額=¥{best.get('amount', 0):,}")
            
            if dry_run:
                print("  🔵 DRY_RUN: 紐付けをスキップ")
                results["skipped"] += 1
                continue
            
            if action == "AUTO":
                # 自動紐付け
                ensure_not_duplicated_and_link(
                    freee_client,
                    rec,
                    file_sha1,
                    best,
                    linking_cfg,
                    target_type=best.get("type", "wallet_txn"),
                    allow_delete=False
                )
                print("  ✅ 自動紐付け完了")
                results["auto"] += 1
                
            elif action == "ASSIST":
                # Slackインタラクティブ確認通知
                try:
                    # OCR品質スコアの設定
                    ocr_quality = best.get("ocr_quality_score", 0.8)
                    
                    # ReceiptNotificationを作成
                    notification = ReceiptNotification(
                        receipt_id=receipt_id,
                        vendor=rec.vendor,
                        amount=rec.amount,
                        date=rec.date.strftime('%Y-%m-%d'),
                        candidate_tx_id=str(best.get('id')),
                        candidate_description=best.get('description', 'No description'),
                        candidate_amount=best.get('amount', 0),
                        score=score,
                        reasons=best.get('reasons', []),
                        ocr_quality=ocr_quality
                    )
                    
                    # Slackインタラクティブメッセージ送信
                    message_ts = slack_notifier.send_receipt_confirmation(notification)
                    
                    if message_ts:
                        print("  📨 Slackインタラクティブ通知送信完了")
                        
                        # pending情報を保存
                        interaction_id = f"receipt_{notification.receipt_id}_{message_ts}"
                        put_pending(
                            interaction_id=interaction_id,
                            receipt_id=notification.receipt_id,
                            tx_id=notification.candidate_tx_id,
                            candidate_data={
                                "description": notification.candidate_description,
                                "amount": notification.candidate_amount,
                                "score": notification.score,
                                "reasons": notification.reasons
                            }
                        )
                        
                        assist_notifications.append(notification)
                        results["assist"] += 1
                    else:
                        print("  ⚠️ Slack通知失敗 - 手動対応に変更")
                        results["manual"] += 1
                        
                except Exception as e:
                    print(f"  ❌ Slack通知エラー: {e}")
                    results["manual"] += 1
                    
            else:
                results["manual"] += 1
                
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            results["error"] += 1
            write_audit("ERROR", "receipt_linking", "process", [receipt_id], 0, "failed", str(e))
    
    # 結果サマリー
    print("\n" + "=" * 50)
    print("📊 処理結果サマリー")
    print(f"  自動紐付け: {results['auto']}件")
    print(f"  確認待ち: {results['assist']}件")
    print(f"  手動対応: {results['manual']}件")
    print(f"  スキップ: {results['skipped']}件")
    print(f"  エラー: {results['error']}件")
    
    # 結果を保存
    result_file = f"receipt_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "execution_time": datetime.now().isoformat(),
            "dry_run": dry_run,
            "results": results,
            "processed_receipts": len(receipts)
        }, f, ensure_ascii=False, indent=2)
    
    # Slackサマリー通知
    if slack_url and not dry_run:
        send_batch_summary(results, len(receipts), slack_url)
    
    print("\n✅ レシート紐付け処理完了")


if __name__ == "__main__":
    main()