from datetime import datetime
import json
import os

# API
FAPI_BASE_URL = "https://fapi.binance.com"
HTTP_PROXY = {"https": "http://127.0.0.1:7890"}

# 手续费率
CM_RATE = 0.05/100
# 滑点
SLIPPAGE = 0.03/100
# 固定止损比例
FIXED_STOP_LOSE = None
# 固定止盈比例
FIXED_TAKE_PROFIT = None
# 追踪止损激活价格比例，如100开多，此参数设为1%，则在价格达到101时才才会激活追踪止损，设置0则开仓价激活
TRAILING_ACTIVE_RATE = 0/100
# 追踪止损最大回调价格比例
TRAILING_CALLBACK_RATE = 0/100

# 回测数据目录
BACKTEST_SAMPLE_ORIGIN_DIR = '../../binance_data_origin'
BACKTEST_SAMPLE_DIR = '../../binance_data'
# 回测代码列表[202608市值前100]
_BACKTEST_SYMBOL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "top100_symbols.json")
if os.path.exists(_BACKTEST_SYMBOL_FILE):
    with open(_BACKTEST_SYMBOL_FILE, "r", encoding="utf-8") as f:
        BACKTEST_SYMBOL_ALL = json.load(f)
else:
    BACKTEST_SYMBOL_ALL = []
    print(f"[warn] 未找到 {_BACKTEST_SYMBOL_FILE}，请先运行 downloader/top100_symbols_downloader.py")
BACKTEST_SYMBOL = BACKTEST_SYMBOL_ALL[:50]

# 回测开始时间
BACKTEST_START_TIME = datetime(2020, 1, 1)
BACKTEST_END_TIME = datetime(2026, 8, 1)

# 初始资金
INIT_CASH = 10000
# 杠杆倍数
LEVERAGE = 5
# 资金利用率 0-1 (每仓目标资金乘以此系数, 用于控制回撤)
EXPOSURE = 1.0
# 最大持有币种
MAX_HOLD_SYMBOL = min(5,len(BACKTEST_SYMBOL))
# 每币种最大开仓次数
MAX_SLOT_PER_SYMBOL = 1

# 是否打印回测进度
PRINT_PROGRESS = True
# 是否导出报表明细记录（交易记录、持仓记录、指标数据等）
EXPORT_RESULT_DETAIL = True
# 最大保留报表记录数
MAX_REPORT_RECORD = 5