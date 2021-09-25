from datetime import datetime, timedelta
import email
import re
from typing import Optional
import urllib.request
import urllib.error

from bs4 import BeautifulSoup  # type: ignore
from imapclient import IMAPClient  # type: ignore

URL_PATTERN = re.compile(r"(?P<url>https?://[^\s]+)")
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:92.0) Gecko/20100101 Firefox/92.0"

RR_PATTERN = re.compile(
    r"https://www\.royalroad\.com/fiction/(?P<id>\d+)/.*/chapter/\d+/.*"
)
STORY_TITLE_PATTERN = re.compile(
    r"has just posted a new chapter of (?P<title>.*) titled .*"
)


def fetch_unprocessed(imap_client):
    messages = imap_client.search(
        ["UNSEEN", "SUBJECT", "New Chapter of", "FROM", "noreply@royalroad.com"]
    )
    for uid, data in imap_client.fetch(messages, ["ENVELOPE", "RFC822"]).items():
        envelope = data[b"ENVELOPE"]
        email_message = email.message_from_bytes(data[b"RFC822"])

        # Quoted-printable bit me in the ass, gotta decode the payload
        # We're just assuming that it's UTF-8 encoded, this will likely bite me in the ass
        # at some future point too
        body = email_message.get_payload(0).get_payload(decode=True).decode("utf-8")
        if match := STORY_TITLE_PATTERN.search(body):
            title = match.group("title")
        else:
            title = "New Story"
        try:
            if match := URL_PATTERN.search(body):
                email_url = match.group("url")
                req = urllib.request.Request(
                    email_url, data=None, headers={"User-Agent": USER_AGENT}
                )
                with urllib.request.urlopen(req) as f:
                    if sub_match := RR_PATTERN.match(f.url):
                        yield (sub_match.group("id"), title)
        except urllib.error.URLError:
            # 2021-09-01 was sent an email with href of "v2c58: Growing by Mileslink"
            pass
