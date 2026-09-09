#!/usr/bin/env python3
"""Gold-aware scoring entry point; valid only for frozen inference artifacts."""

from __future__ import annotations

import argparse
import json

from causalrisk.scoring import score_frozen_run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("gold_file")
    args = parser.parse_args()
    summary = score_frozen_run(args.run_dir, args.gold_file)
    print(json.dumps(summary.to_dict(), sort_keys=True))


if __name__ == "__main__":
    main()
