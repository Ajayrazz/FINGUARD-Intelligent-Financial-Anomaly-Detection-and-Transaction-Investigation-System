"""Ingestion sources. Every source yields `RawChunk`s so the pipeline is source-agnostic.

Future event-stream ingestion (Kafka etc.) = one more IngestionSource whose `chunks()` micro-batches messages;
nothing downstream changes (requirement FR-M1-17, docs/05).
"""

import csv
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import pandas as pd


@dataclass
class RawChunk:
    first_row_number: int  # 1-based number of the first data row in this chunk (header excluded)
    frame: pd.DataFrame  # well-formed rows, all values as strings
    malformed: list[tuple[int, list[str]]] = field(default_factory=list)  # (row_number, raw cells)
    consumed: int = 0  # data rows covered by this chunk (frame + malformed)


class IngestionSource(Protocol):
    def header(self) -> list[str]: ...
    def estimate_rows(self) -> int | None: ...
    def chunks(self, chunk_rows: int, skip_rows: int = 0) -> Iterator[RawChunk]: ...


def _skip(consumed_before: int, frame_len: int, skip_rows: int) -> int:
    """How many leading rows of a chunk starting at `consumed_before` to drop to honour `skip_rows`."""
    return max(0, min(frame_len, skip_rows - consumed_before))


class CsvSource:
    def __init__(self, path: str | Path, encoding: str = "utf-8-sig") -> None:
        self.path, self.encoding = Path(path), encoding

    def _reader(self, fh):  # noqa: ANN001, ANN202
        return csv.reader(fh)

    def header(self) -> list[str]:
        with open(self.path, newline="", encoding=self.encoding, errors="replace") as fh:
            row = next(csv.reader(fh), [])
        return [c.strip() for c in row]

    def estimate_rows(self) -> int | None:
        """Newline count minus header. Approximate if quoted fields contain newlines; used for progress only."""
        n, last = 0, b"\n"
        with open(self.path, "rb") as fh:
            while block := fh.read(1 << 22):
                n += block.count(b"\n")
                last = block[-1:]
        if last != b"\n":  # final line has no trailing newline
            n += 1
        return max(0, n - 1)

    def chunks(self, chunk_rows: int, skip_rows: int = 0) -> Iterator[RawChunk]:
        with open(self.path, newline="", encoding=self.encoding, errors="replace") as fh:
            reader = csv.reader(fh)
            header = [c.strip() for c in next(reader, [])]
            width = len(header)
            rows: list[list[str]] = []
            bad: list[tuple[int, list[str]]] = []
            row_no = 0
            start = 1
            for cells in reader:
                if not cells:  # blank line: ignored, not counted
                    continue
                row_no += 1
                if row_no <= skip_rows:
                    start = row_no + 1
                    continue
                if len(cells) == width:
                    rows.append(cells)
                else:
                    bad.append((row_no, cells))
                if len(rows) + len(bad) >= chunk_rows:
                    yield RawChunk(start, pd.DataFrame(rows, columns=header, dtype=object), bad, row_no - start + 1)
                    rows, bad, start = [], [], row_no + 1
            if rows or bad:
                yield RawChunk(start, pd.DataFrame(rows, columns=header, dtype=object), bad, row_no - start + 1)


class ExcelSource:
    """Read-only streaming read of the first (or named) sheet. Cached values only: formulas are never evaluated."""

    def __init__(self, path: str | Path, sheet: str | None = None) -> None:
        self.path, self.sheet = Path(path), sheet

    def _rows(self):  # noqa: ANN202
        from openpyxl import load_workbook

        wb = load_workbook(self.path, read_only=True, data_only=True)
        ws = wb[self.sheet] if self.sheet else wb.worksheets[0]
        return wb, ws

    def header(self) -> list[str]:
        wb, ws = self._rows()
        try:
            first = next(ws.iter_rows(values_only=True), ())
            return ["" if v is None else str(v).strip() for v in first]
        finally:
            wb.close()

    def estimate_rows(self) -> int | None:
        wb, ws = self._rows()
        try:
            return max(0, (ws.max_row or 1) - 1)
        finally:
            wb.close()

    def chunks(self, chunk_rows: int, skip_rows: int = 0) -> Iterator[RawChunk]:
        wb, ws = self._rows()
        try:
            it = ws.iter_rows(values_only=True)
            header = ["" if v is None else str(v).strip() for v in next(it, ())]
            width = len(header)
            rows: list[list[str]] = []
            bad: list[tuple[int, list[str]]] = []
            row_no, start = 0, 1
            for values in it:
                cells = ["" if v is None else str(v) for v in values]
                if not any(c.strip() for c in cells):  # fully blank row
                    continue
                row_no += 1
                if row_no <= skip_rows:
                    start = row_no + 1
                    continue
                cells = cells[:width] + [""] * (width - len(cells))  # sheets are rectangular; pad short rows
                rows.append(cells)
                if len(rows) >= chunk_rows:
                    yield RawChunk(start, pd.DataFrame(rows, columns=header, dtype=object), bad, row_no - start + 1)
                    rows, bad, start = [], [], row_no + 1
            if rows or bad:
                yield RawChunk(start, pd.DataFrame(rows, columns=header, dtype=object), bad, row_no - start + 1)
        finally:
            wb.close()


class RecordsSource:
    """In-memory records (API ingestion). Keys are the canonical field names."""

    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records
        keys: list[str] = []
        for r in records:
            for k in r:
                if k not in keys:
                    keys.append(k)
        self._header = keys

    def header(self) -> list[str]:
        return self._header

    def estimate_rows(self) -> int | None:
        return len(self.records)

    def chunks(self, chunk_rows: int, skip_rows: int = 0) -> Iterator[RawChunk]:
        for i in range(skip_rows, len(self.records), chunk_rows):
            part = self.records[i : i + chunk_rows]
            frame = pd.DataFrame(
                [{k: ("" if r.get(k) is None else str(r[k])) for k in self._header} for r in part],
                columns=self._header,
                dtype=object,
            )
            yield RawChunk(i + 1, frame, [], len(part))
