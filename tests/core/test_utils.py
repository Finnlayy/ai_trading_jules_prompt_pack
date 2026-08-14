import pytest
from app.core.utils import iso_from_pubdate

def test_iso_from_pubdate_rss_format():
    """Test standard RSS pubDate format."""
    text = "Mon, 06 Sep 2009 16:20:00 +0000"
    expected = "2009-09-06T16:20:00+00:00"
    assert iso_from_pubdate(text) == expected

def test_iso_from_pubdate_gmt_suffix():
    """Test RSS pubDate format with GMT suffix."""
    text = "Mon, 06 Sep 2009 16:20:00 GMT"
    expected = "2009-09-06T16:20:00+00:00"
    assert iso_from_pubdate(text) == expected

def test_iso_from_pubdate_iso_format():
    """Test standard ISO-like date string."""
    text = "2009-09-06T16:20:00"
    expected = "2009-09-06T16:20:00+00:00"
    assert iso_from_pubdate(text) == expected

def test_iso_from_pubdate_iso_format_with_trailing():
    """Test ISO-like date string with trailing chars (e.g., timezone/milliseconds)."""
    text = "2009-09-06T16:20:00.123Z"
    expected = "2009-09-06T16:20:00+00:00"
    assert iso_from_pubdate(text) == expected

def test_iso_from_pubdate_unparsable():
    """Test unparsable string fallback."""
    text = "unparsable date string"
    assert iso_from_pubdate(text) == text

def test_iso_from_pubdate_whitespace():
    """Test stripping whitespace."""
    text = "  Mon, 06 Sep 2009 16:20:00 +0000  "
    expected = "2009-09-06T16:20:00+00:00"
    assert iso_from_pubdate(text) == expected
