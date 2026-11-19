"""CLI: validate raw datasets, write cleaned + split copies and a reproducibility manifest.

    python -m ml_engine.data.prepare [--dataset paysim|creditcard|all]

Raw files are only read (checksummed before and after). Outputs go to datasets/processed/<name>/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import config, preprocess, splits, validation


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _versions() -> dict[str, str]:
    import pyarrow

    return {
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "pyarrow": pyarrow.__version__,
    }


def _write_splits(out_dir: Path, parts: dict[str, pd.DataFrame]) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    for name, part in parts.items():
        path = out_dir / f"{name}.parquet"
        part.reset_index(drop=True).to_parquet(path, index=False)
        files[name] = {"file": path.name, "rows": len(part), "sha256": sha256(path)}
    return files


def prepare(
    name: str,
    raw_file: str,
    *,
    validate_fn,
    profile_fn,
    clean_fn,
    time_col: str,
    account_col: str | None,
) -> dict[str, Any]:
    raw_path = config.RAW_DIR / raw_file
    if not raw_path.exists():
        raise FileNotFoundError(f"{raw_path} not found; see datasets/README.md")
    raw_hash_before = sha256(raw_path)
    print(f"[{name}] reading {raw_path.name}", flush=True)
    raw = pd.read_csv(raw_path)

    result: validation.ValidationResult = validate_fn(raw)
    result.raise_if_failed()
    profile = profile_fn(raw)

    cleaned, clean_stats = clean_fn(raw)
    del raw
    parts, boundaries = splits.chronological_split(cleaned, time_col, config.SPLIT_FRACTIONS)
    split_summary = splits.verify_split(parts, time_col, "is_fraud", total_rows=len(cleaned))
    overlap = splits.account_overlap(parts, account_col) if account_col else None

    out_dir = config.PROCESSED_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    files = _write_splits(out_dir, parts)

    if sha256(raw_path) != raw_hash_before:  # defensive: the raw file must be untouched
        raise RuntimeError(f"raw file {raw_path} changed during preparation")

    manifest = {
        "dataset": name,
        "raw": {"file": raw_file, "sha256": raw_hash_before, "bytes": raw_path.stat().st_size},
        "validation": {"warnings": result.warnings},
        "cleaning": clean_stats,
        "split": {**boundaries, "summary": split_summary, "account_overlap": overlap},
        "outputs": files,
        "versions": _versions(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    (out_dir / "profile.json").write_text(json.dumps(profile, indent=2, default=str))
    print(f"[{name}] wrote {out_dir} ({', '.join(f'{k}={v["rows"]}' for k, v in files.items())})", flush=True)
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", choices=["paysim", "creditcard", "all"], default="all")
    args = ap.parse_args(argv)
    if args.dataset in ("paysim", "all"):
        prepare(
            "paysim",
            config.PAYSIM_FILE,
            validate_fn=validation.validate_paysim,
            profile_fn=validation.profile_paysim,
            clean_fn=preprocess.clean_paysim,
            time_col="step",
            account_col="sender",
        )
    if args.dataset in ("creditcard", "all"):
        prepare(
            "creditcard",
            config.CREDITCARD_FILE,
            validate_fn=validation.validate_creditcard,
            profile_fn=validation.profile_creditcard,
            clean_fn=preprocess.clean_creditcard,
            time_col="time",
            account_col=None,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
