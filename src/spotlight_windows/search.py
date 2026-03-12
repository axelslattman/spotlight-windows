# search.py – orchestrates the search pipeline.
#
# Search priority (in order):
#   1. Apps     – Start Menu shortcuts, weighted higher than files
#   2. Files    – documents, downloads, desktop, extra configured folders
#   3. Calculator – if the query looks like math, evaluate and show result
#   4. Web fallback – always shown last if nothing else matches
#
# This module defines a SearchResult dataclass and a SearchService class
# that the UI calls with the current query string.

import urllib.parse   # For URL-encoding the search query (spaces → %20, etc.)
from dataclasses import dataclass
from enum import Enum, auto  # Enum lets us define a fixed set of named values
from typing import Optional

from . import calculator
from .config import Config
from .indexer import FileIndexer, IndexedEntry


class ResultKind(Enum):
    """The category of a search result, used by the UI to pick an icon."""
    APP  = auto()  # auto() assigns an automatic integer value (1, 2, 3, ...)
    FILE = auto()
    CALC = auto()
    WEB  = auto()


@dataclass
class SearchResult:
    """One item in the search results list."""
    title: str            # Primary text shown (app name, filename, math result, etc.)
    subtitle: str         # Secondary text shown in smaller font (path, expression, etc.)
    kind: ResultKind      # Determines which icon to show
    path: Optional[str]   # Filesystem path to open, or None for CALC/WEB results
    url: Optional[str]    # URL to open for WEB results, or None otherwise


def _score(entry: IndexedEntry, query: str) -> int:
    """Return a relevance score for this index entry against the query.

    Higher score = more relevant. Returns 0 if the entry doesn't match at all.

    Scoring rules (you can adjust these numbers to tune ranking):
    - Name starts with query (case-insensitive): highest score
    - Name contains query:                       medium score
    - Apps get a bonus over plain files so apps rank above files
    """
    name_lower = entry.name.lower()
    query_lower = query.lower()

    if query_lower not in name_lower:
        return 0  # Doesn't match at all – exclude from results

    score = 0

    if name_lower.startswith(query_lower):
        score += 100  # Prefix match is most relevant
    else:
        score += 50   # Substring match

    if entry.is_app:
        score += 20   # Apps rank above files with the same match quality

    return score


class SearchService:
    """Takes a query string and returns an ordered list of SearchResult objects.

    Designed to be called on every keystroke, so it must be fast.
    The actual filesystem walking is done by FileIndexer in the background;
    SearchService only filters and scores the already-built in-memory list.
    """

    def __init__(self, indexer: FileIndexer, cfg: Config) -> None:
        # We store references to the indexer and config so we can use them
        # in search(). In Python, storing something in self.<name> makes it
        # accessible from any method on this object.
        self._indexer = indexer
        self._cfg = cfg

    def search(self, query: str) -> list[SearchResult]:
        """Return sorted search results for the given query string.

        Returns an empty list if the query is empty.
        """
        query = query.strip()
        if not query:
            return []

        results: list[SearchResult] = []

        # --- 1. Calculator (check this first so it appears at the top) ---
        calc_answer = calculator.evaluate(query)
        if calc_answer is not None:
            results.append(SearchResult(
                title=calc_answer,
                subtitle=f"= {query}",     # Show the original expression as a hint
                kind=ResultKind.CALC,
                path=None,
                url=None,
            ))

        # --- 2. Apps and Files (scored and ranked together) ---
        # indexer.entries returns a snapshot of the current index.
        # We score every entry and keep only those with score > 0.
        scored: list[tuple[int, IndexedEntry]] = []
        for entry in self._indexer.entries:
            score = _score(entry, query)
            if score > 0:
                # Tuples of (score, entry) so we can sort by score
                scored.append((score, entry))

        # Sort by score descending: highest relevance first.
        # The `-` in key=-s gives us descending order (highest first).
        scored.sort(key=lambda pair: -pair[0])

        # Take at most max_results entries (leaving room for calc + web results)
        # max(0, ...) ensures we don't get a negative slice limit
        file_slots = max(0, self._cfg.max_results - len(results) - 1)
        for score, entry in scored[:file_slots]:
            kind = ResultKind.APP if entry.is_app else ResultKind.FILE
            results.append(SearchResult(
                title=entry.name,
                subtitle=entry.path,
                kind=kind,
                path=entry.path,
                url=None,
            ))

        # --- 3. Web fallback (always last if we have room) ---
        # Show "Search Google for …" regardless of whether we found other results.
        if len(results) < self._cfg.max_results:
            # urllib.parse.quote() URL-encodes the query: "hello world" → "hello%20world"
            encoded_query = urllib.parse.quote(query)
            url = self._cfg.web_search_url.format(encoded_query)
            results.append(SearchResult(
                title=f'Search Google for "{query}"',
                subtitle=url,
                kind=ResultKind.WEB,
                path=None,
                url=url,
            ))

        return results
