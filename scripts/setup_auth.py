#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configure local WorkBuddy credentials without printing or accepting token arguments."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import wb_auth  # noqa: E402


def run(non_interactive=False, gui=False, replace=False):
    """复用 → 明文导出 → 本机输入 → 体检；不在后台/安装管道中等用户输入。"""
    source = "existing"
    export = None
    try:
        existing = None if replace else wb_auth.read_rt(strict=True)
    except Exception as exc:
        return {"version": wb_auth.VERSION, "status": "config_error",
                "reason": type(exc).__name__,
                "msg": "已有配置无法读取或格式损坏，未覆盖也未要求重录。请先检查本机配置文件权限/格式。"}, 2
    if replace or not existing:
        export = None if replace else wb_auth.export_rt_from_local_state()
        if export and export.get("ok"):
            wb_auth.save_rt(export["rt"], source="export")
            source = "export"
        elif non_interactive or (not gui and not sys.stdin.isatty()):
            return {
                "version": wb_auth.VERSION, "status": "need_local_input", "configured": bool(wb_auth.read_rt()),
                "export": export,
                "msg": "尚未完成授权。不要把令牌发到聊天，也不要放进命令参数。"
                       "若已自行取得令牌，可运行 python scripts/setup_auth.py --gui 打开本机密码框，"
                       "或在本机交互终端运行 python scripts/setup_auth.py 隐藏输入。"
                       "没有令牌时，先使用宿主可用的官方登录/扫码授权；本工具不生成登录二维码。",
            }, 2
        else:
            saved = wb_auth.prompt_rt(gui=gui)
            if not saved.get("ok"):
                return {"version": wb_auth.VERSION, "status": "setup_incomplete",
                        "input": saved, "msg": "授权未完成；不要发送令牌到聊天。"}, 2
            source = "local_input"

    # --check 不领取/接取/派遣/兑换/抽奖；仍会续期并回写本机令牌。
    import claim_all
    result, check_code = claim_all.run(["--check"])
    return {"version": wb_auth.VERSION,
            "status": "ready" if check_code == 0 else "check_failed",
            "source": source, "configured": True,
            "check_exit_code": check_code, "check": result}, check_code


def main(argv=None):
    parser = wb_auth.SafeArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--non-interactive", action="store_true", help="安装/后台使用：不打开输入界面")
    mode.add_argument("--gui", action="store_true", help="需要输入时使用本机密码框（需 tkinter/桌面）")
    parser.add_argument("--replace", action="store_true", help="显式重新录入，跳过已有配置/导出")
    parser.add_argument("--version", action="version", version="setup_auth " + wb_auth.VERSION)
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        wb_auth.print_result({"status": "invalid_arguments", "msg": "不接受令牌参数；不要把令牌发到聊天。"})
        return 2
    result, check_code = run(args.non_interactive, args.gui, args.replace)
    wb_auth.print_result(result)
    return check_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        wb_auth.print_result({"ok": False, "error": "setup_failed",
                              "reason": type(exc).__name__,
                              "msg": "配置或只读体检失败；令牌不会显示在输出中。"})
        sys.exit(1)
