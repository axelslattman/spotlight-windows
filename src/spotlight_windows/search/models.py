from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ResultType(str, Enum):
    CALCULATOR = "calculator"
    APPLICATION = "application"
    FILE = "file"
    FOLDER = "folder"
    RECENT = "recent"


@dataclass
class SearchResult:
    title: str
    subtitle: str
    result_type: ResultType
    target: str
    score: float
    action: str = "open"
