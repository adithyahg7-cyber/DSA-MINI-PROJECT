from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    username: str
    name: str
    salt: str
    password_hash: str
    role: str = "student"
    bio: str = ""
    created_at: float = 0.0
    avatar: Optional[str] = None


@dataclass
class PostMedia:
    media_id: int
    post_id: int
    path: str
    uploader: str
    created_at: float


@dataclass
class Post:
    post_id: int
    author: str
    text: str
    created_at: float
    community_id: Optional[int] = None
    media: list = field(default_factory=list)


@dataclass
class Comment:
    comment_id: int
    post_id: int
    author: str
    text: str
    created_at: float
    parent_id: Optional[int] = None


@dataclass
class Notification:
    notification_id: int
    username: str
    text: str
    created_at: float
    is_read: bool = False


@dataclass
class Event:
    event_id: int
    title: str
    description: str
    date: str
    time: str
    venue: str
    organiser: str
    community_id: Optional[int] = None


@dataclass
class Media:
    media_id: int
    event_id: int
    path: str
    uploader: str
    created_at: float


@dataclass
class Pitch:
    pitch_id: int
    proposer: str
    title: str
    description: str
    status: str
    created_at: float
    decided_by: Optional[str] = None
    decided_at: Optional[float] = None


@dataclass
class Community:
    community_id: int
    name: str
    kind: str
    visibility: str
    owner: str
    created_at: float


@dataclass
class Message:
    message_id: int
    sender: str
    receiver: str
    text: str
    created_at: float
    is_read: bool = False


@dataclass
class Report:
    report_id: int
    post_id: int
    reporter: str
    reason: str
    status: str
    created_at: float
    decided_by: Optional[str] = None
    decided_at: Optional[float] = None
