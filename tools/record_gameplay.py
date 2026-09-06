"""阴阳师伴随录制器命令行入口。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "recordings"


def build_parser() -> argparse.ArgumentParser:
    """创建命令行解析器。"""
    parser = argparse.ArgumentParser(description="录制游戏窗口画面和人工输入")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record = subparsers.add_parser("record", help="开始一次伴随录制")
    record.add_argument("--scenario", required=True, help="场景标识，如 realm_raid")
    record.add_argument("--window-title", default="阴阳师", help="目标窗口标题片段")
    record.add_argument("--fps", type=float, default=8.0, help="视频帧率")
    record.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="原始录制根目录",
    )

    inspect = subparsers.add_parser("inspect", help="校验并查看一次录制")
    inspect.add_argument("recording_dir", type=Path)

    clean = subparsers.add_parser("clean", help="删除一次指定录制")
    clean.add_argument("recording_dir", type=Path)
    clean.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="允许清理的录制根目录",
    )
    return parser


def record_command(args: argparse.Namespace) -> int:
    """运行交互式伴随录制。"""
    from win_util.environment.windows import WindowsEnvironment
    from yys.common.recording.session import RecordingSession
    from yys.common.recording.win32_input import WindowsInputMonitor

    if not sys.stdin.isatty():
        print("录制必须由用户在交互式终端中启动。", file=sys.stderr)
        return 2
    env = WindowsEnvironment(
        window_title=args.window_title,
        capture_mode="foreground",
    )
    session = RecordingSession(
        env=env,
        scenario=args.scenario,
        output_root=args.output_root,
        window_title=args.window_title,
        fps=args.fps,
    )
    monitor = WindowsInputMonitor(
        hwnd=env.hwnd,
        on_mouse=session.record_mouse,
        on_keyboard=session.record_keyboard,
        on_stop=session.request_stop,
        on_wheel=session.record_wheel,
    )
    print(f"已找到游戏窗口，录制编号: {session.recording_id}")
    input("按 Enter 后将自动切换到游戏；录制中按 F12 停止：")
    env.activate_window()
    time.sleep(0.5)
    output_dir = session.run(monitor)
    print(f"录制完成: {output_dir}")
    return 0


def inspect_command(args: argparse.Namespace) -> int:
    """校验录制元数据和事件顺序并输出摘要。"""
    from yys.common.recording.contracts import load_events, load_metadata

    recording_dir = args.recording_dir.resolve()
    metadata = load_metadata(recording_dir / "metadata.json")
    events = load_events(
        recording_dir / "events.jsonl",
        (metadata.client_width, metadata.client_height),
    )
    summary = {
        "recording_id": metadata.recording_id,
        "scenario": metadata.scenario,
        "status": metadata.status,
        "stop_reason": metadata.stop_reason,
        "duration_ms": metadata.duration_ms,
        "client_size": [metadata.client_width, metadata.client_height],
        "event_count": len(events),
        "video": str(recording_dir / "recording.mp4"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def clean_command(args: argparse.Namespace) -> int:
    """在严格目录边界内删除一次录制。"""
    from yys.common.recording.contracts import load_metadata

    if not sys.stdin.isatty():
        print("清理录制必须由用户在交互式终端中确认。", file=sys.stderr)
        return 2
    root = args.output_root.resolve()
    target = args.recording_dir.resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError(f"拒绝清理录制根目录之外的路径: {target}")
    metadata_path = target / "metadata.json"
    if not metadata_path.is_file():
        raise ValueError(f"目标不是有效录制目录: {target}")
    metadata = load_metadata(metadata_path)
    confirmation = input(f"输入录制编号 {metadata.recording_id} 以确认删除：").strip()
    if confirmation != metadata.recording_id:
        print("确认不匹配，未删除。")
        return 1
    shutil.rmtree(target)
    print(f"已删除录制: {target}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """解析命令并返回进程退出码。"""
    args = build_parser().parse_args(argv)
    if args.command == "record":
        return record_command(args)
    if args.command == "inspect":
        return inspect_command(args)
    if args.command == "clean":
        return clean_command(args)
    raise AssertionError(f"未处理的命令: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
