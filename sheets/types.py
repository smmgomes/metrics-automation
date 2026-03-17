from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal, NamedTuple, TypedDict


class Recency(Enum):
    week1 = "week1"
    week2 = "week2"
    month = "month"


class ColumnRange(NamedTuple):
    start: str
    end: str


@dataclass
class HistoricalMetrics:
    date: datetime
    title: str
    week1: list[int | str]
    week2: list[int | str]
    month: list[int | str]


type HistoricalMetricsMap = dict[str, HistoricalMetrics]
type FollowerCounts = list[list[int]]


class UpdatePayload(TypedDict):
    range: str
    values: list[list[Any]]


COLUMN_RANGES: dict[Recency | Literal["metadata", "all_range"], ColumnRange] = {
    "metadata": ColumnRange(start="A", end="C"),
    "all_range": ColumnRange(start="A", end="X"),
    Recency.week1: ColumnRange(start="D", end="J"),
    Recency.week2: ColumnRange(start="K", end="Q"),
    Recency.month: ColumnRange(start="R", end="X"),
}
