#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建「按市值排序的 Binance USDⓈ-M 永续合约前 N 标的」列表。

数据来源（生产环境，当前环境无法直连，故用本地文件测试）：
  exchangeInfo : https://fapi.binance.com/fapi/v1/exchangeInfo
  markets      : https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=300&page=1

本地测试文件：
  - exchangeInfo.json          （本地副本）
  - market.json                （自动合并 markets_01/02/03.json）

处理规则：
  1) 仅保留 USDT 报价的合约（即 symbol 以 USDT 结尾的永续/交割）。
  2) 剔除「同类币种兑换」合约：baseAsset 为稳定币/报价币种者（如 USDCUSDT、FRAXUSDT、STABLEUSDT）。
  3) 处理 Binance 的乘数 baseAsset：市值标的 symbol（如 pepe）应映射到
     合约 baseAsset 的乘数变体（1000PEPE、1000000MOG...），不能丢。
     匹配用正则 ^\\d*<SYMBOL大写>$，任意位数乘数前缀（10/100/1000/10000...）
     都能命中，精确匹配（无前缀）优先。
  4) 上市时间(onboardDate)过滤，方向由 LISTING 开关控制（见下方配置）。

"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

# ========================= 配置区 =========================
# 本地测试时数据文件所在目录（生产环境改成你的工作目录，或把文件放到脚本同目录）
BASE_DIR = r".sample"

EXCHANGE_INFO_PATH = os.path.join(BASE_DIR, "exchangeInfo.json")
MARKET_JSON_PATH   = os.path.join(BASE_DIR, "market.json")   # 生产：CoinGecko 单文件 300 行
MARKET_SPLIT_FILES = [os.path.join(BASE_DIR, f) for f in
                      ["markets_01.json", "markets_02.json", "markets_03.json"]]
TOP_N              = 100
# 结果写出路径（相对脚本运行目录）
OUTPUT_PATH        = "config/top100_symbols.json"

# 上市时间过滤的截止点
LISTING_CUTOFF = datetime(2026, 7, 1, tzinfo=timezone.utc)
# =========================================================

# 规则 2：需要剔除的「同类币种兑换」baseAsset（稳定币 / 报价币种）
STABLE_BASES = {
    "USDT", "USDC", "DAI", "USDF", "USDA", "FDUSD", "TUSD", "BUSD", "USDD", "PYUSD",
    "EURT", "GUSD", "FRAX", "LUSD", "SUSD", "USDE", "USD1", "USDP", "USTC", "USDN",
    "CUSD", "MIM", "ALUSD", "FEI", "HUSD", "EURS", "XSGD", "USDK", "USDG", "STABLE",
}


def load_exchange_info(path=EXCHANGE_INFO_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_market_data():
    """加载 CoinGecko 市值数据；优先 market.json，缺失则合并分片文件。"""
    rows = []
    if os.path.exists(MARKET_JSON_PATH):
        with open(MARKET_JSON_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
    else:
        for fn in MARKET_SPLIT_FILES:
            if os.path.exists(fn):
                with open(fn, "r", encoding="utf-8") as f:
                    rows.extend(json.load(f))
    # 按市值排名升序（排名越小市值越高）
    rows.sort(key=lambda m: m["market_cap_rank"])
    return rows


def candidate_bases(market_symbol, by_base):
    """市值标的 -> 候选 baseAsset（按匹配优先级排序，只返回 by_base 中真实存在的）。

    用正则匹配任意位数乘数前缀（10/100/1000/10000/1000000...），不硬编码枚举，
    避免漏掉新上架的乘数合约（如 1000000MOG）。
    顺序：精确匹配（无前缀）优先，乘数前缀越短越优先。"""
    u = market_symbol.upper()
    pat = re.compile(r"^\d*" + re.escape(u) + r"$")
    return sorted(
        (b for b in by_base if pat.fullmatch(b)),
        key=lambda b: len(b) - len(u),  # 前缀数字长度；0 即精确匹配
    )


def build_symbol_list(top_n=TOP_N):
    ei = load_exchange_info()
    markets = load_market_data()
    cutoff_ms = int(LISTING_CUTOFF.timestamp() * 1000)

    # 按 baseAsset 建索引，同时套用规则 1(USDT) + 2(稳定币) + 4(上市时间)
    by_base = defaultdict(list)
    for s in ei["symbols"]:
        if s["quoteAsset"] != "USDT":
            continue
        if s["baseAsset"] in STABLE_BASES:
            continue
        if s["onboardDate"] >= cutoff_ms:
            continue
        by_base[s["baseAsset"]].append(s)

    # 按市值从高到低匹配，规则 3 的 1000 倍处理在这里生效
    result = []
    seen = set()
    for m in markets:
        for cand in candidate_bases(m["symbol"], by_base):
            # 同一 baseAsset 下优先 PERPETUAL
            cands = sorted(
                by_base[cand],
                key=lambda x: 0 if x["contractType"] == "PERPETUAL" else 1,
            )
            sym = cands[0]["symbol"]
            if sym in seen:
                continue
            seen.add(sym)
            result.append((m["market_cap_rank"], sym))
            break  # 这个市值标的已匹配，跳出候选尝试

    result.sort(key=lambda x: x[0])
    return [sym for _, sym in result[:top_n]]


def _self_check():
    """打印各阶段计数，便于核对流程。"""
    ei = load_exchange_info()
    markets = load_market_data()
    cutoff_ms = int(LISTING_CUTOFF.timestamp() * 1000)

    usdt = [s for s in ei["symbols"] if s["quoteAsset"] == "USDT"]
    non_stable = [s for s in usdt if s["baseAsset"] not in STABLE_BASES]
    eligible = [s for s in non_stable if s["onboardDate"] < cutoff_ms]

    print(f"[check] USDT 合约总数            : {len(usdt)}", file=sys.stderr)
    print(f"[check] 剔除稳定币后            : {len(non_stable)}", file=sys.stderr)
    print(f"[check] 叠加上市时间过滤后(候选): {len(eligible)}", file=sys.stderr)
    print(f"[check] 市值数据条数            : {len(markets)}", file=sys.stderr)


if __name__ == "__main__":
    _self_check()
    syms = build_symbol_list()
    # 同时输出到 stdout（便于管道）和本地文件
    print(json.dumps(syms, ensure_ascii=False))
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(syms, f, ensure_ascii=False, indent=2)
    print(f"[done] 已写出 {OUTPUT_PATH}，实际数量={len(syms)}", file=sys.stderr)
