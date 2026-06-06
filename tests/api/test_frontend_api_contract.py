from __future__ import annotations

import re
from pathlib import Path

from app.main import app


FRONTEND = Path("frontend.html")


def _frontend_source() -> str:
    return FRONTEND.read_text(encoding="utf-8")


def _frontend_api_paths() -> set[str]:
    html = _frontend_source()
    patterns = [
        r"fetch\(\s*\"([^\"]+)\"",
        r"request\(\s*\"([^\"]+)\"",
        r"request\(\s*`([^`?]+)",
        r"EventSource\(\"([^\"]+)\"",
    ]
    paths: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, html):
            path = match.group(1).split("?", 1)[0]
            paths.add(path)
    return paths


def _route_templates() -> set[str]:
    return {
        getattr(route, "path", "")
        for route in app.routes
        if getattr(route, "path", "").startswith("/")
    }


def _template_matches(route_template: str, concrete_path: str) -> bool:
    if "${" in concrete_path:
        concrete_esc = re.escape(concrete_path)
        concrete_pattern = "^" + re.sub(r"\\\$\\\{[^}]+\\\}", r"/?[^/]*", concrete_esc) + "$"
        route_filled = re.sub(r"\{[^}]+\}", "param", route_template)
        return re.match(concrete_pattern, route_filled) is not None

    escaped = re.escape(route_template)
    pattern = re.sub(r"\\\{[^}]+\\\}", r"[^/]+", escaped)
    concrete = re.sub(r"\$\{[^}]+\}", "placeholder", concrete_path)
    return re.fullmatch(pattern, concrete) is not None


def test_all_literal_frontend_api_paths_have_backend_routes():
    routes = _route_templates()
    missing = []

    for path in sorted(_frontend_api_paths()):
        if any(_template_matches(route, path) for route in routes):
            continue
        missing.append(path)

    assert missing == []
