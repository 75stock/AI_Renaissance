"""
Industrial Sentinel 自动补数数据源。

真实 provider 请求、字段解析和可选缓存写入都放在 data_sources/ 层。
Skill 脚本只允许作为薄调试包装调用这里的接口。
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


EASTMONEY_FIELD_MAP = {
    "f41": "revenue_growth",
    "f57": "gross_margin",
    "f9": "pe",
    "f20": "total_market_cap",
}

AKSHARE_FIELD_MAP = {
    "revenue_growth": "营业总收入同比增长率",
    "gross_margin": "销售毛利率",
    "net_profit_parent": "归属母公司净利润",
    "rd_ratio": "研发费用/营业总收入",
    "contract_liability": "合同负债",
    "inventory_days": "存货周转天数",
    "fixed_asset_turnover": "固定资产周转率",
}


def clean_code(stock_code: str) -> str:
    """去后缀，保留股票主体代码。"""
    return re.sub(r"\.(SH|SZ|BJ|HK)$", "", stock_code.upper())


def code_to_eastmoney_secid(stock_code: str) -> str:
    """将股票代码转为东方财富 secid 格式。"""
    code = stock_code.upper()
    clean = clean_code(code)
    if ".SH" in code or clean.startswith(("6", "68")):
        return f"1.{clean}"
    return f"0.{clean}"


def fetch_from_eastmoney(stock_code: str) -> Dict[str, float]:
    """通过东方财富 push2 API 获取可映射到 real_signals 的字段。"""
    secid = code_to_eastmoney_secid(stock_code)
    url = (
        "https://push2.eastmoney.com/api/qt/ulist.np/get"
        f"?fltt=2&fields=f2,f9,f12,f14,f20,f41,f57&secids={secid}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    stock = data["data"]["diff"][0]

    signals = {}
    for provider_field, signal_field in EASTMONEY_FIELD_MAP.items():
        value = stock.get(provider_field)
        if value is None or value == "-":
            continue
        try:
            signals[signal_field] = float(value)
        except (TypeError, ValueError):
            continue
    return signals


def fetch_from_akshare(stock_code: str) -> Dict[str, float]:
    """通过 AkShare 获取备用财务指标。"""
    import akshare as ak

    df = ak.stock_financial_analysis_indicator(symbol=clean_code(stock_code))
    signals = {}
    if df.empty:
        return signals

    latest = df.iloc[0]
    for signal_field, provider_field in AKSHARE_FIELD_MAP.items():
        if provider_field not in latest.index or latest[provider_field] is None:
            continue
        try:
            signals[signal_field] = float(latest[provider_field])
        except (TypeError, ValueError):
            continue
    return signals


def fetch_real_signals(stock_code: str) -> Dict[str, float]:
    """获取 Industrial Sentinel 可消费的 real_signals。"""
    signals = {}
    try:
        signals.update(fetch_from_eastmoney(stock_code))
    except Exception:
        pass

    if len(signals) < 3:
        try:
            signals.update(fetch_from_akshare(stock_code))
        except Exception:
            pass
    return signals


def build_real_data(stock_code: str, signals: Dict[str, float]) -> Dict[str, object]:
    """把抓取结果包装成 industrial_sentinel 的 real_data 结构。"""
    core_fields = [
        "revenue_growth",
        "gross_margin",
        "order_backlog",
        "capacity_utilization",
        "price_yoy",
        "inventory_days",
        "contract_liability",
        "fixed_asset_turnover",
    ]
    return {
        "stock_code": stock_code.upper(),
        "stock_name": clean_code(stock_code),
        "industry": "数据缺失",
        "preset": "generic",
        "real_signals": dict(signals),
        "industry_data": [],
        "_last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "_data_source": "data_sources.industrial_sentinel_auto_fetch",
        "_missing_count": sum(1 for field in core_fields if signals.get(field) is None),
    }


def fetch_real_data(stock_code: str) -> Optional[Dict[str, object]]:
    """获取 real_data，失败或无字段时返回 None。"""
    signals = fetch_real_signals(stock_code)
    if not signals:
        return None
    return build_real_data(stock_code, signals)


def fetch_and_save_real_data(
    stock_code: str,
    output_dir: Path,
    force: bool = False,
) -> Optional[Path]:
    """抓取并保存 real_data，供本地调试脚本使用。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{clean_code(stock_code)}_real_data.json"

    if out_path.exists() and not force:
        return out_path

    data = fetch_real_data(stock_code)
    if data is None:
        return None

    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing.setdefault("real_signals", {}).update(data["real_signals"])
        existing["_last_updated"] = data["_last_updated"]
        existing["_data_source"] = data["_data_source"]
        existing["_missing_count"] = data["_missing_count"]
        data = existing

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return out_path
