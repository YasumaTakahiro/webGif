# webGif

ローカル環境で GIF を縦一列に閲覧・整理するための Web アプリです。  
Flask + SQLite + HTMX で動作し、ブラウザからアップロード・カテゴリ／タグ／シリーズによる整理ができます。

## 主な機能

- **ギャラリー** … GIF を縦に並べて閲覧（無限スクロール）
- **カテゴリ・タグ** … 絞り込み（タグは複数選択・AND 条件）
- **シリーズ** … 話数などのまとまりで並び順を指定。絞り込み時は同シリーズをタグが違っても連続表示
- **シリーズのみ / シリーズ名指定** … タグ・カテゴリを無視した表示モード
- **一括取り込み** … フォルダから CLI で `uploads` と DB に登録（Web より高速）
- **GIF ループ補正** … アップロード時・起動時に `loop=0` へ再エンコード（Pillow）
- **LAN 閲覧** … 同一 Wi‑Fi 内の PC・スマホからアクセス可能（任意）

## 必要環境

- Windows 10/11（PowerShell 推奨）
- Python 3.10 以上
- 初回起動時に `.venv` が自動作成され、`requirements.txt` のパッケージがインストールされます

## クイックスタート

```powershell
cd path\to\webGif
.\run.ps1
```

ブラウザで **http://127.0.0.1:5055/** を開きます（デフォルトポートは **5055**。5000 ではありません）。

終了は `Ctrl+C`、または別ターミナルで:

```powershell
.\stop.ps1
```

## 起動スクリプト

| ファイル | 説明 |
|----------|------|
| `run.ps1` / `run.bat` | この PC のみ（`127.0.0.1`）で起動 |
| `run-lan.ps1` / `run-lan.bat` | LAN 内の他端末からもアクセス（`0.0.0.0`） |
| `stop.ps1` / `stop.bat` | ポート 5055 等で動いているサーバーを停止 |
| `import_gifs.ps1` / `import_gifs.bat` | フォルダから GIF を一括登録 |

PowerShell では `.\run.ps1` のように実行してください（`run.bat` だけでは環境によっては venv 作成に失敗することがあります）。

## 環境変数

| 変数 | 既定値 | 説明 |
|------|--------|------|
| `WEBGIF_HOST` | `127.0.0.1` | 待ち受けアドレス（LAN 公開時は `0.0.0.0`） |
| `WEBGIF_PORT` | `5055` | ポート番号 |
| `MAX_UPLOAD_MB` | `0`（無制限） | Web アップロードの合計サイズ上限（MB）。`0` で制限なし |
| `SECRET_KEY` | 開発用固定値 | Flask セッション用（本番では必ず変更） |

例（LAN 公開）:

```powershell
$env:WEBGIF_HOST = "0.0.0.0"
.\run.ps1
```

または `.\run-lan.ps1` を使用します。

## フォルダから一括登録

Web フォームより速く大量の GIF を登録する場合:

```powershell
# 対象確認（書き込みなし）
.\import_gifs.ps1 "D:\path\to\gifs" -n

# 登録
.\import_gifs.ps1 "D:\path\to\gifs"

# サブフォルダ込み・シリーズに 1 番から付与
.\import_gifs.ps1 "D:\gifs\ep1" -r --series-id 1 --series-order-start 1
```

主なオプション: `-r`（再帰）、`--category-id`、`--tag-ids 1,2`、`--series-id`、`--series-order-start`、`--skip-duplicates`、`--no-loop-fix`、`-n`（dry-run）。

タイトルは **元ファイル名（拡張子なし）** になります。

## LAN 内のスマホ・他 PC から見る

1. `.\run-lan.ps1` で起動
2. 表示された `http://192.168.x.x:5055/` を同じ Wi‑Fi の端末で開く
3. ファイアウォールで Python をブロックされた場合は「許可」

**注意:** 認証機能はありません。信頼できる家庭内 LAN でのみ利用してください。インターネット公開を想定した設計ではありません。

## プロジェクト構成

```
webGif/
  app.py              # Flask アプリ・ルート
  db.py               # SQLite スキーマ・クエリ
  gif_util.py         # GIF ループ補正
  import_gifs.py      # 一括取り込み CLI
  webgif_log.py       # ログ出力
  requirements.txt
  templates/          # Jinja2 テンプレート
  static/             # CSS / JavaScript
  uploads/            # GIF 実体（Git では .gitkeep のみ追跡）
  webgif.db           # SQLite（Git 対象外・初回起動で作成）
```

## Git で管理しないもの

`.gitignore` により、次はリポジトリに含めません。

- `.venv/` … 仮想環境（`pip install -r requirements.txt` で再作成）
- `uploads/*.gif` … 画像ファイル
- `webgif.db` … データベース
- `webgif.log` … ログ

clone 後は `.\run.ps1` で venv と DB を用意し、GIF はアップロードまたは `import_gifs` で追加してください。

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| `python` が動かない / Store 版が開く | `.\run.ps1` を使う（`.venv` の Python を使用） |
| ポート使用中 | `.\stop.ps1` 後に再起動。別ポートは `$env:WEBGIF_PORT = "5056"` |
| アップロードが遅い / タイムアウト | 大きい GIF は `import_gifs` を利用。`MAX_UPLOAD_MB=0` は既定 |
| Ctrl+C 後もサーバーが残る | `.\stop.ps1` |
| LAN から繋がらない | ファイアウォール許可、同一 Wi‑Fi、VPN オフ、`run-lan` 使用を確認 |
| 接続テスト | ブラウザで `http://127.0.0.1:5055/health` → `webGif OK` |

## 技術スタック

- [Flask](https://flask.palletsprojects.com/) 3.x
- [HTMX](https://htmx.org/) 2.x（絞り込み・部分更新）
- SQLite 3
- [Pillow](https://python-pillow.org/)（GIF 処理）

## ライセンス

このリポジトリにライセンスファイルがない場合は、利用・再配布前にリポジトリ管理者に確認してください。
