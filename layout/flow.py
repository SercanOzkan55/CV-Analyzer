from __future__ import annotations

from typing import Iterable, List

from .block import Block


def flow_blocks(blocks: Iterable[Block], page_height: float, top: float = 0.0) -> List[List[Block]]:
    pages: List[List[Block]] = []
    current: List[Block] = []
    used = top

    for block in blocks:
        if used + block.height > page_height and current:
            pages.append(current)
            current = []
            used = top
        current.append(block)
        used += block.height

    if current:
        pages.append(current)

    return pages
