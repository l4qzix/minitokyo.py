"""
Minitokyo のシリーズ画像を一括ダウンロードするスクリプト。

一覧ページ・個別ページのHTMLに含まれる /downloads/ リンクはあてにせず、
Minitokyo 自身のダウンロードリダイレクトエンドポイント
(http://www.minitokyo.net/download/{id}) を直接叩いて画像バイト列を
取得する mt.download_bytes() を使用しています。

使い方:

    python download.py haruhi
    python download.py haruhi scan
    python download.py haruhi wallpaper indy_art
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import requests

from minitokyo import Minitokyo, MinitokyoError


DEFAULT_CATEGORIES = ("wallpaper", "indy_art", "scan")


def download_all(
    series_name: str,
    out_dir: str = "downloads",
    categories: tuple[str, ...] = DEFAULT_CATEGORIES,
    delay: float = 1.0,
) -> None:

    mt = Minitokyo()
    series = mt.search(series_name)

    base_dir = Path(out_dir) / _safe_name(series.name)
    base_dir.mkdir(parents=True, exist_ok=True)

    for category in categories:

        cat_dir = base_dir / category
        cat_dir.mkdir(exist_ok=True)

        if category == "wallpaper":
            items = series.iter_wallpapers()

        elif category == "indy_art":
            items = series.iter_indy_art()

        else:
            items = series.iter_scans()

        for item in items:

            # 拡張子はitem.imageから推測できればそれを使い、
            # 取れなければjpgにフォールバックする。
            # (item.image はHTMLから拾えた場合のみ入っている、
            #  あくまで拡張子推測のためのヒント。)
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


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python download.py <series_name> [category ...]")
        sys.exit(1)

    series_name = sys.argv[1]
    categories = tuple(sys.argv[2:]) or DEFAULT_CATEGORIES

    download_all(series_name, categories=categories)
