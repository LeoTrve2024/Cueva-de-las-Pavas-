from datetime import date

from pavas_afluencia.service import day_factor, level, score


def test_document_examples() -> None:
    assert score(20, 100) == 88
    assert score(90, 50) == 26
    assert score(80, 100) == 52


def test_boundaries() -> None:
    assert level(39) == "baja"
    assert level(40) == "media"
    assert level(69) == "media"
    assert level(70) == "alta"


def test_calendar_factor() -> None:
    assert day_factor(date(2026, 10, 3)) == 100
    assert day_factor(date(2026, 10, 5)) == 50
