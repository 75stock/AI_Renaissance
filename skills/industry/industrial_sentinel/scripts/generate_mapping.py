#!/usr/bin/env python3
"""
全量A股行业映射生成器

用法:
    # 方式1: 用akshare生成（推荐，最完整）
    pip install akshare
    python scripts/generate_mapping.py

    # 方式2: 用web_search逐个补充（不需要akshare）
    python scripts/generate_mapping.py --stock 002922 --search

    # 方式3: 批量补充一批股票
    python scripts/generate_mapping.py --batch stocks.txt --search

输出:
    data/mappings/stock-to-preset.json  — 用户自定义映射表（自动加载）
"""

import json
import sys
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent.resolve()
REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DATA_DIR = SCRIPT_DIR / "data"
MAPPING_FILE = DATA_DIR / "mappings" / "stock-to-preset.json"

# 申万行业 → preset 映射规则
INDUSTRY_RULES = [
    # AI芯片层
    (["半导体", "集成电路", "芯片", "GPU", "ASIC", "EDA", "HBM", "晶圆",
      "刻蚀", "光刻", "封测", "先进封装", "存储芯片", "闪存", "DRAM", "NAND"],
     "ai-chip"),

    # 半导体设备
    (["半导体设备", "光刻机", "刻蚀设备", "薄膜沉积", "量测设备",
      "清洗设备", "离子注入", "CMP", "CVD", "PVD", "ALD"],
     "semiconductor-equipment"),

    # 光模块/光通信
    (["光通信", "光模块", "光器件", "光纤", "光缆", "光芯片",
      "光互联", "硅光", "CW光源", "EML", "DSP", "AWG",
      "磷化铟", "有源器件", "无源器件", "光收发"],
     "optical-module"),

    # AI基础设施（PCB/服务器/交换机）
    (["PCB", "印制电路板", "电路板", "服务器", "交换机", "路由器",
      "网络设备", "连接器", "线缆", "覆铜板", "CCL", "载板", "HDI"],
     "ai-infrastructure"),

    # AI能源层
    (["电力", "电网", "能源", "发电", "核电", "风电", "光伏", "储能",
      "变压器", "配电设备", "输变电", "开关设备", "电力设备",
      "液冷", "温控", "散热", "冷却系统", "UPS", "电源",
      "数据中心供电", "PDU", "柴油发电机", "智能电网", "特高压"],
     "ai-energy"),

    # 液冷（更细分的能源子类）
    (["液冷", "浸没式冷却", "冷板式液冷", "CDU", "冷却液",
      "热管理", "散热模组", "风冷", "精密空调"],
     "ai-energy"),

    # 机器人
    (["机器人", "减速器", "伺服系统", "电机", "执行器", "谐波",
      "RV减速器", "步进电机", "无框电机", "力矩电机", "编码器",
      "协作机器人", "人形机器人", "工业机器人", "AGV", "AMV",
      "自动化设备", "工控", "运动控制", "数控系统", "智能制造"],
     "robotics"),

    # 大模型/AI应用
    (["大模型", "AI应用", "自然语言处理", "计算机视觉", "语音识别",
      "推荐算法", "搜索", "自动驾驶", "智慧医疗", "AI教育",
      "多模态", "生成式AI", "AIGC", "Agent", "RAG",
      "金融科技", "AI芯片设计软件"],
     "ai-model"),

    # 存储
    (["存储器", "固态硬盘", "SSD", "内存模组", "闪存控制器",
      "企业级存储", "分布式存储", "NAS", "SAN", "磁带库"],
     "storage"),
]


def match_preset_by_industry_name(industry_name: str) -> str | None:
    """根据行业名称匹配 preset"""
    if not industry_name:
        return None
    name = industry_name.lower()
    for keywords, preset in INDUSTRY_RULES:
        for kw in keywords:
            if kw.lower() in name:
                return preset
    return None


def generate_via_akshare():
    """通过 data_sources 层生成全量映射表"""
    try:
        from data_sources.industry_preset_detection import query_all_a_stock_industries
    except ImportError:
        print("❌ 无法导入 data_sources.industry_preset_detection")
        sys.exit(1)

    print("🔄 正在通过 data_sources 获取全量A股行业数据...")
    stock_rows = query_all_a_stock_industries()
    total = len(stock_rows)
    print(f"   共 {total} 只股票")

    mapping = {}
    not_matched = []

    for idx, row in enumerate(stock_rows):
        code = row["code"]
        name = row["name"]
        industry = row.get("industry", "")

        # 标准化代码
        if code.startswith(("6", "68")):
            std_code = f"{code}.SH"
        elif code.startswith(("0", "3")):
            std_code = f"{code}.SZ"
        else:
            std_code = code

        if industry:
            preset = match_preset_by_industry_name(industry)
            if preset:
                mapping[std_code] = preset
                mapping[name] = preset
            else:
                not_matched.append((std_code, name, industry))

        if (idx + 1) % 500 == 0:
            print(f"   进度: {idx + 1}/{total}...")

    # 保存
    MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 映射表已保存: {MAPPING_FILE}")
    print(f"   成功映射: {len(mapping)//2} 只股票")
    print(f"   未匹配: {len(not_matched)} 只")

    if not_matched:
        print("\n⚠️ 未匹配的股票（请检查行业关键词规则）:")
        for code, name, industry in not_matched[:20]:
            print(f"   {code} {name} — 行业: {industry}")
        if len(not_matched) > 20:
            print(f"   ... 等共 {len(not_matched)} 只")

    return mapping


def search_single_stock(stock_code: str) -> str | None:
    """用web_search搜索单只股票的行业分类"""
    # 尝试用已有数据源
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    from core.auto_detect_preset import auto_detect_preset_with_log

    preset, logs = auto_detect_preset_with_log(stock_code, DATA_DIR)
    if preset:
        print(f"✅ {stock_code} → {preset}")
        for log in logs:
            print(f"   {log}")
        return preset

    # 如果自动检测失败，输出日志
    print(f"⚠️ {stock_code} 自动检测失败日志:")
    for log in logs:
        print(f"   {log}")
    return None


def main():
    parser = argparse.ArgumentParser(description="A股行业映射生成器")
    parser.add_argument("--akshare", action="store_true", help="用akshare生成全量映射")
    parser.add_argument("--stock", type=str, help="查询单只股票")
    parser.add_argument("--batch", type=str, help="批量查询文件（每行一个代码）")
    parser.add_argument("--search", action="store_true", help="用web_search补充")
    parser.add_argument("--show-unmatched", action="store_true", help="显示未匹配的股票")
    args = parser.parse_args()

    if args.akshare:
        generate_via_akshare()
    elif args.stock:
        search_single_stock(args.stock)
    elif args.batch:
        with open(args.batch, "r") as f:
            stocks = [line.strip() for line in f if line.strip()]
        for stock in stocks:
            search_single_stock(stock)
    else:
        # 默认行为：检查当前映射表状态
        if MAPPING_FILE.exists():
            with open(MAPPING_FILE, "r") as f:
                mapping = json.load(f)
            codes = [k for k in mapping.keys() if ".SH" in k or ".SZ" in k]
            print(f"📊 当前映射表: {len(codes)} 只股票")
            print(f"   文件: {MAPPING_FILE}")
            print("\n💡 建议: 运行以下命令生成全量映射")
            print("   python scripts/generate_mapping.py --akshare")
        else:
            print("📊 当前映射表不存在")
            print("\n💡 建议:")
            print("   1. 安装akshare后生成全量映射:")
            print("      pip install akshare")
            print("      python scripts/generate_mapping.py --akshare")
            print("   2. 或查询单只股票:")
            print("      python scripts/generate_mapping.py --stock 002922")


if __name__ == "__main__":
    main()
