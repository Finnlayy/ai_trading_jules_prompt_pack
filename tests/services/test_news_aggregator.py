import pytest
from app.services.news_aggregator import NewsAggregator, _iso_from_pubdate, _strip_html, _parse_rss
from datetime import datetime, timezone

def test_iso_from_pubdate_rss_format():
    pubdate = "Mon, 06 Sep 2009 16:20:00 +0000"
    iso = _iso_from_pubdate(pubdate)
    assert iso == "2009-09-06T16:20:00+00:00"

def test_iso_from_pubdate_gmt():
    pubdate = "Mon, 06 Sep 2009 16:20:00 GMT"
    iso = _iso_from_pubdate(pubdate)
    assert iso == "2009-09-06T16:20:00+00:00"

def test_strip_html():
    html_text = "<p>This is a <b>test</b>.</p>"
    stripped = _strip_html(html_text)
    assert stripped == "This is a test."

def test_parse_rss_valid_xml():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <item>
                <title>Test Title</title>
                <link>http://example.com</link>
                <pubDate>Mon, 06 Sep 2009 16:20:00 +0000</pubDate>
                <description>Test Description</description>
            </item>
        </channel>
    </rss>
    """
    items = _parse_rss(xml, "Test Source")
    assert len(items) == 1
    assert items[0].title == "Test Title"
    assert items[0].link == "http://example.com"
    assert items[0].summary == "Test Description"
    assert items[0].source == "Test Source"

@pytest.mark.asyncio
async def test_news_aggregator_fetch_mocked(monkeypatch):
    class MockResponse:
        def __init__(self, content):
            self.content = content
        def raise_for_status(self):
            pass

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            self.is_closed = False
        async def get(self, url):
            xml = b"""<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0">
                <channel>
                    <item>
                        <title>Test Title</title>
                        <link>http://example.com</link>
                        <pubDate>Mon, 06 Sep 2009 16:20:00 +0000</pubDate>
                        <description>Test Description</description>
                    </item>
                </channel>
            </rss>
            """
            return MockResponse(xml)
        async def aclose(self):
            self.is_closed = True

    monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)

    aggregator = NewsAggregator()
    items = await aggregator.fetch(source="bbc")

    assert len(items) == 1
    assert items[0].title == "Test Title"

    cached = aggregator.get_cached()
    assert len(cached) == 1

    last_fetch = aggregator.last_fetch_iso()
    assert last_fetch is not None

    await aggregator.close()


def test_iso_from_pubdate_invalid():
    pubdate = "Invalid Date String"
    iso = _iso_from_pubdate(pubdate)
    assert iso == "Invalid Date String"

def test_iso_from_pubdate_iso8601():
    pubdate = "2023-10-27T10:00:00Z"
    iso = _iso_from_pubdate(pubdate)
    assert iso == "2023-10-27T10:00:00+00:00"

def test_strip_html_none():
    assert _strip_html(None) == ""

def test_strip_html_no_tags():
    assert _strip_html("No tags here") == "No tags here"

def test_parse_rss_invalid_xml():
    xml = b"invalid xml"
    items = _parse_rss(xml, "Test Source")
    assert items == []

def test_parse_rss_atom_feed():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <title>Atom Title</title>
            <link href="http://atom.example.com" />
            <published>2023-10-27T10:00:00Z</published>
            <summary>Atom Summary</summary>
        </entry>
    </feed>
    """
    items = _parse_rss(xml, "Atom Source")
    assert len(items) == 1
    assert items[0].title == "Atom Title"
    assert items[0].link == "http://atom.example.com"
    assert items[0].summary == "Atom Summary"
    assert items[0].source == "Atom Source"

@pytest.mark.asyncio
async def test_news_aggregator_fetch_error_handling(monkeypatch):
    class MockAsyncClientError:
        def __init__(self, *args, **kwargs):
            self.is_closed = False
        async def get(self, url):
            raise Exception("Network error")
        async def aclose(self):
            self.is_closed = True

    monkeypatch.setattr("httpx.AsyncClient", MockAsyncClientError)

    aggregator = NewsAggregator()
    items = await aggregator.fetch(source="all")

    assert len(items) == 0
    await aggregator.close()
from app.core.utils import strip_html as _strip_html

def test_strip_html():
    assert _strip_html("<b>bold</b> text") == "bold text"
