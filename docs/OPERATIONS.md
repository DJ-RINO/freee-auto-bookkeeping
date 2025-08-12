## 運用手順（レシートOCR→ひも付け ASSIST/AUTO/MANUAL）

### 前提
- GitHub Secrets に以下を設定
  - `FREEE_CLIENT_ID`, `FREEE_CLIENT_SECRET`, `FREEE_REFRESH_TOKEN`
  - `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`, `SLACK_SIGNING_SECRET`
  - `GITHUB_TOKEN`, `TZ=Asia/Tokyo`
- `config/linking.yml` でしきい値・許容を管理

### フロー概要
1. OCR結果を `ReceiptRecord` に整形
2. `matcher.match_candidates()` が候補Top3を生成
3. スコアに応じて
   - AUTO: 即ひも付け
   - ASSIST: Slackに候補とボタンを通知
   - MANUAL: 保留
4. Slackの操作は Webhook 経由で `repository_dispatch(type: apply-receipt-decision)` を起動
5. `apply-decision.yml` が freee へ反映し、結果を返信
6. ファイルボックスの証憑は、未仕訳(wallet_txn) または 登録済み取引(deal) の両方を候補に照合し、自動ひも付け（DRY_RUN推奨）

### 冪等・監査
- `receipt_hash = sha1(vendor_norm|date|amount|file_digest)` を保存し、同一はスキップ
- `file_sha1` ごとの出現履歴も保存（同一ファイルの多重登録を検出）
- `state_store.audit_log` に INFO/ERROR/DEBUG を記録

### レート制限
- 429/5xx は指数バックオフ（1,2,4,8,16s, 最大5回）で再試行

### Webhookのデプロイ（Vercel採用時）
- 本リポジトリをVercelにImport → Deploy
- 環境変数（Project Settings → Environment Variables）に以下を登録
  - `SLACK_SIGNING_SECRET`
  - `GITHUB_TOKEN`（`repo`権限のPAT）
  - `GITHUB_REPOSITORY`（例: DJ-RINO/freee-auto-bookkeeping）
- Slack App → Interactivity → Request URL に `https://<your-vercel-domain>/api/slack/interactive` を設定
- ボタン押下→Vercel→GitHub repository_dispatch→Actionsで反映

### 代替案（Slack→GitHub派 / Notion派）
### 証憑の重複削除ポリシー（推奨）
- 既定は「削除しない」。重複検出時は監査ログに記録のみ
- 完全重複（同一sha1かつ同一receipt_hash）のみ削除候補
- 一部金額のレシート等、正当な多重添付の可能性がある場合は削除しない
- 本削除は将来的にSlack承認（ボタン操作）を経て実行
- Slack→GitHub: 現行。双方向が簡単、Actionsに集約
- Notion派: 承認キューをNotion DBで管理。メリット: 可視性、権限管理。デメリット: 追加連携実装、速度


