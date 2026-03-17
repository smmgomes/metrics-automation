from typing import Literal, NotRequired, TypedDict
from dataclasses import dataclass
from datetime import datetime


type APIInsightValue = list[dict[Literal["value"], int]]
type APICursors = dict[Literal["after", "before"], str]


class APIInsightNode(TypedDict):
    description: str
    id: str
    name: str
    period: str
    title: str
    values: APIInsightValue


class APIInsightsList(TypedDict):
    data: list[APIInsightNode]


class APIMediaNode(TypedDict):
    caption: str
    id: str
    insights: APIInsightsList
    permalink: str
    timestamp: str


class APIPagingNode(TypedDict):
    cursors: APICursors


class APIMediaList(TypedDict):
    data: list[APIMediaNode]
    paging: APIPagingNode


class APIUserMediaResponse(TypedDict):
    followers_count: int
    id: str
    media: APIMediaList


class PostMetrics(TypedDict):
    comments: int
    follows: NotRequired[int]
    likes: int
    reach: int
    shares: int
    total_interactions: int
    views: int


@dataclass
class ProcessedPost:
    id: str
    metrics: PostMetrics
    timestamp: datetime
    identifier: tuple[str, str]


type ExtractedMediaPayload = tuple[list[ProcessedPost], int]
