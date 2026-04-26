from __future__ import annotations


def check_height(current_y: float, needed_height: float, page_height: float, bottom_margin: float) -> bool:
    return current_y + needed_height > (page_height - bottom_margin)


def new_page(pdf) -> None:
    pdf.add_page()
