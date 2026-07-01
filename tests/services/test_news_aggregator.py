import pytest
from app.core.utils import strip_html as _strip_html

def test_strip_html():
    assert _strip_html("<b>bold</b> text") == "bold text"
