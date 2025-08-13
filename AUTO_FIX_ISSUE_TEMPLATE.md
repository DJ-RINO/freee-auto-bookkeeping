# 🔥 今すぐ実行可能なClaude自動修正Issue

以下のテキストをコピーして、GitHubリポジトリで新しいIssueを作成してください：

---

## Issue タイトル
```
[CLAUDE AUTO] freee自動経理システムの完全自動修正
```

## Issue 本文
```markdown
@claude freee自動経理システムの自動診断と修正を実行してください。

### 📊 現在の問題状況
最新のGitHub Actions結果: https://github.com/DJ-RINO/freee-auto-bookkeeping/actions/runs/16943583287

**確認された問題:**
1. 🚨 自動紐付け: **0件** (目標: 30%以上)
2. 🚨 手動対応: **50件** (全件が手動になっている)
3. 🚨 学習システム過剰反応: "None" → ヤマト運輸の不正マッチが数百回
4. ⚠️ スコア上限: 62.8点 (閾値70点に届かない)

### 🛠️ 自動修正リクエスト

#### 最優先修正タスク
- [ ] **学習システム修正**: 空文字列("None")での学習マッチを除外
- [ ] **閾値調整**: 現実的な自動紐付け閾値に変更（70→60点）
- [ ] **許容範囲拡大**: 金額・日付の許容範囲を業務実態に合わせる
- [ ] **デバッグ出力削減**: 不要な学習マッチログを削除

#### 期待される結果
1. 自動紐付け率: 0% → **20%以上**
2. エラー発生: 数百個 → **0個**  
3. 実行時間: 現在値 → **30%短縮**
4. ログ品質: ノイズ多 → **クリーンな出力**

### 🎯 修正後の検証項目
- [ ] GitHub Actionsが正常実行される
- [ ] 最低1件の自動紐付けが発生する
- [ ] "None"に対する学習マッチが発生しない
- [ ] 全体実行時間が改善される

### 📋 関連ファイル
修正が必要と思われるファイル:
- `src/matcher.py` (学習システムの過剰反応修正)
- `config/linking.yml` (閾値調整) 
- `src/vendor_mapping_learner.py` (学習データ品質向上)
- `src/linker.py` (マッチング精度向上)

---
**実行方針**: この問題を完全自動で解決し、次回のGitHub Actions実行で改善結果を確認できるようにしてください。
```

---

## 🚀 即座実行コマンド

GitHubリポジトリで以下をコマンドライン実行：

```bash
# GitHub CLI使用（推奨）
gh issue create --title "[CLAUDE AUTO] freee自動経理システムの完全自動修正" --body "$(cat AUTO_FIX_ISSUE_TEMPLATE.md | sed -n '/## Issue 本文/,/---/p' | sed '1d;$d')"

# または Web UI で手動作成
# https://github.com/DJ-RINO/freee-auto-bookkeeping/issues/new
```

## ✅ 成功確認方法

1. **Issue作成後5分以内**: Claude Code Actionが起動
2. **10分以内**: Pull Requestが自動作成される  
3. **PR確認後**: マージして次のGitHub Actions実行を確認
4. **結果確認**: 自動紐付け件数が1件以上になることを確認

---

**注意**: ANTHROPIC_API_KEY がGitHub Secretsに設定されていることを事前確認してください。