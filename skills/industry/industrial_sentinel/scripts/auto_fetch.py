#!/usr/bin/env python3
"""
Industrial Sentinel 本地补数调试脚本。

真实 provider 请求和字段解析位于 data_sources.industrial_sentinel_auto_fetch。
本脚本只负责命令行参数和把结果写入 skill data 目录。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

from data_sources.industrial_sentinel_auto_fetch import fetch_and_save_real_data


def auto_fetch_and_save(stock_code: str, force: bool = False) -> Path | None:
    """兼容旧脚本入口，委托 data_sources 层完成真实抓取和保存。"""
    return fetch_and_save_real_data(stock_code, output_dir=DATA_DIR, force=force)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Industrial Sentinel 本地补数调试")
    parser.add_argument("stock_code", help="股票代码")
    parser.add_argument("--force", action="store_true", help="强制覆盖")
    args = parser.parse_args()

    result = auto_fetch_and_save(args.stock_code, args.force)
    if result:
        print(f"完成: {result}")
    else:
        print("抓取失败")
        sys.exit(1)
