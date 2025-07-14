# freeeトークン自動更新機能

## 概要

freeeのアクセストークンは24時間で有効期限が切れるため、自動的にリフレッシュする仕組みを実装しています。

## 必要な設定

### GitHub Secretsに追加が必要な項目

1. **FREEE_REFRESH_TOKEN**
   - 初回認証時に取得したリフレッシュトークン
   - アクセストークンと一緒に返される

2. **FREEE_CLIENT_ID**
   - freee Developersで作成したアプリのClient ID

3. **FREEE_CLIENT_SECRET**
   - freee Developersで作成したアプリのClient Secret

4. **GITHUB_TOKEN**（自動設定）
   - GitHub Actionsが自動的に提供
   - Secretsの更新に使用

## 動作の仕組み

1. **実行開始時**
   - 現在のアクセストークンの有効性をチェック
   - 401エラーの場合、自動的にリフレッシュ

2. **トークンリフレッシュ**
   - リフレッシュトークンを使って新しいアクセストークンを取得
   - 成功したら自動的にGitHub Secretsを更新

3. **エラー時のフォールバック**
   - 自動更新に失敗した場合は、既存のトークンを使用
   - エラーログを出力

## 初回設定手順

### 1. freeeで初回認証を実行

```bash
# 認証URLを生成
https://accounts.secure.freee.co.jp/public_api/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code

# 認証コードを使ってトークンを取得
curl -X POST https://accounts.secure.freee.co.jp/public_api/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "code=認証コード" \
  -d "redirect_uri=urn:ietf:wg:oauth:2.0:oob"
```

### 2. レスポンス例

```json
{
  "access_token": "xxx...",
  "token_type": "bearer",
  "expires_in": 86400,
  "refresh_token": "yyy...",
  "scope": "read write",
  "created_at": 1234567890
}
```

### 3. GitHub Secretsに設定

- `FREEE_ACCESS_TOKEN`: access_tokenの値
- `FREEE_REFRESH_TOKEN`: refresh_tokenの値
- `FREEE_CLIENT_ID`: アプリのClient ID
- `FREEE_CLIENT_SECRET`: アプリのClient Secret

## トークンの有効期限

- **アクセストークン**: 24時間（86400秒）
- **リフレッシュトークン**: 通常は無期限（ただしfreeeの仕様変更に注意）

## トラブルシューティング

### リフレッシュが失敗する場合

1. **Client ID/Secretの確認**
   - freee Developersで正しい値を確認

2. **リフレッシュトークンの有効性**
   - 一度も使用していないトークンか確認
   - 無効な場合は初回認証からやり直し

3. **GitHub Secretsの権限**
   - GITHUB_TOKENに書き込み権限があるか確認

### ログの確認方法

```bash
# GitHub Actionsのログを確認
gh run view [RUN_ID] --repo DJ-RINO/freee-auto-bookkeeping --log

# トークン更新関連のログを検索
gh run view [RUN_ID] --repo DJ-RINO/freee-auto-bookkeeping --log | grep -i token
```

## セキュリティ上の注意

- リフレッシュトークンは特に重要なので、絶対に公開しない
- ログに出力しない
- ローカルファイルに保存する場合は.gitignoreに追加

## 今後の改善案

1. **トークン有効期限の事前チェック**
   - 期限切れ前に更新

2. **エラー時のSlack通知**
   - トークン更新失敗時に通知

3. **バックアップトークンの管理**
   - 複数のトークンを管理