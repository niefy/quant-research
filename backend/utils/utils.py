import csv
import os
import random
import time
import string
import polars as pl
from config import config
from config.log import log


def write_to_csv(filename, header, data_row):
    """
    将数据写入CSV文件。

    Windows 下若文件被其它进程（如 IDE 文件监视器、实时报表服务）占用，
    open(..., "a") 会偶发抛 PermissionError（共享冲突，Errno 13）。这里对
    PermissionError 做短时退避重试，避免回测报告写入偶发失败导致整个回测崩溃。
    """
    import time as _time
    last_err = None
    for _attempt in range(5):
        try:
            if not os.path.exists(filename):
                # 文件不存在，创建文件并写入表头
                with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(header)  # 写入表头
                    writer.writerow(data_row)
            else:
                # 文件已存在，直接写入行数据
                with open(filename, "a", newline="", encoding="utf-8-sig") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(data_row)  # 追加写入行数据
            return
        except PermissionError as e:
            last_err = e
            _time.sleep(0.3 * (_attempt + 1))  # 0.3s, 0.6s, 0.9s, 1.2s
    # 重试耗尽仍失败，原样抛出，避免静默丢失数据
    raise last_err

def to_pd_period(backtest_period):
    if backtest_period.endswith("m"):
        return backtest_period.replace("m", "min")
    elif backtest_period.endswith("h"):
        return backtest_period
    elif backtest_period.endswith("d"):
        return backtest_period.replace("d", "D")
    else:
        raise Exception('不支持的周期')

def period_to_s(backtest_period):
    if backtest_period.endswith("m"):
        return int(backtest_period[:-1]) * 60
    elif backtest_period.endswith("h"):
        return int(backtest_period[:-1]) * 60 * 60
    elif backtest_period.endswith("d"):
        return int(backtest_period[:-1]) * 24 * 60 * 60
    else:
        raise Exception('不支持的周期')

def generate_random_string(length):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

def read_files_to_df(symbol,period, all_columns=False,cut_time=True):
    """
    读取指定目录下的所有CSV文件，并合并到一个DataFrame中。

    :param directory: 包含CSV文件的目录路径
    :return: 合并后的DataFrame，index为datetime
    """
    usecols = None
    if not all_columns:
        usecols = ['datetime','open','high','low','close','volume']
    base_dir = f'{config.BACKTEST_SAMPLE_DIR}/{symbol}'
    single_file = f'{base_dir}/{symbol}-{period}.parquet'
    if not os.path.exists(single_file):
        log.error(f'{single_file} not exists')
        return None
    # 读取数据和过滤连一起有助于提升性能
    df = pl.read_parquet(single_file,columns=usecols).filter(
        (pl.col("datetime")>=config.BACKTEST_START_TIME.timestamp() if config.BACKTEST_START_TIME is not None and cut_time else True) &
        (pl.col("datetime")<=config.BACKTEST_END_TIME.timestamp() if config.BACKTEST_END_TIME is not None  and cut_time else True)
    )
    if not len(df):
        return None
    return df

def read_metrics_to_df(symbol="BTCUSDT",period="1d",all_columns=False):
    """
    读取指定目录下的所有CSV文件，并合并到一个DataFrame中。

    :param directory: 包含CSV文件的目录路径
    :return: 合并后的DataFrame，index为datetime
    """
    usecols = None
    if not all_columns:
        usecols = ['datetime','count_long_short_ratio']
    file_path = f'{config.BACKTEST_SAMPLE_DIR}/{symbol}/metrics/{symbol}-{period}.parquet'
    if not os.path.exists(file_path):
        raise Exception(f'{file_path} not exists')
    # 读取数据和过滤连一起有助于提升性能
    df = pl.read_parquet(file_path,columns=usecols).filter(
        (pl.col("datetime")>=config.BACKTEST_START_TIME.timestamp() if config.BACKTEST_START_TIME is not None else True) &
        (pl.col("datetime")<=config.BACKTEST_END_TIME.timestamp() if config.BACKTEST_END_TIME is not None else True)
    )
    if not len(df):
        return None
    return df

def add_one_month(dt):
    """
    给datetime对象的月份+1，并返回新的datetime对象。
    """
    if dt.month == 12:
        return dt.replace(year=dt.year + 1, month=1)
    else:
        return dt.replace(month=dt.month + 1)