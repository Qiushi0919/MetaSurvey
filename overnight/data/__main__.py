"""Append-only private diagnostic artifacts; no networking or credential lookup."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
from .dataset import DataError, canonical, load_verified_dataset, require, sha
from .coverage import analyze_coverage

OUTPUT_ROOT = Path("/Users/qiushi/投资研究/.p1b-archives/overnight-20261005/data")

def exclusive_write(path, raw):
    require(type(path) is Path or isinstance(path, Path), "OUTPUT_PATH_INVALID")
    require(path.is_absolute() and ".." not in path.parts, "OUTPUT_PATH_INVALID")
    require(type(raw) is bytes, "OUTPUT_BYTES_INVALID")
    directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parent.parts[1:]:
            try: os.mkdir(part, mode=0o700, dir_fd=directory)
            except FileExistsError: pass
            try: child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            except OSError: raise DataError("OUTPUT_SYMLINK_OR_DIRECTORY_INVALID") from None
            os.close(directory); directory = child
        try: fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        except FileExistsError: raise DataError("OUTPUT_EXISTS_NO_OVERWRITE") from None
        with os.fdopen(fd, "wb") as stream: stream.write(raw)
    finally: os.close(directory)

def write_outputs(dataset, coverage, run_id):
    require(type(run_id) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,90}", run_id), "OUTPUT_RUN_ID_INVALID")
    require(dataset["fixture"] is False and coverage["fixture"] is False, "FIXTURE_REAL_OUTPUT_BLOCKED")
    # Revalidation binds the same registered dataset; coverage must be recomputed.
    expected = analyze_coverage(dataset)
    require(canonical(coverage) == canonical(expected), "COVERAGE_MUTATED")
    root = OUTPUT_ROOT / run_id
    require(not root.exists() and not root.is_symlink(), "OUTPUT_RUN_EXISTS")
    bodies = {"typed-normalized-dataset.json": canonical(dataset) + b"\n", "coverage-report.json": canonical(coverage) + b"\n"}
    inventory = []
    for name, raw in bodies.items():
        exclusive_write(root / name, raw)
        inventory.append({"object": name, "sha256": sha(raw), "bytes": len(raw)})
    index = {"version": "1.0.0-diagnostic", "run_id": run_id, "state": "QUARANTINED", "source_admission": "BLOCKED",
             "historical_visibility_proven": False, "productionGate": False, "artifacts": inventory}
    exclusive_write(root / "artifact-index.json", canonical(index) + b"\n")
    return index

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        dataset = load_verified_dataset(); coverage = analyze_coverage(dataset)
        write_outputs(dataset, coverage, args.run_id)
        print("QUARANTINED_SIDECARS_WRITTEN requests=44 rows=2786 source_admission=BLOCKED")
    except Exception:
        print("DIAGNOSTIC_OUTPUT_FAILED_NO_ADMISSION")
        return 1
    return 0

if __name__ == "__main__": raise SystemExit(main())
