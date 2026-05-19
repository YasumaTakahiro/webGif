# webGif

ローカル環境で GIF を縦一列に閲覧・整理するための Web アプリです。  
Flask + SQLite + HTMX で動作し、ブラウザからアップロード・カテゴリ／タグ／シリーズによる整理ができます。

開発環境は **Dev Container**（Docker）を前提としています。

## 主な機能

- **ギャラリー** … GIF を縦に並べて閲覧（無限スクロール）
- **カテゴリ・タグ** … 絞り込み（タグは複数選択・AND 条件）
- **シリーズ** … 話数などのまとまりで並び順を指定。絞り込み時は同シリーズをタグが違っても連続表示
- **通常 GIF の表示順** … シリーズ未所属の画像は `gallery_order` で並べ替え（カードの ↑↓）。ID は変えません
- **シリーズのみ / シリーズ名指定** … タグ・カテゴリを無視した表示モード
- **一括取り込み** … フォルダから CLI で `uploads` と DB に登録（Web より高速）
- **LAN 閲覧** … 同一 Wi‑Fi 内の PC・スマホからアクセス可能（任意）

## 必要環境

| 項目 | 内容 |
|------|------|
| Docker Desktop | Windows / macOS / Linux |
| エディタ | Cursor または VS Code + [Dev Containers 拡張](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) |
| GitHub 利用時 | [Git for Windows](https://git-scm.com/download/win)（認証連携用） |

Python はコンテナ内の **`/opt/venv`** に入ります（ホストに Python や `.venv` は不要）。

## クイックスタート

1. リポジトリを Cursor / VS Code で開く
2. コマンドパレット → **Dev Containers: Reopen in Container**
3. 初回ビルド後、サーバーを起動:

```bash
bash .devcontainer/run-dev.sh
```

タスク（**Terminal → Run Task…**）:
- **webGif: run server** … 起動
- **webGif: stop server** … 停止（ポート 5055）
- **webGif: restart server** … 停止してから起動

4. ブラウザで **http://127.0.0.1:5055/**（ポート **5055**。5000 ではない）
5. 終了: 起動したターミナルで **Ctrl+C**

> `run-dev.sh` が `bad interpreter` になる場合は CRLF です。`bash .devcontainer/run-dev.sh` を使うか、`.gitattributes` で LF に直してください。

## 環境変数

| 変数 | 既定値（コンテナ） | 説明 |
|------|-------------------|------|
| `WEBGIF_HOST` | `0.0.0.0` | 待ち受けアドレス |
| `WEBGIF_PORT` | `5055` | ポート番号 |
| `MAX_UPLOAD_MB` | `0`（無制限） | Web アップロードの合計サイズ上限（MB） |
| `WEBGIF_UPLOAD_TMP` | `/tmp/webgif-uploads`（コンテナ） | 受信をコンテナ内 tmp に書いてから `uploads/` へ移動（bind mount への書き込みを短くする） |
| `SECRET_KEY` | 開発用固定値 | Flask セッション用（本番では必ず変更） |

例（別ポート）:

```bash
WEBGIF_PORT=5056 bash .devcontainer/run-dev.sh
```

## フォルダから一括登録

Web より速く大量の GIF を登録する場合（コンテナ内）:

```bash
# 対象確認（書き込みなし）
python import_gifs.py /mnt/gifs -n

# 登録
python import_gifs.py /mnt/gifs

# サブフォルダ込み・シリーズに 1 番から付与
python import_gifs.py /mnt/gifs/ep1 -r --series-id 1 --series-order-start 1
```

ホストの別フォルダを使うときは `docker-compose.yml` の `app.volumes` にマウントを追加:

```yaml
volumes:
  - .:/workspace:cached
  - D:/path/to/gifs:/mnt/gifs:ro
```

主なオプション: `-r`（再帰）、`--category-id`、`--tag-ids 1,2`、`--series-id`、`--series-order-start`、`--skip-duplicates`、`-n`（dry-run）。

タイトルは **元ファイル名（拡張子なし）** になります。  
`uploads/` と DB で同名がなければ、保存ファイル名もアップロード時と同じ名前になります。同名がある場合は確認画面で **SHA-256** を表示し同一内容か判別したうえで、**スキップ / 両方残す（`名前_20260519_143022.ext` のように JST タイムスタンプを付与）/ 置き換え** を選べます。

ギャラリーでは各画像の **非表示**（ファイルは残す）と **お気に入り**（☆ / ★）が可能です。絞り込みパネルで **表示中のみ / 非表示のみ**、**お気に入りのみ** を切り替えられます。

## LAN 内のスマホ・他 PC から見る

Dev Container では既定で `WEBGIF_HOST=0.0.0.0` です。

1. `bash .devcontainer/run-dev.sh` で起動
2. ホスト PC の LAN IP で `http://192.168.x.x:5055/` を開く（ポート転送・ファイアウォールはホスト側）
3. ファイアウォールでブロックされた場合は Docker / ポート 5055 を許可

**注意:** 認証機能はありません。信頼できる家庭内 LAN でのみ利用してください。

## Dev Container の構成

| 項目 | 場所 |
|------|------|
| ソース・`uploads/`・`webgif.db` | ワークスペース bind（ホストと共有） |
| Python 仮想環境 | `/opt/venv`（コンテナ内のみ） |
| pip キャッシュ | Named Volume `pip-cache` |
| シェル履歴 | Named Volume `webgif-bashhistory-*` |

`docker-compose.yml` の `app` に加え、将来は同ファイルに Redis などを追記できます。

## Git / GitHub

**初回（ホスト側）**

1. Git for Windows をインストール
2. Cursor → **GitHub にサインイン**
3. **Dev Containers: Rebuild Container**

**コンテナ内**

```bash
git status
gh auth status
gh auth login   # 未ログイン時
```

| 症状 | 対処 |
|------|------|
| `dubious ownership` | `git config --global --add safe.directory /workspace`（Rebuild 後は自動） |
| SSH 認証失敗 | ホストの `~/.ssh` を用意して Rebuild |
| HTTPS 認証失敗 | ホストで GitHub サインイン → Rebuild、または `gh auth login` |

## プロジェクト構成

```
webGif/
  .devcontainer/      # Dockerfile, devcontainer.json, run-dev.sh
  docker-compose.yml
  app.py
  db.py
  import_gifs.py      # 一括取り込み CLI
  webgif_log.py
  requirements.txt
  templates/
  static/
  uploads/            # GIF 実体（.gitkeep のみ追跡）
  webgif.db           # 初回起動で作成（Git 対象外）
```

## Git で管理しないもの

- `uploads/*.gif` … 画像ファイル
- `webgif.db` … データベース
- `webgif.log` … ログ
- `.venv/` … 使用しない（誤って作った場合用に ignore のみ残す）

clone 後は Dev Container を開き、`run-dev.sh` で起動。GIF は Web アップロードまたは `import_gifs.py` で追加。

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| ポート使用中 | 起動中のターミナルを Ctrl+C。別ポートは `WEBGIF_PORT=5056` |
| アップロードが遅い／止まったように見える | 大きい GIF は完了まで数分かかることがある（`webgif.log` の `upload saved:` を確認）。大量なら `import_gifs.py` を利用。リポジトリは WSL 内（`/home/...`）に置くと Windows 直下より速い |
| アップロード後に画像が出ない | 送信完了までタブを閉じない。絞り込み（カテゴリ・タグ）を解除して確認 |
| LAN から繋がらない | ファイアウォール・同一 Wi‑Fi・VPN を確認 |
| 接続テスト | `http://127.0.0.1:5055/health` → `webGif OK` |
| `git` / `gh` がない | **Rebuild Container** |

## 技術スタック

- [Flask](https://flask.palletsprojects.com/) 3.x
- [HTMX](https://htmx.org/) 2.x
- SQLite 3

## ライセンス

このリポジトリにライセンスファイルがない場合は、利用・再配布前にリポジトリ管理者に確認してください。
