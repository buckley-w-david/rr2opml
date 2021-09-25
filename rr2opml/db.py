import contextlib
from typing import Optional, Tuple

import sqlalchemy  # type: ignore
from sqlalchemy import create_engine  # type: ignore
from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    MetaData,
    ForeignKey,
    Boolean,
    DateTime,
)  # type: ignore
from sqlalchemy.sql import text, select  # type: ignore

from rr2opml.models import Story

metadata = MetaData()
stories = Table(
    "stories",
    metadata,
    Column("story_id", Integer, primary_key=True),
    Column("royalroad_id", Integer, nullable=False),
    Column("title", String, nullable=False),
    Column("feed_url", String, nullable=False),
)


@contextlib.contextmanager
def connect(connection_string: str) -> sqlalchemy.engine.Connection:
    engine = create_engine(connection_string)
    metadata.create_all(engine)
    try:
        with engine.connect() as conn:
            yield conn
    finally:
        engine.dispose()


def add_story(conn, story: Story) -> int:
    result = conn.execute(
        stories.insert(),
        **story.dict()
    )
    return result.inserted_primary_key[0]


def get_stories(conn):
    s = select(stories)
    return conn.execute(s).fetchall()

def story_id_from_rr_id(conn, rr_id):
    s = select(stories.c.story_id).where(stories.c.royalroad_id == rr_id)
    result = conn.execute(s).fetchone()
    return result[0] if result else None

