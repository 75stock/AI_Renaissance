#!/usr/bin/env python3
"""
数据回填工具 — 将搜索到的数据项自动回填到 *_real_data.json

用法:
    python3 scripts/fill_data.py <stock_code> --field revenue_growth --value 35.0 --source "2025Q4财报"
    python3 scripts/fill_data.py <stock_code> --batch items.json

field 与 real_data 路径对应:
    industry_market_growth → industry_signals.industry_market_growth
    industry_order_growth  → industry_signals.industry_order_growth
    industry_price_yoy     → industry_signals.industry_price_yoy
    peer_gross_margin      → peer_basket_signals.gross_margin_median
    company_revenue_growth → company_signals.revenue_growth
    rd_ratio               → company_signals.rd_ratio
    stock_name          → 顶层 stock_name
    industry            → 顶层 industry
"""

import json
import re
import sys
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"

# field → JSON path 映射
FIELD_TO_PATH = {
    # 顶层字段
    "stock_name": "stock_name",
    "industry": "industry",
    "sub_industry": "sub_industry",
    "preset": "preset",
    "chain_position": "chain_position",
    # System A 行业级字段
    "industry_market_growth": "industry_signals.industry_market_growth",
    "industry_demand_growth": "industry_signals.industry_demand_growth",
    "industry_order_growth": "industry_signals.industry_order_growth",
    "industry_order_backlog": "industry_signals.industry_order_backlog",
    "industry_capacity_utilization": "industry_signals.industry_capacity_utilization",
    "industry_price_yoy": "industry_signals.industry_price_yoy",
    "industry_inventory_days": "industry_signals.industry_inventory_days",
    "industry_capex_plan": "industry_signals.industry_capex_plan",
    "industry_policy_count": "industry_signals.industry_policy_count",
    "industry_penetration_rate": "industry_signals.industry_penetration_rate",
    "inflection_signals": "industry_signals.inflection_signals",
    "lifecycle_signals": "industry_signals.lifecycle_signals",
    # 同业篮子验证字段
    "peer_revenue_growth": "peer_basket_signals.revenue_growth_median",
    "peer_gross_margin": "peer_basket_signals.gross_margin_median",
    "peer_inventory_days": "peer_basket_signals.inventory_days_median",
    # System B 个股字段
    "company_revenue_growth": "company_signals.revenue_growth",
    "rd_ratio": "company_signals.rd_ratio",
    "research_expense_ratio": "company_signals.research_expense_ratio",
    "net_profit_parent": "company_signals.net_profit_parent",
    "revenue": "company_signals.revenue",
    "operating_cash_flow": "company_signals.operating_cash_flow",
    "fixed_asset": "company_signals.fixed_asset",
    "total_asset": "company_signals.total_asset",
    "market_share": "company_signals.market_share",
    "major_customer_orders": "company_signals.major_customer_orders",
    "contract_liability": "company_signals.contract_liability",
    "fixed_asset_turnover": "company_signals.fixed_asset_turnover",
}

# ========== capex_plan 枚举校验 ==========
CAPEX_PLAN_VALID = {"underway", "planned", "none", "aggressive"}
CAPEX_PLAN_VALUES_HELP = """
  capex_plan 必须为以下枚举值之一:
    "underway"   — 扩产进行中（已公告、已在建）
    "planned"    — 扩产计划已公告但未开工
    "none"       — 近期无扩产计划
    "aggressive" — 激进扩产（规模超预期、节奏加快）
  示例: --field capex_plan --value underway
""" 


def _set_nested(data: dict, path: str, value: Any):
    """按 '.' 分隔路径设置嵌套字典值。"""
    keys = path.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def _load_or_create(stock_code: str) -> Dict[str, Any]:
    """加载现有 real_data 或创建模板。"""
    candidates = [
        DATA_DIR / f"{stock_code}_real_data.json",
        DATA_DIR / f"{stock_code.upper()}_real_data.json",
    ]
    for path in candidates:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

    # 创建模板
    code = stock_code.upper()
    base_code = re.sub(r"\.(SH|SZ|BJ|HK)$", "", code)
    return {
        "stock_code": code,
        "stock_name": base_code,
        "industry": "数据缺失",
        "preset": "generic",
        "generated_at": datetime.now().strftime("%Y-%m-%d"),
        "industry_signals": {},
        "peer_basket_signals": {},
        "company_signals": {},
        "industry_data": [],
    }


def fill_field(
    stock_code: str,
    field: str,
    value: Any,
    source: str = "",
    source_date: str = "",
    source_url: str = "",
    save: bool = True,
) -> Dict[str, Any]:
    """回填单个字段到 real_data。

    Args:
        stock_code: 股票代码
        field: 字段名（见 FIELD_TO_PATH）
        value: 值（自动转换数字）
        source: 数据来源描述
        source_date: 数据日期
        source_url: 来源 URL
        save: 是否保存到文件

    Returns:
        更新后的 data dict
    """
    data = _load_or_create(stock_code)

    # 解析字段路径
    path = FIELD_TO_PATH.get(field, field)
    if "." not in path and path not in ("stock_name", "industry", "sub_industry", "preset", "chain_position"):
        path = f"industry_signals.{field}"

    # 值转换
    if isinstance(value, str):
        # 尝试转数字
        v = value.strip().replace("%", "").replace(",", "")
        try:
            value = float(v)
            if value == int(value):
                value = int(value)
        except ValueError:
            pass

    # capex_plan 枚举校验
    if field == "capex_plan" and isinstance(value, str):
        v = value.strip().lower()
        if v not in CAPEX_PLAN_VALID:
            print(f"⚠️  警告: capex_plan='{value}' 不是有效枚举值")
            print(CAPEX_PLAN_VALUES_HELP)
            # 尝试中文→枚举映射
            cn_map = {"进行中": "underway", "已规划": "planned", "规划中": "planned",
                      "无": "none", "激进": "aggressive", "扩产": "underway"}
            v = cn_map.get(v, v)
            if v in CAPEX_PLAN_VALID:
                value = v
                print(f"   已自动转换: '{value}' → '{v}'")
            else:
                print(f"   无法自动转换，将使用原始值（可能无法匹配拐点判定）")
    
    # 写入
    _set_nested(data, path, value)

    # 写入 source 信息
    if field not in ("stock_name", "industry", "stock_code", "preset"):
        root = path.split(".", 1)[0] if "." in path else "industry_signals"
        target = data.setdefault(root, {})
        source_key = f"{field}_source"
        if source:
            target[source_key] = source
        if source_date:
            target[f"{field}_date"] = source_date
        if source_url:
            target[f"{field}_url"] = source_url

    # 更新缺失计数
    industry = data.get("industry_signals", {})
    core_fields = [
        "industry_market_growth", "industry_order_growth",
        "industry_capacity_utilization", "industry_price_yoy",
        "industry_inventory_days", "industry_capex_plan",
    ]
    missing = sum(1 for f in core_fields if industry.get(f) is None)
    data["_missing_count"] = missing
    data["_last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    if save:
        out_path = DATA_DIR / f"{stock_code.upper()}_real_data.json"
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 已写入: {out_path}")
        print(f"   {field} = {value}")
        if source:
            print(f"   来源: {source}")

    return data


def fill_batch(stock_code: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """批量回填多个字段。

    Args:
        stock_code: 股票代码
        items: [{field: "revenue_growth", value: 35.0, source: "..."}, ...]
    """
    data = _load_or_create(stock_code)
    for item in items:
        data = fill_field(
            stock_code,
            item["field"],
            item.get("value"),
            source=item.get("source", ""),
            source_date=item.get("date", ""),
            source_url=item.get("url", ""),
            save=False,
        )
    # 最终保存
    out_path = DATA_DIR / f"{stock_code.upper()}_real_data.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 批量回填完成: {out_path} ({len(items)} 项)")
    return data


def _auto_run_pipeline(stock_code: str):
    """自动重新运行 pipeline 生成报告"""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from core.pipeline import run_pipeline
        print(f"\\n🔄 自动重新运行 pipeline: {stock_code}")
        result = run_pipeline(stock_code)
        if result:
            print(f"✅ 报告已生成: {result}")
        else:
            print("⚠️  pipeline 返回空路径")
    except Exception as e:
        print(f"⚠️  自动重跑失败（不影响数据回填）: {e}")
    
def show_missing(stock_code: str) -> List[str]:
    """显示缺失字段列表。"""
    data = _load_or_create(stock_code)
    industry = data.get("industry_signals", {})
    peer = data.get("peer_basket_signals", {})
    company = data.get("company_signals", {})
    core_paths = {
        "industry_market_growth": industry,
        "industry_order_growth": industry,
        "industry_capacity_utilization": industry,
        "industry_price_yoy": industry,
        "industry_inventory_days": industry,
        "industry_capex_plan": industry,
        "peer_revenue_growth": peer,
        "peer_gross_margin": peer,
        "company_revenue_growth": company,
        "rd_ratio": company,
    }
    missing = [f for f, source in core_paths.items() if source.get(f) is None and FIELD_TO_PATH.get(f, "").split(".")[-1] not in source]
    filled = [f for f in core_paths if f not in missing]

    print(f"📊 {stock_code} 数据状态:")
    print(f"  已填充: {len(filled)}/{len(core_fields)}")
    if filled:
        for f in filled:
            path = FIELD_TO_PATH.get(f, f)
            root, _, key = path.partition(".")
            value = data.get(root, {}).get(key, data.get(root, {}).get(f))
            print(f"    ✅ {f} = {value}")
    if missing:
        for f in missing:
            print(f"    ❌ {f} 缺失")
    return missing


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="数据回填工具")
    parser.add_argument("stock_code", help="股票代码")
    parser.add_argument("--field", help="要回填的字段名")
    parser.add_argument("--value", help="字段值")
    parser.add_argument("--source", default="", help="数据来源")
    parser.add_argument("--date", default="", help="数据日期")
    parser.add_argument("--url", default="", help="来源URL")
    parser.add_argument("--batch", help="批量回填的 JSON 文件路径")
    parser.add_argument("--show", action="store_true", help="显示缺失字段")
    parser.add_argument("--auto-run", action="store_true", help="回填后自动重新运行 pipeline 生成报告")

    args = parser.parse_args()

    if args.show:
        show_missing(args.stock_code)
        sys.exit(0)
    
    # 执行回填
    if args.batch:
        with open(args.batch, "r", encoding="utf-8") as f:
            items = json.load(f)
        fill_batch(args.stock_code, items)
    elif args.field and args.value is not None:
        fill_field(
            args.stock_code, args.field, args.value,
            source=args.source, source_date=args.date, source_url=args.url,
        )
    else:
        parser.print_help()
        sys.exit(1)
    
    # P2-1: 自动重新运行 pipeline
    if args.auto_run:
        _auto_run_pipeline(args.stock_code)
