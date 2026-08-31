# Minitokyo API Wrapper — ドキュメント

[Minitokyo](http://www.minitokyo.net) の壁紙・同人イラスト（Indy Art）・スキャン画像を、Python から検索・閲覧・取得するための非公式ラッパーです。

- 依存パッケージ: `requests`, `beautifulsoup4`
- Python: 3.9+（`from __future__ import annotations` 使用、`list[str]` などのビルトインジェネリクスを使用）

```bash
pip install requests beautifulsoup4
```

---

## 目次

1. [クイックスタート](#クイックスタート)
2. [全体構成](#全体構成)
3. [`Minitokyo` クライアント](#minitokyo-クライアント)
4. [`Series`](#series)
5. [`ImageItem`](#imageitem)
6. [カテゴリ](#カテゴリ)
7. [例外](#例外)
8. [イテレータ（全ページ取得）](#イテレータ全ページ取得)
9. [実践例](#実践例)（全件ダウンロードスクリプトを含む）
10. [注意点・既知の制約](#注意点既知の制約)

---

## クイックスタート

```python
from minitokyo import Minitokyo

mt = Minitokyo()

# シリーズ（作品）を検索
series = mt.search("haruhi")
print(series.name, series.tid)

# 壁紙一覧（1ページ目）を取得
wallpapers = series.wallpapers(page=1)

for item in wallpapers:
    print(item.id, item.title, item.resolution, item.image)
```

---

## 全体構成

このライブラリは3つの主要コンポーネントで構成されます。

| コンポーネント | 役割 |
|---|---|
| `Minitokyo` | HTTPセッションを保持し、検索・シリーズ取得・ギャラリー取得・単体画像取得を行うエントリーポイント |
| `Series` | 1つの作品（タグ）を表すデータクラス。`wallpapers()` / `indy_art()` / `scans()` などのショートカットメソッドを持つ |
| `ImageItem` | 1枚の画像（壁紙・同人イラスト・スキャン）を表すデータクラス |

内部的には Minitokyo の以下のドメインにアクセスします。

- `http://www.minitokyo.net` — 検索・シリーズページ
- `http://browse.minitokyo.net` — ギャラリー（画像一覧）
- `http://gallery.minitokyo.net` — 個別画像ページ

---

## `Minitokyo` クライアント

### `Minitokyo(timeout=20, user_agent=...)`

クライアントを初期化します。内部で `requests.Session()` を1つ保持し、以降のすべてのリクエストで再利用します（Cookie・コネクションが引き継がれます）。

| 引数 | 型 | デフォルト | 説明 |
|---|---|---|---|
| `timeout` | `int` | `20` | 各リクエストのタイムアウト秒数 |
| `user_agent` | `str` | Chrome 140相当のUA文字列 | 送信する `User-Agent` ヘッダー |

```python
mt = Minitokyo(timeout=30)
```

---

### `mt.search(query: str) -> Series`

Minitokyo のサイト内検索を行い、最初にヒットしたシリーズを返します。

Minitokyo は `/search?q=...` に対して通常 `303 See Other` でシリーズページ（例: `/Haruhi+Suzumiya`）へリダイレクトするため、本メソッドはリダイレクトを追跡してシリーズ情報を解析します。万一リダイレクトが発生せず検索結果ページがそのまま返ってきた場合は、フォールバックとしてページ内のリンクから最初のシリーズページを推測して取得します。

| 引数 | 型 | 説明 |
|---|---|---|
| `query` | `str` | 検索語（空文字不可） |

**戻り値:** `Series`

**例外:**
- `ValueError` — `query` が空文字/空白のみ
- `MinitokyoError` — リダイレクトに `Location` ヘッダーがない
- `MinitokyoNotFound` — 該当するシリーズが見つからない

```python
series = mt.search("lucky star")
```

---

### `mt.get_series(url_or_name: str) -> Series`

シリーズページを直接取得します。相対パス（例: `"Haruhi+Suzumiya"`）とフルURLの両方を受け付けます。

```python
series = mt.get_series("Haruhi+Suzumiya")
series = mt.get_series("http://www.minitokyo.net/Haruhi+Suzumiya")
```

**戻り値:** `Series`
**例外:** `MinitokyoNotFound` — ページの解析に失敗した場合

---

### `mt.gallery(tid: int, category: str = "wallpaper", page: int = 1) -> list[ImageItem]`

指定した `tid`（シリーズのタグID）・カテゴリ・ページのギャラリー一覧を取得します。`Series` を経由せず `tid` が分かっている場合に直接呼び出せます。

| 引数 | 型 | デフォルト | 説明 |
|---|---|---|---|
| `tid` | `int` | 必須 | シリーズのタグID |
| `category` | `str` | `"wallpaper"` | `"wallpaper"` / `"indy_art"` / `"scan"`（エイリアス可、[カテゴリ](#カテゴリ)参照） |
| `page` | `int` | `1` | ページ番号（1以上） |

**戻り値:** `list[ImageItem]`（該当ページに画像がなければ空リスト）

**例外:**
- `ValueError` — `tid` が `None`、`page < 1`、または不明なカテゴリ名

```python
items = mt.gallery(tid=1446, category="indy_art", page=2)
```

---

### `mt.get_category(series: Series, category: str = "wallpaper", page: int = 1) -> list[ImageItem]`

`mt.gallery()` のラッパーで、`Series` オブジェクトを直接渡せます（内部で `series.tid` を使用）。

```python
items = mt.get_category(series, "scan", page=1)
```

---

### `mt.iter_gallery(tid: int, category: str = "wallpaper", start_page: int = 1) -> Iterator[ImageItem]`

指定カテゴリの全ページを、空ページに到達するまで自動的に巡回する `ImageItem` のイテレータです。

```python
for item in mt.iter_gallery(tid=1446, category="wallpaper"):
    print(item.id, item.title)
```

> ⚠️ 内部でページを1つずつ順にリクエストします。大量ページのシリーズでは相応の時間とリクエスト数がかかります。

---

### `mt.get(image_id: int) -> ImageItem`

画像IDから個別ページ (`gallery.minitokyo.net/view/{id}`) を取得し、`ImageItem` を返します。まずギャラリー一覧と同じ構造での解析を試み、失敗した場合は個別ページ用のフォールバックパーサーで解析します。

```python
image = mt.get(510114)
```

**戻り値:** `ImageItem`
**例外:** `MinitokyoNotFound` — 画像が見つからない、または解析できない

---

### `mt.download_bytes(image_id: int, referer: str = "http://www.minitokyo.net/") -> bytes`

画像IDだけを指定して、オリジナル画像のバイト列を直接取得します。Minitokyo自身の「ダウンロード」ボタンが使っているリダイレクトエンドポイント `http://www.minitokyo.net/download/{id}` を叩くため、HTMLの`/downloads/`リンクをスクレイピングする方式に一切依存しません。

**これが画像を取得する最も確実な方法です。** 理由は[注意点・既知の制約](#注意点既知の制約)を参照してください（要約すると、一覧ページにはそもそもダウンロードリンクが無く、個別ページのリンクはMinitokyo側のバグで壊れていることがあるためです）。

| 引数 | 型 | デフォルト | 説明 |
|---|---|---|---|
| `image_id` | `int` | 必須 | 画像ID |
| `referer` | `str` | `"http://www.minitokyo.net/"` | 送信する `Referer` ヘッダー |

**戻り値:** `bytes`（画像の生データ）
**例外:** `ValueError` — `image_id` が `None`。HTTPエラー時は `requests.exceptions.HTTPError` がそのまま伝播

```python
data = mt.download_bytes(509290)

with open("509290.jpg", "wb") as f:
    f.write(data)
```

`item.download_url` / `item.image` はあくまで「HTMLから拾えた場合のおまけ情報」として扱い、実際にファイルを保存する処理では `download_bytes(item.id)` を使うことを推奨します。

---

## `Series`

シリーズ（作品）を表すデータクラス。

| フィールド | 型 | 説明 |
|---|---|---|
| `name` | `str` | シリーズ名 |
| `url` | `str` | シリーズページのURL |
| `tid` | `Optional[int]` | Minitokyo内部のタグID |
| `wallpaper_count` | `Optional[int]` | 壁紙の総数（ページ上の表記から取得） |
| `indy_art_count` | `Optional[int]` | 同人イラストの総数 |
| `scan_count` | `Optional[int]` | スキャンの総数 |
| `tags` | `list[str]` | 「Tagged under」欄から取得したタグ一覧 |

### メソッド

| メソッド | 説明 |
|---|---|
| `series.wallpapers(page=1)` | 壁紙一覧を取得（`list[ImageItem]`） |
| `series.indy_art(page=1)` | 同人イラスト一覧を取得 |
| `series.scans(page=1)` | スキャン一覧を取得 |
| `series.category(category, page=1)` | 任意カテゴリ名を指定して取得 |
| `series.iter_wallpapers(start_page=1)` | 壁紙を全ページ巡回するイテレータ |
| `series.iter_indy_art(start_page=1)` | 同人イラストを全ページ巡回するイテレータ |
| `series.iter_scans(start_page=1)` | スキャンを全ページ巡回するイテレータ |

> `Series` は `Minitokyo.search()` / `Minitokyo.get_series()` から返された時点で内部的に `_client` （発行元の `Minitokyo` インスタンス）を保持しています。`Series` を自分でインスタンス化して上記メソッドを呼ぶと `_client` が `None` のため `MinitokyoError` になります。

```python
series = mt.search("k-on")

for wp in series.iter_wallpapers():
    print(wp.id, wp.resolution)
```

---

## `ImageItem`

1枚の画像を表すデータクラス。

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | `int` | 画像ID |
| `title` | `str` | タイトル（取得できない場合は `alt` テキストで代替） |
| `url` | `Optional[str]` | Minitokyoのギャラリー個別ページURL |
| `thumbnail` | `Optional[str]` | サムネイル画像URL |
| `image` | `Optional[str]` | オリジナル画像のダウンロードURL |
| `resolution` | `Optional[str]` | 解像度（例: `"1920x1080"`） |
| `author` | `Optional[str]` | 投稿者名（本文中の `"... by username"` から抽出、取れないこともある） |
| `category` | `Optional[str]` | `"wallpaper"` / `"indy_art"` / `"scan"` |
| `tags` | `list[str]` | 現状は常に空リスト（将来の拡張用フィールド） |

### プロパティ

- `item.download_url` — `item.image` のエイリアス

```python
item = items[0]
print(item.download_url)  # item.image と同じ
```

> ⚠️ **`image` / `download_url` は信頼できないことがあります。** ギャラリー一覧ページ（`ul.scans`）にはそもそも `/downloads/` リンクが含まれていないことが多く、その場合 `image` は `None` になります。また個別ページ（`/view/{id}`）側では、Minitokyo側のサーバーバグで `href` 属性の中にPHPの警告文（`Warning: Undefined array key "filename" in ...`）が混入していることがあり、これは `_clean_url()` で正規表現によりURL部分だけを抽出して対処していますが、根本的にHTML構造に依存する不安定な取得経路です。**実際にファイルをダウンロードする場合は、`item.download_url` の有無に関わらず `Minitokyo.download_bytes(item.id)` を使ってください。** こちらはHTMLをパースせず、Minitokyo自身のダウンロードリダイレクトエンドポイントを直接叩くため安定しています。

> `thumbnail` / `author` についても、Minitokyo 側のHTML構造やページ種別によって `None` になることがあります。使用前に必ず `None` チェックをしてください。

---

## カテゴリ

`category` 引数には以下のいずれかの正規名、またはエイリアスを渡せます（大文字小文字・前後の空白は無視されます）。

| 正規名 | 受理されるエイリアス |
|---|---|
| `wallpaper` | `wallpaper`, `wallpapers` |
| `indy_art` | `indy_art`, `indy`, `indy art`, `indyart` |
| `scan` | `scan`, `scans` |

未知のカテゴリ名を渡すと `ValueError` が発生します。

```python
mt.gallery(tid=1446, category="Wallpapers")  # OK -> "wallpaper" として扱われる
mt.gallery(tid=1446, category="posters")     # ValueError
```

---

## 例外

| 例外クラス | 継承元 | 発生条件 |
|---|---|---|
| `MinitokyoError` | `Exception` | ベース例外。想定外のレスポンス構造など |
| `MinitokyoNotFound` | `MinitokyoError` | 検索・シリーズ取得・画像取得で対象が見つからない場合 |

```python
from minitokyo import Minitokyo, MinitokyoNotFound

mt = Minitokyo()

try:
    series = mt.search("存在しない作品名のような何か")
except MinitokyoNotFound:
    print("見つかりませんでした")
```

`requests` 由来の `requests.exceptions.HTTPError` / `Timeout` / `ConnectionError` などは捕捉されず、そのまま呼び出し元に伝播します。

---

## イテレータ（全ページ取得）

以下の3つのイテレータは、いずれも「返ってきたページが空リストになるまで `page` を1ずつ増やして呼び続ける」という同じロジックです。

- `Minitokyo.iter_gallery(tid, category, start_page=1)`
- `Series.iter_wallpapers(start_page=1)`
- `Series.iter_indy_art(start_page=1)`
- `Series.iter_scans(start_page=1)`

```python
# 全壁紙のIDだけ集める
all_ids = [item.id for item in series.iter_wallpapers()]
```

途中で打ち切りたい場合は `itertools.islice` などと組み合わせてください。

```python
import itertools

first_50 = list(itertools.islice(series.iter_wallpapers(), 50))
```

---

## 実践例

### 1. シリーズ検索 → 高解像度壁紙だけ抽出

```python
mt = Minitokyo()
series = mt.search("violet evergarden")

hd_wallpapers = [
    item for item in series.wallpapers(page=1)
    if item.resolution and "1920" in item.resolution
]
```

### 2. 画像を1枚だけダウンロードして保存

```python
item = mt.get(510114)

data = mt.download_bytes(item.id)

with open(f"{item.id}.jpg", "wb") as f:
    f.write(data)
```

> 以前は `item.download_url` を `mt.session.get()` で直接叩く方法を案内していましたが、[前述の通り](#imageitem)このURLはHTMLの構造やサイト側のバグに依存して欠損・破損することがあるため、`mt.download_bytes(item.id)` を使う方法に統一しています。

### 3. 複数シリーズを横断して壁紙数をまとめる

```python
names = ["haruhi", "k-on", "lucky star"]

for name in names:
    series = mt.search(name)
    print(f"{series.name}: 壁紙 {series.wallpaper_count} / スキャン {series.scan_count}")
```

### 4. シリーズの画像を全件ダウンロード（カテゴリ絞り込み対応）

`iter_wallpapers()` / `iter_indy_art()` / `iter_scans()` を使って全ページを巡回し、各画像を `mt.download_bytes(item.id)` で取得してローカルに保存するヘルパー関数の例です。`categories` 引数でダウンロード対象を絞り込めます。

`item.download_url`（HTMLからのスクレイピング結果）には依存せず、常に `download_bytes()` でIDから直接取得するため、一覧ページにダウンロードリンクが無いケースや、個別ページのリンクがサイト側のバグで壊れているケースの両方を気にする必要がありません。

```python
import time
import re
from pathlib import Path

import requests

from minitokyo import Minitokyo, MinitokyoError


def download_all(
    series_name: str,
    out_dir: str = "downloads",
    categories: tuple[str, ...] = ("wallpaper", "indy_art", "scan"),
    delay: float = 1.0,
):
    mt = Minitokyo()
    series = mt.search(series_name)

    base_dir = Path(out_dir) / _safe_name(series.name)
    base_dir.mkdir(parents=True, exist_ok=True)

    for category in categories:
        cat_dir = base_dir / category
        cat_dir.mkdir(exist_ok=True)

        items = series.iter_wallpapers() if category == "wallpaper" \
            else series.iter_indy_art() if category == "indy_art" \
            else series.iter_scans()

        for item in items:
            # 拡張子はitem.imageから推測できればそれを使い、
            # 取れなければjpgにフォールバックする。
            ext = "jpg"
            if item.image:
                guessed = item.image.rsplit(".", 1)[-1].split("?")[0]
                if len(guessed) <= 4 and guessed.isalnum():
                    ext = guessed

            dest = cat_dir / f"{item.id}.{ext}"

            if dest.exists():
                print(f"[skip] {item.id}: 既にダウンロード済み")
                continue

            try:
                data = mt.download_bytes(item.id)

            except (requests.RequestException, MinitokyoError) as e:
                print(f"[error] {item.id}: {e}")
                continue

            dest.write_bytes(data)
            print(f"[ok] {item.id} -> {dest}")

            time.sleep(delay)  # サイトに負荷をかけすぎないよう間隔をあける


def _safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()
```

**カテゴリの絞り込みは `categories` 引数だけで変更できます。**

```python
# デフォルト：壁紙・同人イラスト・スキャン全部
download_all("haruhi")

# スキャンだけ
download_all("haruhi", categories=("scan",))

# 壁紙と同人イラストだけ（スキャン除外）
download_all("haruhi", categories=("wallpaper", "indy_art"))

# 壁紙だけ
download_all("haruhi", categories=("wallpaper",))
```

コマンドライン引数で対話的に切り替えたい場合:

```python
import sys

if __name__ == "__main__":
    series_name = sys.argv[1]
    categories = tuple(sys.argv[2:]) or ("wallpaper", "indy_art", "scan")
    download_all(series_name, categories=categories)
```

```bash
python download.py haruhi scan
python download.py haruhi wallpaper indy_art
```

> `download_all()` は既存ファイルがあればスキップするので、途中で中断しても再実行すれば続きから再開できます。`delay` はサイトへの負荷軽減とアクセス制限回避のため、1〜2秒程度を目安にしてください。

---

## 注意点・既知の制約

- **非公式ラッパーです。** Minitokyo公式のAPIではなく、HTML構造をスクレイピング・解析しているため、サイト側のマークアップ変更で動作しなくなる可能性があります。
- **`item.image` / `item.download_url` は当てにしないこと。** ギャラリー一覧ページには`/downloads/`リンクがそもそも含まれておらず、`image`が`None`になることがあります。個別ページ（`/view/{id}`）側では、Minitokyo側のサーバーバグにより`href`属性の中にPHPの警告文（`Warning: Undefined array key "filename" in /var/www/minitokyo/www/html2/view.html on line 37`）がそのまま出力されているケースが確認されています。`_clean_url()`は正規表現で実際のURL部分だけを抽出することでこれに対処していますが、根本的にHTML依存で不安定なため、**実ファイルの取得には必ず `Minitokyo.download_bytes(image_id)` を使ってください。**
- **ホットリンク対策の可能性。** `download_bytes()`を含め、画像本体に直接アクセスする際は`Referer`ヘッダーや`mt.session`のCookieが必要になる場合があります。403が返る場合はまずここを疑ってください。
- **カウント値の欠損。** `Series.wallpaper_count` などはページ上の表記（例: `"Wallpapers (1,234)"`）から正規表現で抽出しているため、表記が変わると `None` になります。
- **`author` の抽出精度。** タイトル文字列末尾の `"... by username"` パターンに依存しているため、投稿者名が付いていない・別形式の場合は `None` になります。
- **レート制限は未実装。** `iter_*` 系メソッドを使う場合、連続リクエストになるため、必要に応じて `time.sleep()` を挟むなど自前でレート制御してください。
- **HTTP接続。** `BASE_URL` / `GALLERY_URL` / `BROWSE_URL` はいずれも `http://` です。サイト側が `https` にリダイレクトする場合、`requests` が自動的に追従します。
