# Secretsチェックリスト

設定が完了したら、以下を確認してください：

## 必須項目
- [ ] FREEE_ACCESS_TOKEN が設定されている
- [ ] FREEE_COMPANY_ID が設定されている（数字のみ）
- [ ] ANTHROPIC_API_KEY が設定されている

## オプション
- [ ] SLACK_WEBHOOK_URL が設定されている

## テスト実行
設定完了後、以下のコマンドでテスト：

```bash
# GitHub CLIでテスト
gh workflow run bookkeeping.yml --repo DJ-RINO/freee-auto-bookkeeping -f dry_run=true

# または、GitHubのWebUIから：
# Actions → Auto Bookkeeping → Run workflow → dry_run: true
```

## トラブルシューティング

### よくあるエラー

1. **"invalid literal for int()"**
   - FREEE_COMPANY_ID が数字以外の文字を含んでいる
   - 解決: 数字のみを入力（例: 1234567）

2. **"401 Unauthorized"**
   - トークンの期限切れまたは無効
   - 解決: 新しいトークンを取得して更新

3. **"Secrets not found"**
   - Secret名のタイプミス
   - 解決: 大文字小文字を正確に入力

### 注意事項
- Secretsは一度設定すると内容は表示されません
- 更新する場合は「Update」ボタンから新しい値を入力
- スペースや改行が含まれないよう注意
