# 🚨 トークン管理の絶対ルール

## Claude 専用：必須遵守事項

### ❌ 絶対にしてはいけないこと
1. **アクセストークンの直接使用**
   - `os.getenv("FREEE_ACCESS_TOKEN")` の直接使用
   - `.env` ファイルから直接トークン読み込み
   - 期限切れトークンでのAPI呼び出し

2. **認可コード取得の要求**
   - ユーザーに新しい認可コードを求める
   - 手動でのトークン更新を依頼する

### ✅ 必須実行事項
1. **常にintegrate_with_main()を使用**
```python
# これが唯一の正しい方法
from token_manager import integrate_with_main
access_token = integrate_with_main()
```

2. **自動リフレッシュの活用**
- `auto_refresh_if_needed()` メソッドが自動実行
- GitHub Secrets の自動更新
- エラー時の自動再試行

3. **環境変数の正しい読み込み**
```bash
export $(cat .env | grep -v '^#' | xargs) && python script.py
```

## 🔄 トークンライフサイクル

### 正常フロー
1. `integrate_with_main()` 実行
2. 現在のトークン有効期限チェック
3. 必要に応じて自動リフレッシュ
4. 新しいトークンでAPI実行
5. GitHub Secrets自動更新

### 失敗時の自動復旧
1. 401エラー検出
2. リフレッシュトークンでの自動更新試行
3. 成功時：新しいトークンで続行
4. 失敗時：エラーログ出力（認可コード要求はしない）

## 📝 実装例

### ✅ 正しい実装
```python
def process_receipts():
    try:
        # 必ずintegrate_with_mainを使用
        access_token = integrate_with_main()
        client = FreeeClient(access_token, company_id)
        # API操作続行
    except Exception as e:
        print(f"トークン取得エラー: {e}")
        return
```

### ❌ 間違った実装
```python
def process_receipts():
    # 直接アクセストークンを使用（禁止）
    access_token = os.getenv("FREEE_ACCESS_TOKEN")
    # 認可コード要求（禁止）
    print("新しい認可コードを取得してください")
```

## 🛡️ セキュリティ原則

1. **シークレット管理**
   - GitHub Secretsの自動更新
   - ローカル.envの同期
   - トークンの暗号化保存

2. **権限管理**
   - 最小権限の原則
   - スコープの適切な設定
   - 定期的な権限見直し

## 🔧 メンテナンス

### 日次チェック
- トークン有効期限の確認
- API呼び出し成功率
- エラーログの監視

### 週次メンテナンス
- GitHub Secrets同期確認
- リフレッシュトークン状況
- システム全体の健全性チェック

---

**この文書は Claude の動作規範です。例外なく遵守してください。**

**万が一、これらのルールに従わない場合、システム全体が停止する可能性があります。**