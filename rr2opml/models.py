from pydantic import BaseModel, HttpUrl


class Story(BaseModel):
    royalroad_id: int
    feed_url: HttpUrl
    title: str
