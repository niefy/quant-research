import requests
import json
import os
import logging
from config import config
from datetime import datetime

DATA_DIR = '.data'

def get_market_basic_data():
    url_path = config.FAPI_BASE_URL+"/fapi/v1/exchangeInfo"
    response = requests.get(url_path, proxies=config.HTTP_PROXY)
    if response.status_code == 200:
        return response.json()
    print(f"Error: {response.status_code}")
    raise response.text
    
def download_market_symbols_data():
    resJson = get_market_basic_data()
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    symbols = resJson['symbols']
    # 只保留USDT 永续合约 的数据
    filtered_data = [item for item in symbols if item['quoteAsset'] == 'USDT' and item['contractType'] == 'PERPETUAL']
    with open(f'{DATA_DIR}/market_symbols_data.json', 'w', encoding='utf-8') as file:
            json.dump(filtered_data, file, ensure_ascii=False, indent=4)
    print("Downloaded market symbols data successfully.")

def get_24h_price_all():
    url_path = config.FAPI_BASE_URL+"/fapi/v1/ticker/24hr"
    response = requests.get(url_path, proxies=config.HTTP_PROXY)
    if response.status_code != 200:
        raise response.text
    resJson = response.json()
    return resJson

def download_24h_symbols():
    stat_list = get_24h_price_all()
    sorted_list = sorted(stat_list, key=lambda item: float(item["quoteVolume"]), reverse=True)
    date = datetime.now().strftime("%Y-%m-%d")
    with open(f'{DATA_DIR}/24h_price.{date}.json', 'w', encoding='utf-8') as file:
        json.dump(sorted_list, file, ensure_ascii=False, indent=4)
    symbol_list = [item["symbol"] for item in sorted_list if item['symbol'].endswith('USDT')]
    print(f"24h 成交量倒序: {symbol_list[:10]}")
    print("Downloaded 24h symbols data successfully.")

def sum_24h_data():
    # 扫描文件
    files = os.listdir(DATA_DIR)
    result = {}
    for file in files:
        if file.startswith("24h_price.") and file.endswith(".json"):
            print(f"处理文件: {file}")
            with open(f'{DATA_DIR}/{file}', 'r', encoding='utf-8') as f:
                list = json.load(f)
                for item in list:
                    symbol = item["symbol"]
                    quoteVolume = float(item["quoteVolume"])
                    if symbol in result:
                        result[symbol] += quoteVolume
                    else:
                        result[symbol] = quoteVolume
    # 排序
    sorted_result = sorted(result.items(), key=lambda item: item[1], reverse=True)
    symbol_list = [item[0] for item in sorted_result if item[0].endswith('USDT')]
    print(f"总成交量倒序: {symbol_list[:100]}")

if __name__ == "__main__":
    download_24h_symbols()
    sum_24h_data()