"""Bounded, fail-closed discovery checkpoints; no database migration required."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from accountant.ops.edgar_calendar import edgar_holidays

MAX_BYTES = 8 * 1024 * 1024
HISTORY_DAYS = 30


def _filing_day(day: date) -> bool:
    return day.weekday() < 5 and day not in edgar_holidays(day.year)


@contextmanager
def checkpoint_lock(path: Path):
    """Lock a stable sidecar, not the checkpoint inode replaced by atomic saves."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + ".lock").open("a+b") as handle:
        handle.seek(0)
        if os.name == "nt":
            msvcrt = importlib.import_module("msvcrt")

            if not handle.read(1):
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl = importlib.import_module("fcntl")

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class DiscoveryState:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict = {"version": 1, "days": {}}
        if path.exists():
            if path.stat().st_size > MAX_BYTES:
                raise ValueError("discovery checkpoint exceeds size limit")
            self.data = json.loads(path.read_text(encoding="utf-8"))
            self._validate()

    def _validate(self):
        if self.data.get("version") != 1 or not isinstance(self.data.get("days"), dict):
            raise ValueError("unsupported discovery checkpoint")
        attempts = self.data.get("company_attempts", {})
        if not isinstance(attempts, dict) or not all(
            type(n) is int and n >= 0 for n in attempts.values()
        ):
            raise ValueError("invalid company attempts")
        for day, entry in self.days.items():
            if date.fromisoformat(day).isoformat() != day or date.fromisoformat(day) > date.today():
                raise ValueError("invalid checkpoint date")
            if not isinstance(entry.get("ok"), bool) or type(entry.get("attempts")) is not int:
                raise ValueError("invalid checkpoint status")
            for field in ("pending", "done"):
                if not isinstance(entry.get(field), dict):
                    raise ValueError("invalid checkpoint companies")
                for cik, accessions in entry[field].items():
                    if not (len(cik) == 10 and cik.isdigit() and isinstance(accessions, list)):
                        raise ValueError("invalid checkpoint company")
                    if not all(isinstance(a, str) and len(a) == 20 for a in accessions):
                        raise ValueError("invalid checkpoint accessions")

    @property
    def days(self):
        return self.data["days"]

    def entry(self, day: date):
        return self.days.setdefault(
            day.isoformat(), {"ok": False, "attempts": 0, "pending": {}, "done": {}}
        )

    def dates(self, today: date, start: date | None, end: date) -> list[date]:
        if end > today or (start is not None and start > end):
            raise ValueError("invalid or future discovery date range")
        if start is not None:
            return [
                start + timedelta(days=i)
                for i in range((end - start).days + 1)
                if _filing_day(start + timedelta(days=i))
            ]
        valid = [date.fromisoformat(d) for d in self.days if date.fromisoformat(d) <= end]
        overlap = end
        count = 0
        while count < 3:
            if _filing_day(overlap):
                count += 1
            if count < 3:
                overlap -= timedelta(days=1)
        floor = end - timedelta(days=HISTORY_DAYS - 1)
        first = max(floor, min(overlap, max(valid) if valid else floor))
        normal = {
            first + timedelta(days=i)
            for i in range((end - first).days + 1)
            if _filing_day(first + timedelta(days=i))
        }
        # Least-attempted first prevents one permanent failure monopolizing retries.
        retries = sorted(
            (d for d in valid if not self.days[d.isoformat()]["ok"]),
            key=lambda d: (self.days[d.isoformat()]["attempts"], d),
        )[:10]
        return sorted(normal | set(retries))

    def save(self, today: date):
        cutoff = today - timedelta(days=HISTORY_DAYS)
        self.data["days"] = {
            d: e
            for d, e in self.days.items()
            if date.fromisoformat(d) >= cutoff or not e["ok"] or e["pending"]
        }
        raw = json.dumps(self.data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(raw) > MAX_BYTES:
            raise ValueError("discovery checkpoint full; unresolved work retained on disk")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name + ".")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            if os.name != "nt":
                directory = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
