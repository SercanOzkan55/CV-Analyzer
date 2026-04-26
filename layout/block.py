from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Block:
    text: str
    height: float
    section: str = ""
