# freee × Claude 自動仕訳システム

freee会計の未仕訳明細を、Claude APIで自動判定して登録するシステムです。

## 特徴

- 過去の取引履歴を学習し、高精度な仕訳を実現
- 信頼度90%以上の取引は自動登録
- 信頼度90%未満の取引はSlackで確認通知（80%未満も必ず通知）
- 会社固有の仕訳パターンを自動学習
- GitHub Actionsで週次自動実行

## 機能

- freee会計から未仕訳の入出金明細を取得
- 過去の取引履歴・勘定科目マスタを参照してAI分析
- Claude APIで勘定科目・税区分・取引先を推定
- 信頼度100%の取引は自動登録
- 信頼度100%未満の取引はSlackで確認通知
- 学習システムによる継続的な精度向上

## セットアップ

### 1. 必要なAPI情報の取得

#### freee API
1. [freee Developers](https://developer.freee.co.jp/) でアプリを作成
2. OAuth2.0でアクセストークンを取得
   ```bash
   # 認証URLの例
   https://accounts.secure.freee.co.jp/public_api/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code
   ```
3. 会社IDを確認（freee管理画面のURLから）

#### Claude API
1. [Anthropic Console](https://console.anthropic.com/) でAPIキーを作成
2. Claude 3 Sonnetを使用（コスト効率重視）

#### Slack Webhook（オプション）
1. Slack App を作成し、Incoming Webhook を有効化
2. Webhook URLを取得

### 2. GitHub設定

1. このリポジトリをFork
2. Settings > Secrets and variables > Actions で以下を設定：
   - `FREEE_ACCESS_TOKEN`
   - `FREEE_COMPANY_ID`
   - `FREEE_CLAUDE_API_KEY`
   - `SLACK_WEBHOOK_URL`（オプション）

### 3. ローカル実行

```bash
# 依存関係のインストール
pip install -r requirements.txt

# 環境変数の設定
cp .env.sample .env
# .envファイルを編集して各種トークンを設定

# 過去データのインポート（初回のみ）
python src/data_importer.py

# テスト実行（登録なし）
DRY_RUN=true python src/main.py

# 本番実行
python src/main.py
```

## 実行方法

### 定期実行
- 毎週月曜日 AM 9:00 自動実行
- 処理完了後、Slackに通知

### 手動実行
1. GitHub Actions の "Auto Bookkeeping" ワークフローへ
2. "Run workflow" をクリック
3. 必要に応じて "Dry run mode" を選択

### Slack経由の手動実行
```
/freee-bookkeeping          # 本番実行
/freee-bookkeeping dry-run  # テスト実行
```

## 学習データの活用

システムは以下のデータを参照して推論精度を向上させます：

1. **過去の取引履歴**（deals.csv）
   - 実際の仕訳パターンを学習
   - 取引先ごとの傾向を把握

2. **勘定科目マスタ**（freee_account_item_*.csv）
   - 正確な勘定科目IDと名称のマッピング
   - 税区分の自動判定

3. **取引先マスタ**（freee_partners_*.csv）
   - 取引先の正式名称を把握
   - 取引先ごとの支払条件

4. **自動仕訳ルール**（freee_user_matchers_*.csv）
   - 既存の自動仕訳ルールを活用
   - パターンマッチングの精度向上

## コスト試算

### Claude API（Claude 3 Sonnet）
- 入力: $3 / 1Mトークン
- 出力: $15 / 1Mトークン
- 1取引あたり: 約2,000トークン（過去データ含む）

### 月間コスト目安
| 取引件数/月 | Claude API | 日本円換算 |
|------------|------------|-----------|
| 100件      | $0.60      | 約90円    |
| 500件      | $3.00      | 約450円   |
| 1,000件    | $6.00      | 約900円   |

### freee API
- 無料（API制限: 3,000回/日、300回/時）

## 仕訳ルール例

システムは過去の取引パターンを学習し、以下のような判定を行います：

| 摘要 | 推定勘定科目 | 税区分 | 信頼度 |
|------|------------|--------|---------|
| Amazon Web Services | 通信費(604) | 課税10%(21) | 95% |
| セブンイレブン | 雑費(831) | 軽減8%(24) | 90% |
| JR東日本 | 旅費交通費(607) | 課税10%(21) | 92% |
| 給与振込 | 給料手当(650) | 非課税(0) | 88% |

## トラブルシューティング

### よくあるエラー

1. **401 Unauthorized**
   - アクセストークンの期限切れ
   - → トークンを再取得

2. **文字化け**
   - CSVファイルのエンコーディング問題
   - → Shift-JISで保存されているか確認

3. **取引先が見つからない**
   - 新規取引先の場合
   - → 自動的に新規作成されます

## 開発

### テスト実行
```bash
# ユニットテスト
python -m pytest tests/ -v

# データインポートのテスト
python src/data_importer.py
```

### ディレクトリ構成
```
freee-auto-bookkeeping/
├── src/
│   ├── main.py              # メイン処理
│   ├── enhanced_main.py     # 学習機能付きメイン
│   ├── learning_system.py   # 学習システム
│   └── data_importer.py     # CSVインポート
├── tests/
│   └── test_main.py         # テストコード
├── learning_data/           # 学習データ保存
├── .github/workflows/       # GitHub Actions
├── requirements.txt         # 依存関係
└── README.md               # このファイル
```

## ライセンス

MIT License

## Claude Code Action (CCA) 対応

このリポジトリはClaude Code Actionに対応しており、以下の機能が利用できます：

- プルリクエスト時の自動コードレビュー
- freee API統合部分の品質チェック
- セキュリティ観点でのコード検証
