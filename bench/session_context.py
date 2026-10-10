"""Session numbers block for the "sessao" questions, built from iRacingEng's own `ibt_info` output.

iRacingEng has no final prompt yet; its draft (rag/scripts/custo_por_pergunta.py) sends a free-text
"NÚMEROS" block. This module assembles that block from three `ibt_info` outputs, without computing
anything new, so every model sees the same raw session data:

    ibt_info <file.ibt> --laps                         -> per-lap table + session totals
    ibt_info <file.ibt> --yaml                         -> only the CarSetup section is kept
    ibt_info <file.ibt> --csv SessionTime,TrackTempCrew -> first and last reading only

Usage:
    uv run python -m bench.session_context
        --laps L.txt --yaml S.yaml --track-temp T.csv --out OUT.txt   (one command line)

The output stays outside git (bench/data/ is ignored): it describes a private session.
"""

import argparse
import csv
import io
from pathlib import Path


def car_setup_section(yaml_text: str) -> str:
    """The `CarSetup:` top-level block of the session YAML, as-is."""
    lines = yaml_text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith("CarSetup:"))
    except StopIteration:
        raise ValueError("session YAML has no CarSetup section") from None
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i][:1].isalpha() or lines[i] == "..."),
        len(lines),
    )
    return "\n".join(lines[start:end]).rstrip()


def track_temp_bounds(csv_text: str) -> tuple[float, float]:
    """First and last TrackTempCrew reading (°C)."""
    rows = [r for r in csv.DictReader(io.StringIO(csv_text)) if r.get("TrackTempCrew")]
    if not rows:
        raise ValueError("track temperature CSV has no TrackTempCrew readings")
    return float(rows[0]["TrackTempCrew"]), float(rows[-1]["TrackTempCrew"])


def build_session_block(laps_text: str, yaml_text: str, track_temp_csv: str) -> str:
    start, end = track_temp_bounds(track_temp_csv)
    return "\n\n".join(
        [
            "VOLTAS (ibt_info --laps)\n" + laps_text.strip(),
            f"TEMPERATURA DA PISTA (TrackTempCrew)\ninício: {start:.1f} °C · fim: {end:.1f} °C",
            "SETUP (CarSetup do arquivo da sessão)\n" + car_setup_section(yaml_text),
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the session numbers block.")
    parser.add_argument("--laps", type=Path, required=True)
    parser.add_argument("--yaml", type=Path, required=True)
    parser.add_argument("--track-temp", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    block = build_session_block(
        args.laps.read_text(encoding="utf-8"),
        args.yaml.read_text(encoding="utf-8"),
        args.track_temp.read_text(encoding="utf-8"),
    )
    args.out.write_text(block + "\n", encoding="utf-8", newline="\n")
    print(f"{len(block)} chars -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
