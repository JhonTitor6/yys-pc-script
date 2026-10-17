"""带人工确认和多重保险丝的真实脚本运行入口。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def build_parser() -> argparse.ArgumentParser:
    """创建受保护运行命令行解析器。"""
    parser = argparse.ArgumentParser(
        description="单次运行游戏脚本；默认观察模式，不向游戏发送输入",
    )
    parser.add_argument("script_id", choices=["realm_raid", "regional_demon_boss"], help="要运行的脚本")
    parser.add_argument("--execute", action="store_true", help="实际发送输入")
    parser.add_argument("--window-title", default="阴阳师", help="目标窗口标题片段")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-actions", type=int, default=30)
    parser.add_argument("--unknown-limit", type=int, default=3)
    parser.add_argument(
        "--max-battles",
        type=int,
        default=9,
        help="结界突破最大战斗次数；地域鬼王固定挑战一次并忽略此参数",
    )
    parser.add_argument(
        "--skip-quit-three",
        action="store_true",
        help="结界突破本次运行不执行首次退三次；地域鬼王忽略此参数",
    )
    parser.add_argument(
        "--confirmation-phrase",
        help="已获用户授权的非交互单次调试确认短语",
    )
    return parser


def run_command(args: argparse.Namespace) -> int:
    """在精确确认后运行一次脚本，且绝不自动重启。"""
    confirmation = (
        f"RUN {args.script_id}" if args.execute else f"OBSERVE {args.script_id}"
    )
    supplied_confirmation = args.confirmation_phrase
    if supplied_confirmation is None and not sys.stdin.isatty():
        print(
            "真实运行必须由交互式终端启动，或显式提供确认短语。",
            file=sys.stderr,
        )
        return 2

    mode = "执行" if args.execute else "观察"
    print(
        f"模式: {mode}；最长 {args.timeout_seconds:g} 秒；"
        f"最多 {args.max_actions} 个动作；连续 {args.unknown_limit} 帧未知即停止。"
    )
    print("运行期间可随时按 F12 紧急停止。")
    typed = (
        supplied_confirmation.strip()
        if supplied_confirmation is not None
        else input(f"输入 {confirmation} 以开始本次运行：").strip()
    )
    if typed != confirmation:
        print("确认不匹配，未启动。")
        return 1

    from win_util.environment.guarded import GuardedEnvironment, RunGuard
    from win_util.environment.windows import WindowsEnvironment
    from yys.common.recording.win32_input import WindowsInputMonitor

    capture_mode = "foreground" if args.execute else "print_window"
    real_env = WindowsEnvironment(
        window_title=args.window_title,
        capture_mode=capture_mode,
    )
    if args.execute:
        print("执行模式将切换到游戏前台；运行期间请保持游戏窗口位于前台。")
        real_env.activate_window()
        time.sleep(0.5)
    guard = RunGuard(
        timeout_seconds=args.timeout_seconds,
        max_actions=args.max_actions,
        unknown_limit=args.unknown_limit,
    )
    guarded_env = GuardedEnvironment(
        real_env,
        guard,
        observe_only=not args.execute,
    )
    script: Any | None = None

    def ignore_mouse(
        _action: str,
        _x: int,
        _y: int,
        _end_x: int | None,
        _end_y: int | None,
        _button: str,
    ) -> None:
        return None

    def ignore_keyboard(_action: str, _key: str) -> None:
        return None

    def emergency_stop(_reason: str) -> None:
        guard.request_emergency_stop()
        if script is not None:
            script.stop()

    monitor = WindowsInputMonitor(
        hwnd=real_env.hwnd,
        on_mouse=ignore_mouse,
        on_keyboard=ignore_keyboard,
        on_stop=emergency_stop,
    )
    exit_code = 0
    summary: dict[str, object] | None = None
    try:
        if args.script_id == "realm_raid":
            from yys.realm_raid.realm_raid_script import RealmRaidScript

            script = RealmRaidScript(
                args.script_id,
                env=guarded_env,
                config={
                    "max_battle_count": args.max_battles,
                    "quit_3_times_config": not args.skip_quit_three,
                },
            )
        else:
            from yys.regional_demon_boss.regional_demon_boss_script import RegionalDemonBossScript

            # 地域鬼王固定挑战一次，结界突破专属参数不改变此分支。
            script = RegionalDemonBossScript(args.script_id, env=guarded_env, config={})
        script.set_run_guard(guard)
        if not args.execute and args.script_id == "realm_raid":
            # 旧结界突破观察模式不做入口导航；地域鬼王由自身环境状态决定。
            script.entry_scene = None
        monitor.start()
        script.run()
        summary = {
            "mode": "execute" if args.execute else "observe",
            "guard": guard.snapshot(),
            "planned_actions": len(guarded_env.action_records),
            "script": script.get_state_snapshot(),
            "auto_restart": False,
        }
    except KeyboardInterrupt:
        emergency_stop("keyboard_interrupt")
        print("脚本已被键盘中断。", file=sys.stderr)
        exit_code = 130
    except Exception as exc:
        print(f"脚本运行失败: {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        try:
            monitor.stop()
        except Exception as exc:
            print(f"输入监听器停止失败: {exc}", file=sys.stderr)
            exit_code = exit_code or 1

    if exit_code != 0 or summary is None:
        return exit_code or 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """解析参数并返回进程退出码。"""
    return run_command(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
