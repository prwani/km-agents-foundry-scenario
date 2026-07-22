from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Brand:
    navy: str = "17324D"
    teal: str = "00A6A6"
    gold: str = "F4B942"
    cloud: str = "F3F7FA"
    ink: str = "1C2733"
    muted: str = "607386"
    white: str = "FFFFFF"
    header_font: str = "Aptos Display"
    body_font: str = "Aptos"


CONTOSO = Brand()
