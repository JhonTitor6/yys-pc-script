"""录制关键帧候选与回放夹具生成工具。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def build_parser() -> argparse.ArgumentParser:
    """创建夹具工具参数解析器。"""
    parser = argparse.ArgumentParser(description="从伴随录制生成场景回放夹具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    candidates = subparsers.add_parser("candidates", help="生成待确认关键帧清单")
    candidates.add_argument("recording_dir", type=Path)
    candidates.add_argument("--output", type=Path, required=True)

    build = subparsers.add_parser("build", help="按人工确认清单生成夹具")
    build.add_argument("recording_dir", type=Path)
    build.add_argument("confirmation", type=Path)
    build.add_argument("output_dir", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行夹具生成命令。"""
    from yys.common.recording.fixture_builder import (
        build_candidates,
        build_confirmed_fixture,
    )

    args = build_parser().parse_args(argv)
    if args.command == "candidates":
        output = build_candidates(args.recording_dir.resolve(), args.output.resolve())
    elif args.command == "build":
        output = build_confirmed_fixture(
            args.recording_dir.resolve(),
            args.confirmation.resolve(),
            args.output_dir.resolve(),
        )
    else:
        raise AssertionError(f"未处理的命令: {args.command}")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
