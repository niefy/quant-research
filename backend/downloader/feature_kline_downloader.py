# 币安合约K线数据获取
# 下载页面：https://www.binance.com/zh-CN/landing/data
import requests
import datetime as dt
import time
import zipfile
import io
import os
from config import config

def handle_response(response):
        """
        处理响应状态码
        :param response: 响应对象
        """
        if response.status_code == 403:
            raise Exception("违反WAF限制")
        elif response.status_code == 408:
            raise Exception("请求超时")
        elif response.status_code == 429:
            print("访问频次超限，即将被封IP")
            # raise Exception("访问频次超限，即将被封IP")
        elif response.status_code == 418:
            raise Exception("因访问频次超限已被封IP")
        elif 400 <= response.status_code < 500:
            raise Exception(f"客户端错误: {response.status_code}")
        elif 500 <= response.status_code < 600:
            raise Exception(f"服务器错误: {response.status_code}")


def download_and_extract_zip(url, extract_dir):
    """
    下载ZIP文件并解压到指定目录，不保存ZIP文件到磁盘。

    :param url: ZIP文件的URL
    :param extract_dir: 解压到的目标目录
    """
    # 发送GET请求，以流的形式获取ZIP文件
    response = requests.get(url, stream=True,proxies=config.HTTP_PROXY)
    handle_response(response)
    # 创建目录
    if not os.path.exists(extract_dir):
        # 如果文件夹不存在，创建文件夹
        os.makedirs(extract_dir)
    # 使用BytesIO创建一个内存中的文件对象
    zip_file = io.BytesIO(response.content)

    # 使用zipfile解压内存中的ZIP文件
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)  # 解压到指定目录

    #print(f'文件已下载并解压到 {extract_dir}')

def sub_one_month(dt:dt.datetime):
    """
    给datetime对象的月份-1，并返回新的datetime对象。
    """
    # 首先尝试简单地替换月份为月份-1，如果月份为1，则替换为12，并减少年份
    if dt.month == 1:
        return dt.replace(year=dt.year - 1, month=12)
    else:
        return dt.replace(month=dt.month - 1)

def add_header_if_missing(csv_files_dir):
    """
    币安部分历史行情数据表头缺失，如果CSV文件缺失表头，则添加表头。
    :param file_path: CSV文件的路径
    """
    if not os.path.exists(csv_files_dir):
        return
    header_string = "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore"
    # 遍历目录下的所有文件
    for filename in os.listdir(csv_files_dir):
        if filename.endswith('.csv'):  # 确保文件是.txt格式
            filepath = os.path.join(csv_files_dir, filename)
            
            # 读取原文件内容
            with open(filepath, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            
            # 检查首行是否包含表头
            if not lines[0].strip() == header_string:
                # 如果首行不包含表头，则在开头插入固定字符串
                lines.insert(0, f"{header_string}\n")
                # 写入修改后的文件内容
                with open(filepath, 'w', encoding='utf-8') as file:
                    file.writelines(lines)

def downloadMonthlyData(symbol,peroid="1m",start_time=dt.datetime(2024, 1, 1),end_time = dt.datetime.now()):
    """
    获取行情数据并保存到csv文件
    """
    target_dir = f"{config.BACKTEST_SAMPLE_ORIGIN_DIR}/monthly/{symbol}/{peroid}"
    error=0
    while start_time<=end_time:
        month = end_time.strftime("%Y-%m")
        # 示例：https://data.binance.vision/data/futures/um/monthly/klines/DOGEUSDT/1d/DOGEUSDT-1d-2021-01.zip
        # 现货行情示例：https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2025-02.zip
        url = f"https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/{peroid}/{symbol}-{peroid}-{month}.zip"
        try:
            if not os.path.exists(f'{target_dir}/{symbol}-{peroid}-{month}.csv'):
                print(f"下载行情数据:{url}到{target_dir}")
                download_and_extract_zip(url, target_dir)
                time.sleep(2)
        except Exception as e:
            print(e)
            error+=1
            if error>=3:
                print("下载失败3次，退出循环")
                break
            if str(e).startswith("客户端错误: 404"):
                continue
        end_time = sub_one_month(end_time)
    add_header_if_missing(target_dir)
    print(f"{symbol}行情数据下载完成")

def downloadDailyData(symbol,peroid="1m",start_time=dt.datetime(2024, 1, 1),end_time = dt.datetime.now()):
    """
    获取行情数据并保存到csv文件
    """
    target_dir = f"{config.BACKTEST_SAMPLE_ORIGIN_DIR}/daily/{symbol}/{peroid}"
    error=0
    while start_time<=end_time:
        day = end_time.strftime("%Y-%m-%d")
        print(f"下载行情数据:{symbol}-{peroid}-{day}",)
        # 示例：https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2023-08-09.zip
        url = f"https://data.binance.vision/data/futures/um/daily/klines/{symbol}/{peroid}/{symbol}-{peroid}-{day}.zip"
        try:
            if not os.path.exists(f'{target_dir}/{symbol}-{peroid}-{day}.csv'):
                download_and_extract_zip(url, target_dir)
                time.sleep(2)
        except Exception as e:
            print(e)
            if str(e).startswith("客户端错误: 404"):
                pass
            if error>=3:
                print("下载失败3次，退出循环")
                break
            error+=1
        end_time = end_time - dt.timedelta(days=1)
    add_header_if_missing(target_dir)
    print(f"{symbol}行情数据下载完成")