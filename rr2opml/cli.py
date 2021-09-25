from datetime import datetime, timedelta
from imaplib import IMAP4
import logging
import re
from typing import Optional, List, Protocol
from pathlib import Path
from urllib.parse import urljoin, quote

from bs4 import BeautifulSoup  # type: ignore
from imapclient import IMAPClient  # type: ignore
import typer

import opml.writer
import opml.models

from rr2opml import db
from rr2opml import email
from rr2opml.config import Rr2OpmlConfig
from rr2opml.models import Story

# Email RFC
# https://datatracker.ietf.org/doc/html/rfc3501

# TODO configurable log level
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_new_stories(db_conn, imap_client):
    for royalroad_id, title in email.fetch_unprocessed(imap_client):
        story_id = db.story_id_from_rr_id(db_conn, royalroad_id)
        if story_id is None:
            story = Story(
                royalroad_id=int(royalroad_id),
                title=title,
                feed_url=f"https://www.royalroad.com/syndication/{royalroad_id}",
            )
            story_id = db.add_story(db_conn, story)


def write_opml(db_conn, feed_dir: Path):
    opml_version = opml.models.Version.VERSION2
    opml_head = opml.models.Head()
    outlines = []
    for story_row in db.get_stories(db_conn):
        story_id = story_row.story_id
        story = Story(**story_row._mapping)
        outlines.append(
            opml.models.Outline(
                text=story.title,
                attributes={
                    "type": "rss",
                    "xmlUrl": story.feed_url,
                },
            )
        )

    updated_opml = opml.models.Opml(
        version=opml_version, head=opml_head, body=opml.models.Body(outlines=outlines)
    )
    opml.writer.write(str(feed_dir / "subscriptions.xml"), updated_opml)


app = typer.Typer()


@app.command()
def touch(config_file: Path = Path("rr2opml.toml")):
    if not config_file.exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config = Rr2OpmlConfig()  # Creates a config structure with default values
        config.dump(config_file)


@app.command()
def update(config_file: Path = Path("rr2opml.toml")):
    touch(config_file)
    config = Rr2OpmlConfig.load(config_file)

    feed_dir = Path(config.feeds_directory)
    feed_dir.mkdir(parents=True, exist_ok=True)

    with db.connect(config.db) as conn, IMAPClient(host=config.host) as client:
        client.login(config.username, config.password)
        client.select_folder(config.folder)

        fetch_new_stories(conn, client)
        write_opml(conn, feed_dir)


@app.command()
def serve(config_file: Path = Path("rr2opml.toml")):
    touch(config_file)
    config = Rr2OpmlConfig.load(config_file)

    feed_dir = Path(config.feeds_directory)
    feed_dir.mkdir(parents=True, exist_ok=True)

    with db.connect(config.db) as conn, IMAPClient(host=config.host) as client:
        client.login(config.username, config.password)
        client.select_folder(config.folder)

        fetch_new_stories(conn, client)
        write_opml(conn, feed_dir)

        # Switch to idle mode and handle events as they come in
        while True:
            # > clients using IDLE are advised to terminate the IDLE and re-issue it at least every 29 minutes to avoid being logged off
            # https://datatracker.ietf.org/doc/html/rfc2177.html
            reset = datetime.now() + timedelta(minutes=10)
            try:
                client.idle()
                while datetime.now() < reset:
                    # Wait for up to 30 seconds for an IDLE response
                    responses = client.idle_check(timeout=30)
                    if responses and responses != [(b"OK", b"Still here")]:
                        # You're not allowed to send the server other stuff while idling
                        # FIXME: while the new messages are fetched, new incoming ones aren't discovered!
                        # This isn't too big a deal since they would be picked up at the next update
                        client.idle_done()
                        fetch_new_stories(conn, client)
                        client.idle()

                        write_opml(conn, feed_dir)
            except IMAP4.error:
                pass
            finally:
                client.idle_done()


if __name__ == "__main__":
    app()
