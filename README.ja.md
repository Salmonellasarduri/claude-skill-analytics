# claude-skill-analytics

Claude Code のスキル利用状況を自動で記録・分析するプラグイン。

どのスキルがワークフローを支えているか、どれが眠っているか、どれがサイレントに壊れているか — 一目でわかるようになります。

> **English version**: [README.md](README.md)

## クイックスタート

**1. プラグインディレクトリにクローン:**

```bash
cd ~/.claude/plugins/local-curated/
git clone https://github.com/Salmonellasarduri/claude-skill-analytics.git
```

**2. プロジェクトで有効化:**

`.claude/settings.json` に追加:

```json
{
  "enabledPlugins": {
    "claude-skill-analytics@local-curated": true
  }
}
```

これだけ。以降、スキル呼び出しは自動でログされます。

## 使い方

数日間ふつうに Claude Code を使った後:

```
/claude-skill-analytics:report
```

オプション:
- `--days 7` — 直近7日
- `--skill codex-analyst` — 特定スキルに絞る
- `--format json` — JSON 出力（CI/自動化向け）

## 出力例

```
=== Skill Usage Report (last 30 days) -- 2026-03-18 21:50 ===

--- workflow ---
  Skill                                     Calls   OK%  Sessions Last Used
  ---------------------------------------- ------ ----- --------- ------------
  plan                                         12  100%        10 2026-03-18
  save                                         10  100%         9 2026-03-18
  review                                        8  100%         8 2026-03-17

--- hookify ---
  hookify:configure                             3  100%         2 2026-03-15
  hookify:list                                  2  100%         2 2026-03-14

--- uncategorized ---
  my-custom-skill                               1  100%         1 2026-03-16

--- Signals & Recommendations ---
  [INVESTIGATE] codex-analyst: 40% failure rate (2/5)
    -> Check if the skill is misconfigured or has known issues.
  [DORMANT] doc-updater: last used 2026-02-10 (36d ago)
    -> Consider disabling to reduce context overhead.

--- Daily Trend ---
  2026-03-15    5  #####
  2026-03-16    8  ########
  2026-03-17   12  ############
  2026-03-18    6  ######
```

## 機能

| 機能 | 説明 |
|------|------|
| **自動ログ** | PostToolUse(Skill) フックが全スキル呼び出しを記録 |
| **カテゴリ別ランキング** | ワークフロー系・プラグイン系・カスタム分類でグルーピング |
| **休眠検知** | 30日以上使われていないスキルを `[DORMANT]` としてフラグ |
| **失敗率アラート** | 25%以上の失敗率（3回以上）のスキルを `[INVESTIGATE]` としてフラグ |
| **改善提案** | シグナルごとに具体的なアクションを提示 |
| **JSON エクスポート** | `--format json` で CI/他ツール連携 |
| **ゼロ設定** | インストール直後から動作。設定不要 |

## 設定

### カテゴリのカスタマイズ

プロジェクトルートに `categories.yaml` を作成:

```yaml
workflow:
  - plan
  - save
  - review
  - implement
  - debug

utility:
  - codex-analyst
  - gemini-researcher
  - doc-updater
```

- スキル名に `:` を含むもの（例: `hookify:configure`）はプラグイン名で自動分類されます
- どのルールにも該当しないスキルは `uncategorized` に分類されます

### 閾値の調整

`scripts/skill_analytics.py` を編集:

```python
DORMANT_AFTER_DAYS = 30       # 何日未使用で DORMANT にするか
INVESTIGATE_FAIL_PCT = 0.25   # 失敗率の閾値（25%）
INVESTIGATE_MIN_CALLS = 3     # フラグを立てる最低呼び出し回数
```

## 仕組み

```
  スキル呼び出し
       |
       v
  PostToolUse(Skill) フック
       |
       v
  skill_usage_logger.py  -->  logs/skill_usage.jsonl
       |
       v
  /claude-skill-analytics:report
       |
       v
  skill_analytics.py  -->  ランキング + シグナル + 改善提案
```

1. Claude Code がスキルを呼び出すたびに、フックがログエントリを追記
2. レポートコマンドを実行すると、分析スクリプトがログを読んでインサイトを生成

## プライバシー

このプラグインが記録するのは以下のフィールド **のみ** です:

| フィールド | 例 | 用途 |
|------------|------|------|
| `ts` | `2026-03-18T12:00:00+00:00` | 呼び出し時刻 |
| `v` | `1` | ログスキーマバージョン |
| `skill` | `plan` | どのスキルが呼ばれたか |
| `command_name` | `plan` | Claude Code が返したコマンド名 |
| `session_id` | `uuid` | セッション内の呼び出しをグルーピング |
| `success` | `true` | 成功したかどうか |

**記録されないもの:** プロジェクトのパス、ファイル名、コード断片、スキルの引数、その他のコンテンツ。

ログファイルはプロジェクト内の `logs/skill_usage.jsonl` に保存されます。誤コミット防止のため `.gitignore` に `logs/` を追加してください。

## アンインストール

**1.** `.claude/settings.json` から削除:

```json
{
  "enabledPlugins": {
    "claude-skill-analytics@local-curated": false
  }
}
```

**2.** プラグインディレクトリを削除:

```bash
rm -rf ~/.claude/plugins/local-curated/claude-skill-analytics
```

**3.** ログデータを削除（任意）:

```bash
rm logs/skill_usage.jsonl logs/.last_skill_report
```

## 既知の制限事項

- **Windows の `python3`**: フックは `python3` を使用しますが、Windows では PATH に存在しない場合があります。Git Bash 環境では通常利用可能です。これは Python を使うすべての Claude Code プラグインに共通する制約です。
- **フック API の安定性**: Claude Code のフックシステムは発展途上です。将来のアップデートで PostToolUse のフォーマットが変わった場合、ロガーの更新が必要になる場合があります。パーサーは欠損フィールドをグレースフルに処理します。
- **PostToolUse matcher**: `hooks.json` の `"Skill"` matcher はプロジェクト設定では動作確認済みですが、プラグインインストール経由では未検証です。ログが記録されない場合は Claude Code のバージョンを確認してください。

## 動作要件

- Claude Code（プラグインサポート付き）
- Python 3.10+

## ライセンス

MIT
