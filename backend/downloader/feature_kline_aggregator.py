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
    dtypes={'datetime': pl.Int64,'open': pl.Float64, 'high': pl.Float64, 'low': pl.Float64, 'close': pl.Float64, 'volume': pl.Float64, 'quote_volume': pl.Float64, 'count': pl.Int64, 'taker_buy_volume': pl.Float64, 'taker_buy_quote_volume': pl.Float64}
    dfs = [pl.scan_csv(file,dtypes=dtypes) for file in csv_files]
    df = pl.concat(dfs).collect()
    df = df.with_columns(
        pl.col('open_time').cast(pl.Datetime(time_unit='ms')).alias('datetime')
    )
    return df

# 聚合函数
def _aggregate_data(df, time_period):
    # 根据时间周期重新采样
    resampled = df.group_by_dynamic("datetime",every=time_period,closed="left").agg([
        pl.col('open').first().alias('open'),
        pl.col('high').max().alias('high'),
        pl.col('low').min().alias('low'),
        pl.col('close').last().alias('close'),
        pl.col('close_time').last().alias('close_time'),
        pl.col('volume').sum().alias('volume'),
        pl.col('quote_volume').sum().alias('quote_volume'),
        pl.col('count').sum().alias('count'),
        pl.col('taker_buy_volume').sum().alias('taker_buy_volume'),
        pl.col('taker_buy_quote_volume').sum().alias('taker_buy_quote_volume')
    ])
    return resampled

def fill_missing_data(df,source_period):
    """补全中间缺失的数据"""
    # 创建完整的时间索引
    df_filled  = df.upsample(time_column="datetime", every=source_period).fill_null(strategy="forward")
    return df_filled

def _save_data_to_file(df, symbol, period):
    # 创建目录
    traget_dir = f'{config.BACKTEST_SAMPLE_DIR}/{symbol}/'
    if not os.path.exists(traget_dir):
        # 如果文件夹不存在，创建文件夹
        os.makedirs(traget_dir)
    # df = df.drop(['datetime'])
    # 保存到CSV文件
    df = df.with_columns(
        ((pl.col("close_time")+1)/1000).cast(pl.Int64).alias("datetime")  # 将时间转为时间戳保存
    )
    df = df.drop("close_time")
    df.write_parquet(f'{traget_dir}/{symbol}-{period}.parquet')
    # df.write_csv(f'{traget_dir}/{symbol}-{period}.csv')


def aggregate_kline_data(symbol, target_periods,source_period="1h",source_type="monthly"):
    """
    聚合K线数据，并保存到CSV文件中
    从1h周期聚合到指定4h/8h/1d周期
    :param symbol: 交易对
    :param period: 目标周期，例如4h/8h/1d
    """
    print(f'合并K线数据：{symbol}，周期：{target_periods}')
    df = _read_csv_files_to_df(f'{config.BACKTEST_SAMPLE_ORIGIN_DIR}/{source_type}/{symbol}/{source_period}')
    if  df is None or len(df) == 0:
        print(f'没有{source_period}数据，跳过：{symbol}')
        return
    df = fill_missing_data(df,source_period)
    for target_period in target_periods:
        result = _aggregate_data(df, target_period)
        _save_data_to_file(result, symbol, target_period)