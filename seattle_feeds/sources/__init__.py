from .carbonhouse import CarbonhouseSource
from .clockout import ClockOutSource
from .dice import DiceVeraSource
from .showbox import ShowboxSource
from .tractor import TractorSource
from .nectar import NectarSource, HiddenHallSource

SOURCES = [
    CarbonhouseSource("neumos", "Neumos", "https://www.neumos.com", "Neumos"),
    CarbonhouseSource("barboza", "Barboza", "https://www.thebarboza.com", "Barboza"),
    DiceVeraSource(),
    ShowboxSource(),
    TractorSource(),
    ClockOutSource(),
    NectarSource(),
    HiddenHallSource(),
]
