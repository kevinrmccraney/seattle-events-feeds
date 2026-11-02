from .crocodile import CrocodileSource, SunsetTavernSource, BelltownYachtClubSource, BabaYagaSource
from .tripledoor import TripleDoorSource, RabbitBoxSource
from .abbeyarts import FremontAbbeySource, BallardHomesteadSource
from .carbonhouse import CarbonhouseSource
from .clockout import ClockOutSource
from .dice import DiceVeraSource
from .showbox import ShowboxSource
from .tractor import TractorSource
from .nectar import NectarSource, HiddenHallSource
from .royalroom import RoyalRoomSource
from .jazzalley import JazzAlleySource
from .elcorazon import ElCorazonSource, FunhouseSource

SOURCES = [
    CarbonhouseSource("neumos", "Neumos", "https://www.neumos.com", "Neumos"),
    CarbonhouseSource("barboza", "Barboza", "https://www.thebarboza.com", "Barboza"),
    DiceVeraSource(),
    ShowboxSource(),
    TractorSource(),
    ClockOutSource(),
    NectarSource(),
    HiddenHallSource(),
    ElCorazonSource(),
    FunhouseSource(),
    JazzAlleySource(),
    RoyalRoomSource(),
    CrocodileSource(),
    SunsetTavernSource(),
    BelltownYachtClubSource(),
    BabaYagaSource(),
    TripleDoorSource(),
    RabbitBoxSource(),
    FremontAbbeySource(),
    BallardHomesteadSource(),
]
