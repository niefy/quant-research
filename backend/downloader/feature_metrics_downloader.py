# 币安合约交易指标数据获取
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
    response = requests.get(url, stream=True)
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


def downloadDataToCsv(symbol,start_time=dt.datetime(2024, 1, 1),end_time = dt.datetime.now()):
    """
    获取指标数据并保存到csv文件
    """

    target_dir_temp = f"{config.BACKTEST_SAMPLE_ORIGIN_DIR}/metrics/{symbol}"
    print(f'{symbol}指标数据下载开始...')
    error=0
    while start_time<=end_time:
        day = end_time.strftime("%Y-%m-%d")
        # 示例：https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-2024-01-06.zip
        url = f"https://data.binance.vision/data/futures/um/daily/metrics/{symbol}/{symbol}-metrics-{day}.zip"
        try:
            if not os.path.exists(f'{target_dir_temp}/{symbol}-metrics-{day}.csv'):
                print(f"下载指标数据:{symbol}-metrics-{day} 到 {target_dir_temp}")
                download_and_extract_zip(url, target_dir_temp)
                time.sleep(2)
        except Exception as e:
            print(e)
            if error>=3:
                print("下载失败3次，退出循环")
                break
            error+=1
        end_time = end_time - dt.timedelta(days=1)
    # target_dir = f"{config.BACKTEST_SAMPLE_DIR}/{symbol}/metrics"
    # target_file_name = f"{symbol}-metrics-merge.csv"
    # merge_csv_files(target_dir_temp, target_dir,target_file_name)
    print(f"{symbol}指标数据下载完成")