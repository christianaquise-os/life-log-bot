from dataclasses import dataclass


@dataclass
class Session:
    id: int
    chat_id: int
    pillar: str
    sub_track: str | None
    activity_name: str
    raw_text: str
    source_intent: str
    start_ts: str
    end_ts: str | None
    duration_seconds: int | None
    status: str
    notion_page_id: str | None

    @classmethod
    def from_row(cls, row) -> "Session":
        return cls(
            id=row["id"],
            chat_id=row["chat_id"],
            pillar=row["pillar"],
            sub_track=row["sub_track"],
            activity_name=row["activity_name"],
            raw_text=row["raw_text"],
            source_intent=row["source_intent"],
            start_ts=row["start_ts"],
            end_ts=row["end_ts"],
            duration_seconds=row["duration_seconds"],
            status=row["status"],
            notion_page_id=row["notion_page_id"],
        )


@dataclass
class PendingAction:
    id: int
    chat_id: int
    kind: str
    payload: dict

    @classmethod
    def from_row(cls, row) -> "PendingAction":
        import json

        return cls(
            id=row["id"],
            chat_id=row["chat_id"],
            kind=row["kind"],
            payload=json.loads(row["payload_json"]),
        )
