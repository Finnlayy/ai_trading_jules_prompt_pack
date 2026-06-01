import pytest
from app.services.news_aggregator import _strip_html

def test_strip_html():
    assert _strip_html("<b>bold</b> text") == "bold text"
