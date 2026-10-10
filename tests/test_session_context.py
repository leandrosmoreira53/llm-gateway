from pathlib import Path

import pytest

from bench.dataset import dataset_fingerprint
from bench.session_context import build_session_block, car_setup_section, track_temp_bounds

YAML = """---
WeekendInfo:
 TrackName: bristol
DriverInfo:
 DriverCarIdx: 0
CarSetup:
 UpdateCount: 3
 Tires:
  LeftFront:
   ColdPressure: 18.0 psi
...
"""
CSV = "SessionTime,TrackTempCrew\n1.0,22.22\n2.0,\n3.0,26.67\n"
LAPS = "sessão volta tempo\n  2  1  15.5  limpa\n\n2 voltas, 1 limpas\n"


def test_car_setup_section_only() -> None:
    section = car_setup_section(YAML)
    assert section.startswith("CarSetup:")
    assert "ColdPressure: 18.0 psi" in section
    assert "DriverInfo" not in section
    assert "..." not in section


def test_missing_car_setup_fails() -> None:
    with pytest.raises(ValueError, match="CarSetup"):
        car_setup_section("WeekendInfo:\n x: 1\n")


def test_track_temp_first_and_last_reading() -> None:
    assert track_temp_bounds(CSV) == (22.22, 26.67)
    with pytest.raises(ValueError, match="TrackTempCrew"):
        track_temp_bounds("SessionTime,TrackTempCrew\n")


def test_block_keeps_raw_output_and_adds_nothing_computed() -> None:
    block = build_session_block(LAPS, YAML, CSV)
    assert block.startswith("VOLTAS (ibt_info --laps)\nsessão volta tempo")
    assert "2 voltas, 1 limpas" in block
    assert "início: 22.2 °C · fim: 26.7 °C" in block
    assert block.rstrip().endswith("ColdPressure: 18.0 psi")


def test_fingerprint_ignores_line_endings(tmp_path: Path) -> None:
    lf = tmp_path / "lf.jsonl"
    crlf = tmp_path / "crlf.jsonl"
    lf.write_bytes(b'{"id": "a"}\n{"id": "b"}\n')
    crlf.write_bytes(b'{"id": "a"}\r\n{"id": "b"}\r\n')
    assert dataset_fingerprint(lf) == dataset_fingerprint(crlf)
