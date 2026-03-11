from __future__ import annotations

import sqlite3
from pathlib import Path

from rapidfuzz import fuzz

from spotlight_windows.calculator import maybe_calculate
from spotlight_windows.config import AppSettings
from spotlight_windows.search.app_discovery import AppDiscovery
from spotlight_windows.search.models import ResultType, SearchResult


class SearchService:
    def __init__(self, db_path: Path, settings: AppSettings, app_discovery: AppDiscovery) -> None:
        self.db_path = db_path
        self.settings = settings
        self.app_discovery = app_discovery

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return self._recent_results()

        results: list[SearchResult] = []
        calc = maybe_calculate(query)
        if calc is not None:
            calc_str = ("{:.8f}".format(calc)).rstrip("0").rstrip(".")
            results.append(
                SearchResult(
                    title=f"{query} = {calc_str}",
                    subtitle="Press Enter to copy result",
                    result_type=ResultType.CALCULATOR,
                    target=calc_str,
                    score=200.0,
                    action="copy",
                )
            )

        results.extend(self._search_apps(query))
        results.extend(self._search_files(query))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[: self.settings.max_results]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _search_files(self, query: str) -> list[SearchResult]:
        terms = " ".join(token for token in query.split() if token)
        rows = []
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT files.path, files.name, files.snippet,
                           bm25(file_fts, 1.2, 0.7, 0.4) AS rank
                    FROM file_fts
                    JOIN files ON files.id = file_fts.rowid
                    WHERE file_fts MATCH ?
                    ORDER BY rank
                    LIMIT 20
                    """,
                    (terms if terms else query,),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    """
                    SELECT path, name, snippet, 1.0 AS rank
                    FROM files
                    WHERE name LIKE ? OR path LIKE ?
                    ORDER BY modified DESC
                    LIMIT 20
                    """,
                    (f"%{query}%", f"%{query}%"),
                ).fetchall()
        results = []
        for row in rows:
            name = row["name"]
            fuzzy_bonus = fuzz.WRatio(query, name) / 8
            score = 100 - float(row["rank"]) + fuzzy_bonus
            subtitle = row["snippet"] or row["path"]
            result_type = ResultType.FOLDER if Path(row["path"]).is_dir() else ResultType.FILE
            results.append(
                SearchResult(
                    title=name,
                    subtitle=subtitle,
                    result_type=result_type,
                    target=row["path"],
                    score=score,
                )
            )
        return results

    def _search_apps(self, query: str) -> list[SearchResult]:
        results: list[SearchResult] = []
        for app in self.app_discovery.all_apps():
            ratio = fuzz.WRatio(query.lower(), app.title.lower())
            if ratio < 45:
                continue
            results.append(
                SearchResult(
                    title=app.title,
                    subtitle=app.subtitle,
                    result_type=ResultType.APPLICATION,
                    target=app.target,
                    score=ratio + 40,
                )
            )
        return sorted(results, key=lambda item: item.score, reverse=True)[:8]

    def _recent_results(self) -> list[SearchResult]:
        return [
            SearchResult(
                title=Path(item).name,
                subtitle=item,
                result_type=ResultType.RECENT,
                target=item,
                score=60 - index,
            )
            for index, item in enumerate(self.settings.recent_items[:8])
        ]
