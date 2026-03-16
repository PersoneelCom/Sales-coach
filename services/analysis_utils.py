from __future__ import annotations

import re
from typing import Optional


SECTION_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def split_markdown_sections(markdown: str) -> dict[str, str]:
    matches = list(SECTION_PATTERN.finditer(markdown))
    sections: dict[str, str] = {}

    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[title] = markdown[start:end].strip()

    return sections


def extract_score_value(score_section: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", score_section)
    if match:
        return float(match.group(1))
    return None


def extract_first_bullet(section_text: str) -> str:
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            return stripped[2:].strip()
        if stripped:
            return stripped
    return ""


def markdown_section_items(section_text: str) -> list[str]:
    items: list[str] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
        else:
            items.append(stripped)
    return items


def top_section_items(section_text: str, limit: int = 3) -> list[str]:
    return markdown_section_items(section_text)[:limit]
