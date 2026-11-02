from .carbonhouse import CarbonhouseSource
from .dice import DiceVeraSource
from .showbox import ShowboxSource

SOURCES = [
    CarbonhouseSource("neumos", "Neumos", "https://www.neumos.com", "Neumos"),
    CarbonhouseSource("barboza", "Barboza", "https://www.thebarboza.com", "Barboza"),
    DiceVeraSource(),
    ShowboxSource(),
]
