from .base import Channel, answer_instructions
from .cif_text import CifTextChannel
from .image import ImageChannel
from .tools import ToolsChannel
from .tui import TuiChannel

CHANNELS = {
    "cif": lambda: CifTextChannel(strip=True),
    "cif_raw": lambda: CifTextChannel(strip=False),
    "image": ImageChannel,
    "tui": TuiChannel,
    "tools": ToolsChannel,
}

__all__ = ["CHANNELS", "Channel", "answer_instructions"]