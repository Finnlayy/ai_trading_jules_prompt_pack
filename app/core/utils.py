import asyncio
import json
from datetime import datetime, timezone
from typing import Any, List, Optional
from sqlalchemy.orm import Session

def strip_html(text: str) -> str:
    """Very basic HTML tag stripper."""
    result = []
    in_tag = False
    for ch in text or "":
        if ch == "<":
            in_tag = True
        elif ch == ">":
            in_tag = False
        elif not in_tag:
            result.append(ch)
    return "".join(result).strip()

def json_dumps_default(obj: Any) -> Any:
    """Default handler for json.dumps."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return str(obj)

def json_dumps(payload: Any, **kwargs: Any) -> str:
    """Safely dumps JSON with standard default handler."""
    kwargs.setdefault("default", json_dumps_default)
    return json.dumps(payload, **kwargs)

async def write_json_async(filepath: str, payload: Any, indent: int = 2) -> None:
    """Writes a JSON file asynchronously."""
    def _write():
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json_dumps(payload, indent=indent))
    await asyncio.to_thread(_write)

async def append_jsonl_async(filepath: str, payload: Any) -> None:
    """Appends a line to a JSONL file asynchronously."""
    def _write():
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json_dumps(payload) + "\n")
    await asyncio.to_thread(_write)

def execute_with_db(func, *args, **kwargs):
    from app.db import get_db
    gen = get_db()
    db = next(gen)
    try:
        return func(db, *args, **kwargs)
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

def iso_from_pubdate(text: str) -> str:
    """Best-effort parse of RSS pubDate to ISO."""
    t = text.strip()
    # Handle GMT suffix by replacing with +0000
    if t.endswith(" GMT"):
        t = t[:-4] + " +0000"
    # RSS pubDate format: Mon, 06 Sep 2009 16:20:00 +0000
    try:
        dt = datetime.strptime(t, "%a, %d %b %Y %H:%M:%S %z")
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass
    try:
        dt = datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        pass
    return text
