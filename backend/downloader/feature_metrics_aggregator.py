import os
import polars as pl
from pathlib import Path
from config import config


def _read_csv_files_to_df(directory):
    """
    读取指定目录下的所有CSV文件，并合并到一个DataFrame中。

    :param directory: 包含CSV文件的目录路径
    :return: 合并后的DataFrame
    """
    if not os.path.exists(directory):
        return None
    csv_files = list(Path(directory).glob('*.csv'))
    
    dtypes={
        "create_time": pl.String,
        "symbol": pl.String,
        "sum_open_interest":pl.Float32,
        "sum_open_interest_value":pl.Float32,
        "count_toptrader_long_short_ratio":pl.Float32,
        "sum_toptrader_long_short_ratio":pl.Float32,
        "count_long_short_ratio":pl.Float32,
        "sum_taker_long_short_vol_ratio":pl.Float32
    }
    dfs = [pl.scan_csv(file,dtypes = dtypes) for file in csv_files]
    df = pl.concat(dfs).collect()
    # 原始数据是UTC时间，create_time为开始时间，我们需要往后偏移5m变为周期结束时间
    df = df.with_columns(
        (pl.col('create_time').str.strptime(pl.Datetime("ms",time_zone="UTC"), format='%Y-%m-%d %H:%M:%S') + pl.duration(minutes=5)).alias('datetime')
    )
    return df

# 按币安官方实时接口字段命名处理数据
def _aggregate_data(df):
    # 根据时间周期重新采样,对比官网实时数据做调整
    df = df.sort("datetime")
    # df = df.rename({
    #     "col1": "new1",
    #     "col1": "new1",
    #     "col1": "new1",
    #     "col1": "new1",
    #     "col1": "new1",
    #     "col1": "new1",
    #     "col1": "new1",
    #     "col2": "new2"
    # })
    return df

def _save_data_to_file(df, symbol):
    # 创建目录
    traget_dir = f'{config.BACKTEST_SAMPLE_DIR}/{symbol}'
    if not os.path.exists(traget_dir):
        # 如果文件夹不存在，创建文件夹
        os.makedirs(traget_dir)
    df = df.drop(['create_time'])
    df = df.with_columns(
        pl.col("datetime").dt.epoch("s").alias("datetime")  # 将时间转为时间戳保存
    )
    # 保存到CSV文件
    target_file = f'{traget_dir}/metrics-{symbol}.parquet'
    df.write_parquet(target_file)
    # df.write_csv(target_file)
    print(f'指标数据已保存到：{target_file}')


def aggregate_metrics_data(symbol):
    """
    转换指标数据，统一以周期结束时间作为datetime,并保存到parquet文件中
    :param symbol: 交易对
    """
    print(f'转换指标数据：{symbol}')
    df = _read_csv_files_to_df(f'{config.BACKTEST_SAMPLE_ORIGIN_DIR}/metrics/{symbol}')
    if  df is None or len(df) == 0:
        print(f'没有{config.BACKTEST_SAMPLE_ORIGIN_DIR}/metrics/{symbol}数据，跳过：{symbol}')
        return
    result = _aggregate_data(df)
    _save_data_to_file(result, symbol)
