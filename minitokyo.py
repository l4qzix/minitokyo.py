from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Optional
from urllib.parse import urljoin

import re
import requests
from bs4 import BeautifulSoup


# ============================================================
# Constants
# ============================================================

BASE_URL = "http://www.minitokyo.net"
GALLERY_URL = "http://gallery.minitokyo.net"
BROWSE_URL = "http://browse.minitokyo.net"

CATEGORY_INDEX = {
    "wallpaper": 1,
    "indy_art": 2,
    "scan": 3,
}

CATEGORY_ALIASES = {
    "wallpapers": "wallpaper",
    "wallpaper": "wallpaper",

    "indy": "indy_art",
    "indy art": "indy_art",
    "indy_art": "indy_art",
    "indyart": "indy_art",

    "scans": "scan",
    "scan": "scan",
}


# ============================================================
# Exceptions
# ============================================================

class MinitokyoError(Exception):
    """Base exception for Minitokyo."""


class MinitokyoNotFound(MinitokyoError):
    """Requested item was not found."""


# ============================================================
# Image
# ============================================================

@dataclass
class ImageItem:
    id: int

    title: str = ""

    # Minitokyo gallery page
    url: Optional[str] = None

    # Thumbnail
    thumbnail: Optional[str] = None

    # Original/download image
    image: Optional[str] = None

    # e.g. 1920x1080
    resolution: Optional[str] = None

    # User / uploader if available
    author: Optional[str] = None

    # wallpaper / indy_art / scan
    category: Optional[str] = None

    # Arbitrary tags
    tags: list[str] = field(default_factory=list)

    def __repr__(self):
        return (
            f"ImageItem("
            f"id={self.id}, "
            f"title={self.title!r}, "
            f"resolution={self.resolution!r}, "
            f"category={self.category!r}"
            f")"
        )

    @property
    def download_url(self) -> Optional[str]:
        """Alias for the original image URL.

        NOTE: On some pages Minitokyo does not expose a scrapeable
        /downloads/ link at all (gallery listing pages), or the link
        is present but corrupted by a server-side PHP warning being
        injected into the href (individual view pages). In both
        cases this may be None or unreliable.

        Prefer `Minitokyo.download_bytes(item.id)` when you need a
        guaranteed way to fetch the original image bytes — it uses
        Minitokyo's own /download/{id} redirect endpoint instead of
        parsing HTML.
        """
        return self.image


# ============================================================
# Series
# ============================================================

@dataclass
class Series:
    name: str

    url: str

    # Minitokyo's internal tag ID
    tid: Optional[int] = None

    # Number of images in each category
    wallpaper_count: Optional[int] = None
    indy_art_count: Optional[int] = None
    scan_count: Optional[int] = None

    tags: list[str] = field(default_factory=list)

    _client: Optional["Minitokyo"] = field(
        default=None,
        repr=False,
        compare=False
    )

    def __repr__(self):
        return (
            f"Series("
            f"name={self.name!r}, "
            f"tid={self.tid!r}"
            f")"
        )

    # --------------------------------------------------------
    # Categories
    # --------------------------------------------------------

    def wallpapers(
        self,
        page: int = 1
    ) -> list[ImageItem]:

        if self._client is None:
            raise MinitokyoError(
                "Series is not attached to a Minitokyo client."
            )

        return self._client.gallery(
            tid=self.tid,
            category="wallpaper",
            page=page
        )

    def indy_art(
        self,
        page: int = 1
    ) -> list[ImageItem]:

        if self._client is None:
            raise MinitokyoError(
                "Series is not attached to a Minitokyo client."
            )

        return self._client.gallery(
            tid=self.tid,
            category="indy_art",
            page=page
        )

    def scans(
        self,
        page: int = 1
    ) -> list[ImageItem]:

        if self._client is None:
            raise MinitokyoError(
                "Series is not attached to a Minitokyo client."
            )

        return self._client.gallery(
            tid=self.tid,
            category="scan",
            page=page
        )

    def category(
        self,
        category: str,
        page: int = 1
    ) -> list[ImageItem]:

        if self._client is None:
            raise MinitokyoError(
                "Series is not attached to a Minitokyo client."
            )

        return self._client.gallery(
            tid=self.tid,
            category=category,
            page=page
        )

    # --------------------------------------------------------
    # Iterators
    # --------------------------------------------------------

    def iter_wallpapers(
        self,
        start_page: int = 1
    ) -> Iterator[ImageItem]:

        page = start_page

        while True:

            items = self.wallpapers(page)

            if not items:
                break

            yield from items

            page += 1

    def iter_indy_art(
        self,
        start_page: int = 1
    ) -> Iterator[ImageItem]:

        page = start_page

        while True:

            items = self.indy_art(page)

            if not items:
                break

            yield from items

            page += 1

    def iter_scans(
        self,
        start_page: int = 1
    ) -> Iterator[ImageItem]:

        page = start_page

        while True:

            items = self.scans(page)

            if not items:
                break

            yield from items

            page += 1


# ============================================================
# Minitokyo client
# ============================================================

class Minitokyo:

    def __init__(
        self,
        timeout: int = 20,
        user_agent: str = (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/140.0 Safari/537.36"
        ),
    ):

        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Language": "en-US,en;q=0.9",
        })

    # ========================================================
    # HTTP
    # ========================================================

    def _request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> requests.Response:

        response = self.session.request(
            method,
            url,
            timeout=self.timeout,
            **kwargs
        )

        response.raise_for_status()

        return response

    def _get_soup(
        self,
        url: str,
        **kwargs
    ) -> tuple[requests.Response, BeautifulSoup]:

        response = self._request(
            "GET",
            url,
            **kwargs
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        return response, soup

    # ========================================================
    # Search
    # ========================================================

    def search(
        self,
        query: str
    ) -> Series:

        """
        Search Minitokyo.

        Example:

            series = mt.search("haruhi")

        Minitokyo redirects:

            /search?q=haruhi
                ->
            /Haruhi+Suzumiya
        """

        if not query or not query.strip():
            raise ValueError("query cannot be empty")

        response = self.session.get(
            f"{BASE_URL}/search",
            params={
                "q": query
            },
            allow_redirects=False,
            timeout=self.timeout
        )

        # ----------------------------------------------------
        # Minitokyo currently returns 303 -> /Series+Name
        # ----------------------------------------------------

        if response.status_code in (301, 302, 303, 307, 308):

            location = response.headers.get("Location")

            if not location:
                raise MinitokyoError(
                    "Search returned a redirect without Location."
                )

            url = urljoin(
                BASE_URL,
                location
            )

            return self._get_series_from_url(url)

        # ----------------------------------------------------
        # If Minitokyo ever returns the search page directly
        # ----------------------------------------------------

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        series = self._parse_search_page(soup)

        if series is None:
            raise MinitokyoNotFound(
                f"No result found for: {query}"
            )

        return series

    # ========================================================
    # Get series directly
    # ========================================================

    def get_series(
        self,
        url_or_name: str
    ) -> Series:

        """
        Get a series.

        Both are accepted:

            mt.get_series("Haruhi+Suzumiya")

        or:

            mt.get_series(
                "http://www.minitokyo.net/Haruhi+Suzumiya"
            )
        """

        if url_or_name.startswith(
            "http://"
        ) or url_or_name.startswith(
            "https://"
        ):
            url = url_or_name

        else:
            url = urljoin(
                BASE_URL + "/",
                url_or_name.lstrip("/")
            )

        return self._get_series_from_url(url)

    # ========================================================
    # Internal series loader
    # ========================================================

    def _get_series_from_url(
        self,
        url: str
    ) -> Series:

        response, soup = self._get_soup(url)

        series = self._parse_series(
            soup,
            response.url
        )

        if series is None:
            raise MinitokyoNotFound(
                f"Could not parse series page: {response.url}"
            )

        series._client = self

        return series

    # ========================================================
    # Parse search page
    # ========================================================

    def _parse_search_page(
        self,
        soup: BeautifulSoup
    ) -> Optional[Series]:

        """
        Fallback parser for a direct search-result page.

        The normal current Minitokyo flow does not need this,
        because /search redirects to the matching series.
        """

        # Look for a normal Minitokyo page link.
        for a in soup.find_all(
            "a",
            href=True
        ):

            href = a["href"]

            if (
                "minitokyo.net/" in href
                and "/search" not in href
                and "/gallery/" not in href
                and "/view/" not in href
            ):

                text = a.get_text(
                    " ",
                    strip=True
                )

                if not text:
                    continue

                url = urljoin(
                    BASE_URL,
                    href
                )

                try:
                    return self._get_series_from_url(url)

                except MinitokyoError:
                    continue

        return None

    # ========================================================
    # Parse series
    # ========================================================

    def _parse_series(
        self,
        soup: BeautifulSoup,
        url: str
    ) -> Optional[Series]:

        # ----------------------------------------------------
        # Name
        # ----------------------------------------------------

        name = None

        # The page has:
        #
        # <h2>...</h2>
        #
        # and the active tab contains the series name.

        active_tab = soup.select_one(
            "#tabs li.active a"
        )

        if active_tab:
            name = active_tab.get_text(
                " ",
                strip=True
            )

        if not name:

            h1 = soup.find("h1")

            if h1:
                name = h1.get_text(
                    " ",
                    strip=True
                )

                name = re.sub(
                    r"\s*-\s*Wallpaper and Scan Gallery\s*$",
                    "",
                    name,
                    flags=re.I
                )

        if not name:

            title = soup.title

            if title:
                name = title.get_text(
                    " ",
                    strip=True
                )

        if not name:
            return None

        # ----------------------------------------------------
        # tid + category counts
        # ----------------------------------------------------

        tid = None

        wallpaper_count = None
        indy_art_count = None
        scan_count = None

        tabs = soup.select(
            "#tabs a"
        )

        for a in tabs:

            href = a.get("href", "")
            text = a.get_text(
                " ",
                strip=True
            )

            # Example:
            #
            # browse.minitokyo.net/gallery?tid=1446&index=1

            match = re.search(
                r"[?&]tid=(\d+)",
                href
            )

            if not match:
                continue

            current_tid = int(
                match.group(1)
            )

            if tid is None:
                tid = current_tid

            index_match = re.search(
                r"[?&]index=(\d+)",
                href
            )

            if not index_match:
                continue

            index = int(
                index_match.group(1)
            )

            count_match = re.search(
                r"\(([\d,]+)\)",
                text
            )

            count = None

            if count_match:
                count = int(
                    count_match.group(1).replace(
                        ",",
                        ""
                    )
                )

            if index == 1:
                wallpaper_count = count

            elif index == 2:
                indy_art_count = count

            elif index == 3:
                scan_count = count

        # ----------------------------------------------------
        # Tags
        # ----------------------------------------------------

        tags = []

        # Tagged under ...
        for p in soup.select(
            "p"
        ):

            text = p.get_text(
                " ",
                strip=True
            )

            if text.startswith(
                "Tagged under"
            ):

                for a in p.find_all(
                    "a"
                ):

                    tag = a.get_text(
                        " ",
                        strip=True
                    )

                    if tag and tag not in tags:
                        tags.append(tag)

                break

        return Series(
            name=name,
            url=url,
            tid=tid,
            wallpaper_count=wallpaper_count,
            indy_art_count=indy_art_count,
            scan_count=scan_count,
            tags=tags,
            _client=self
        )

    # ========================================================
    # Gallery
    # ========================================================

    def gallery(
        self,
        tid: int,
        category: str = "wallpaper",
        page: int = 1
    ) -> list[ImageItem]:

        """
        Get images from one category.

        category:

            wallpaper
            indy_art
            scan

        Examples:

            mt.gallery(1446, "wallpaper")
            mt.gallery(1446, "indy_art")
            mt.gallery(1446, "scan")
        """

        if tid is None:
            raise ValueError(
                "tid cannot be None"
            )

        if page < 1:
            raise ValueError(
                "page must be >= 1"
            )

        category = self._normalize_category(
            category
        )

        index = CATEGORY_INDEX[
            category
        ]

        params = {
            "tid": tid,
            "index": index,
        }

        # Minitokyo uses page for pagination.
        if page > 1:
            params["page"] = page

        response, soup = self._get_soup(
            f"{BROWSE_URL}/gallery",
            params=params
        )

        return self._parse_gallery(
            soup,
            category
        )

    # ========================================================
    # Gallery by Series
    # ========================================================

    def get_category(
        self,
        series: Series,
        category: str = "wallpaper",
        page: int = 1
    ) -> list[ImageItem]:

        return self.gallery(
            tid=series.tid,
            category=category,
            page=page
        )

    # ========================================================
    # Gallery iterator
    # ========================================================

    def iter_gallery(
        self,
        tid: int,
        category: str = "wallpaper",
        start_page: int = 1
    ) -> Iterator[ImageItem]:

        page = start_page

        while True:

            items = self.gallery(
                tid=tid,
                category=category,
                page=page
            )

            if not items:
                break

            yield from items

            page += 1

    # ========================================================
    # Parse gallery
    # ========================================================

    def _parse_gallery(
        self,
        soup: BeautifulSoup,
        category: str
    ) -> list[ImageItem]:

        results = []

        for li in soup.select(
            "ul.scans > li"
        ):

            # ------------------------------------------------
            # Gallery view URL
            # ------------------------------------------------

            view_link = li.find(
                "a",
                href=re.compile(
                    r"gallery\.minitokyo\.net/view/\d+"
                )
            )

            if not view_link:
                continue

            href = view_link.get(
                "href",
                ""
            )

            id_match = re.search(
                r"/view/(\d+)",
                href
            )

            if not id_match:
                continue

            image_id = int(
                id_match.group(1)
            )

            view_url = urljoin(
                GALLERY_URL,
                href
            )

            # ------------------------------------------------
            # Image / thumbnail
            # ------------------------------------------------

            img = li.find("img")

            thumbnail = None
            resolution = None
            alt = ""

            if img:

                thumbnail = self._clean_url(
                    img.get("src")
                )

                resolution = img.get(
                    "title"
                )

                alt = img.get(
                    "alt",
                    ""
                )

            # ------------------------------------------------
            # Original download URL
            #
            # NOTE: gallery listing pages (ul.scans as returned by
            # /gallery) typically do NOT include a /downloads/ link
            # at all — that's only present on individual /view/{id}
            # pages, and even there it can be corrupted by a
            # server-side PHP warning injected into the href. Don't
            # rely on this being populated; use
            # Minitokyo.download_bytes(image_id) instead when you
            # need the actual file.
            # ------------------------------------------------

            image = None

            download_link = li.find(
                "a",
                href=re.compile(
                    r"/downloads/"
                )
            )

            if download_link:

                image = self._clean_url(
                    download_link.get("href")
                )

            # ------------------------------------------------
            # Title
            # ------------------------------------------------

            title = ""

            p = li.find("p")

            if p:

                # Remove the download link from the text.
                p_copy = BeautifulSoup(
                    str(p),
                    "html.parser"
                )

                for a in p_copy.find_all(
                    "a"
                ):

                    if "/downloads/" in a.get(
                        "href",
                        ""
                    ):
                        a.decompose()

                title = p_copy.get_text(
                    " ",
                    strip=True
                )

            if not title:
                title = alt

            # ------------------------------------------------
            # Author
            # ------------------------------------------------

            author = None

            if p:

                # Sometimes the title contains:
                #
                # "Something by username"
                #
                text = p.get_text(
                    " ",
                    strip=True
                )

                match = re.search(
                    r"\s+by\s+(.+?)\s*$",
                    text,
                    flags=re.I
                )

                if match:
                    author = match.group(1).strip()

            results.append(
                ImageItem(
                    id=image_id,
                    title=title,
                    url=view_url,
                    thumbnail=thumbnail,
                    image=image,
                    resolution=resolution,
                    author=author,
                    category=category,
                )
            )

        return results

    # ========================================================
    # Single image
    # ========================================================

    def get(
        self,
        image_id: int
    ) -> ImageItem:

        """
        Get one image.

        Example:

            image = mt.get(510114)
        """

        url = f"{GALLERY_URL}/view/{image_id}"

        response, soup = self._get_soup(
            url
        )

        # First try the same structure used by galleries.
        items = self._parse_gallery(
            soup,
            category=None
        )

        for item in items:

            if item.id == image_id:

                item.url = response.url

                return item

        # ----------------------------------------------------
        # Fallback parser for individual page
        # ----------------------------------------------------

        item = self._parse_single(
            soup,
            image_id,
            response.url
        )

        if item is None:
            raise MinitokyoNotFound(
                f"Image not found: {image_id}"
            )

        return item

    # ========================================================
    # Parse single image
    # ========================================================

    def _parse_single(
        self,
        soup: BeautifulSoup,
        image_id: int,
        url: str
    ) -> Optional[ImageItem]:

        title = ""

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        h1 = soup.find("h1")

        if h1:
            title = h1.get_text(
                " ",
                strip=True
            )

        if not title and soup.title:

            title = soup.title.get_text(
                " ",
                strip=True
            )

        # ----------------------------------------------------
        # Original image
        # ----------------------------------------------------

        image = None
        thumbnail = None
        resolution = None

        # Download link.
        #
        # NOTE: On individual /view/{id} pages, Minitokyo sometimes
        # injects a PHP warning ("Warning: Undefined array key
        # \"filename\" in ...") directly into this href, e.g.:
        #
        #   <a href="
        #   Warning: Undefined array key "filename" in ...
        #   http://static.minitokyo.net/downloads/40/35/509290.jpg"
        #    onclick="window.location = '/download/509290'; ...">
        #
        # _clean_url() below strips that garbage out, but if it
        # still fails for any reason, fall back to
        # Minitokyo.download_bytes(image_id), which hits Minitokyo's
        # own /download/{id} redirect endpoint directly instead of
        # scraping this link.
        for a in soup.find_all(
            "a",
            href=True
        ):

            href = a["href"]

            if (
                "/downloads/" in href
                and str(image_id) in href
            ):

                image = self._clean_url(
                    href
                )

                break

        # ----------------------------------------------------
        # Image tags
        # ----------------------------------------------------

        for img in soup.find_all(
            "img"
        ):

            src = img.get(
                "src"
            )

            if not src:
                continue

            src = self._clean_url(
                src
            )

            if str(image_id) not in src:
                continue

            if "/thumbs/" in src:
                thumbnail = src

            elif image is None:
                image = src

            if not resolution:

                resolution = img.get(
                    "title"
                )

        # ----------------------------------------------------
        # Find category
        # ----------------------------------------------------

        category = None

        page_text = soup.get_text(
            " ",
            strip=True
        ).lower()

        if "wallpaper" in page_text:
            category = "wallpaper"

        elif "indy art" in page_text:
            category = "indy_art"

        elif "scan" in page_text:
            category = "scan"

        # ----------------------------------------------------
        # If nothing related to the ID was found
        # ----------------------------------------------------

        if (
            image is None
            and thumbnail is None
        ):
            return None

        return ImageItem(
            id=image_id,
            title=title,
            url=url,
            thumbnail=thumbnail,
            image=image,
            resolution=resolution,
            category=category,
        )

    # ========================================================
    # Download original bytes (robust, does not depend on
    # scraping a /downloads/ link out of the page HTML)
    # ========================================================

    def download_bytes(
        self,
        image_id: int,
        referer: str = "http://www.minitokyo.net/",
    ) -> bytes:

        """
        Fetch the original image bytes for a given image ID using
        Minitokyo's own download redirect endpoint:

            http://www.minitokyo.net/download/{id}

        This is the same endpoint the site's own "Download" button
        uses (see the onclick handler on individual /view/{id}
        pages: `window.location = '/download/{id}'`). It sidesteps
        both:

          - gallery listing pages, which usually don't expose a
            /downloads/ link in their HTML at all, and
          - individual /view/{id} pages, where the /downloads/ link
            can be corrupted by a PHP warning Minitokyo sometimes
            injects into the href.

        Example:

            data = mt.download_bytes(509290)
            with open("509290.jpg", "wb") as f:
                f.write(data)
        """

        if image_id is None:
            raise ValueError("image_id cannot be None")

        url = f"{BASE_URL}/download/{image_id}"

        response = self._request(
            "GET",
            url,
            headers={"Referer": referer},
            allow_redirects=True,
        )

        return response.content

    # ========================================================
    # Category helper
    # ========================================================

    @staticmethod
    def _normalize_category(
        category: str
    ) -> str:

        if not isinstance(
            category,
            str
        ):
            raise ValueError(
                "category must be a string"
            )

        key = category.strip().lower()

        if key not in CATEGORY_ALIASES:
            raise ValueError(
                "Unknown category: "
                f"{category!r}. "
                "Use 'wallpaper', 'indy_art', or 'scan'."
            )

        return CATEGORY_ALIASES[key]

    # ========================================================
    # URL helper
    # ========================================================

    @staticmethod
    def _clean_url(
        url: Optional[str]
    ) -> Optional[str]:

        if not url:
            return None

        url = url.strip()

        # Markdown-style URLs can appear when HTML has been
        # converted to Markdown.
        #
        # [http://example.com](...)
        match = re.match(
            r"^\[([^\]]+)\]",
            url
        )

        if match:
            url = match.group(1)

        # Minitokyo sometimes injects a PHP warning directly into
        # an href attribute, e.g.:
        #
        #   "\nWarning: Undefined array key \"filename\" in
        #    /var/www/minitokyo/www/html2/view.html on line 37
        #    \nhttp://static.minitokyo.net/downloads/40/35/509290.jpg"
        #
        # Extract only the actual http(s) URL portion, ignoring any
        # surrounding garbage. If more than one URL-looking token is
        # present, the last one is used (the real link tends to come
        # after any injected warning text).
        matches = re.findall(
            r"https?://\S+",
            url
        )

        if matches:
            url = matches[-1]

        # Remove accidental whitespace.
        url = url.strip()

        return url
