from .crocodile import CrocodileSource, SunsetTavernSource, BelltownYachtClubSource, BabaYagaSource, ShowboxCrocodileSource
from .tripledoor import TripleDoorSource
from .rabbitbox import RabbitBoxSource
from .abbeyarts import FremontAbbeySource, BallardHomesteadSource
from .carbonhouse import CarbonhouseSource
from .clockout import ClockOutSource
from .dice import DiceVeraSource
from .tractor import TractorSource
from .nectar import NectarSource, HiddenHallSource
from .royalroom import RoyalRoomSource
from .jazzalley import JazzAlleySource
from .elcorazon import ElCorazonSource, FunhouseSource

SOURCES = [
    CarbonhouseSource("neumos", "Neumos", "https://www.neumos.com", "Neumos"),
    CarbonhouseSource("barboza", "Barboza", "https://www.thebarboza.com", "Barboza"),
    DiceVeraSource(),
    ShowboxCrocodileSource(),
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
