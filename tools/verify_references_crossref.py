# -*- coding: utf-8 -*-
"""Print authoritative Crossref metadata for manuscript references with DOIs."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request


DOIS = {
    1: "10.1126/science.1185231",
    5: "10.1145/3586183.3606763",
    6: "10.1057/s41599-024-03611-3",
    7: "10.18653/v1/2024.findings-naacl.211",
    8: "10.18653/v1/2024.acl-long.554",
    9: "10.1057/s41599-024-03609-x",
    10: "10.3390/systems13010029",
    11: "10.1007/s10462-025-11412-6",
    12: "10.1038/30918",
    13: "10.1126/science.286.5439.509",
    14: "10.1126/science.aap9559",
    15: "10.1145/956750.956769",
    16: "10.1007/s11704-026-60308-3",
}


def first(message: dict, key: str):
    value = message.get(key)
    return value[0] if isinstance(value, list) and value else value


for number, doi in DOIS.items():
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    request = urllib.request.Request(url, headers={"User-Agent": "LEDS-reference-audit/1.0 (mailto:research@example.invalid)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        message = json.load(response)["message"]
    issued = first(message, "issued") or {}
    date_parts = first(issued, "date-parts") or []
    record = {
        "reference": number,
        "doi": message.get("DOI", doi),
        "title": first(message, "title"),
        "container": first(message, "container-title"),
        "year": date_parts[0] if date_parts else None,
        "volume": message.get("volume"),
        "issue": message.get("issue"),
        "page_or_article": message.get("page") or message.get("article-number"),
        "published_online": message.get("published-online"),
        "published_print": message.get("published-print"),
    }
    print(json.dumps(record, ensure_ascii=False))
