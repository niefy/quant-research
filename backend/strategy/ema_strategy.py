from config import config
from backtest import BackTest
from backtest import utils
from collections import defaultdict
import polars_talib as plta
import polars as pl

"""
EMA均线策略
"""
class EmaStrategy(BackTest):
    def __init__(self,period, feed,properties={}):
        self.strategy_name = "EmaStrategy"
        self.strategy_desc = "固定标的,设置止盈止盈：adjust=False"
        default_properties = {"ma_short":12,"ma_long":300,"entry_index":[1],"take_profit":2}
        self.properties = {**default_properties, **properties}
        self.prev_tick = defaultdict(lambda: None)
        self.cross_count = defaultdict(lambda: int)
        super().__init__(period,feed)

    def initialize(self,symbol,df):
        df = df.with_columns(
            pl.col("close").ta.ema(self.properties['ma_short']).alias("ma_short"),
            pl.col("close").ta.ema(self.properties['ma_long']).alias("ma_long"),
        )
        self.cross_count[symbol] = 0
        return df
        

    def on_tick(self,tick_time,symbol, tick_data):
        # self.log(f'{symbol} on tick：{tick}')
        
        
        if len(tick_data)<2 or tick_data['ma_long'][-2] is None:
            return
        hold_shares = self.broker.get_shares(symbol)
        # 平仓逻辑
        if hold_shares > 0 and tick_data['ma_short'][-1] < tick_data['ma_long'][-1]:
            self.broker.exit_market(symbol, -hold_shares,msg="ema_cross")
        elif hold_shares > 0 and tick_data['ma_short'][-1] > tick_data['ma_long'][-1]*self.properties["take_profit"]:
            self.broker.exit_market(symbol, -hold_shares,msg="take_profitx止盈")
        elif hold_shares < 0 and tick_data['ma_short'][-1] > tick_data['ma_long'][-1]:
            self.broker.exit_market(symbol, -hold_shares,msg="ema_cross")
        elif hold_shares < 0 and tick_data['ma_short'][-1] < tick_data['ma_long'][-1]*(1/self.properties["take_profit"]):
            self.broker.exit_market(symbol, -hold_shares,msg="take_profitx止盈")
        # 开仓逻辑
        ema_cross_over = tick_data['ma_short'][-2] <= tick_data['ma_long'][-2] and tick_data['ma_short'][-1] > tick_data['ma_long'][-1]
        ema_cross_under = tick_data['ma_short'][-2] >= tick_data['ma_long'][-2] and tick_data['ma_short'][-1] < tick_data['ma_long'][-1]
        if ema_cross_over or ema_cross_under:
            self.cross_count[symbol] = 0
        else:
            self.cross_count[symbol] += 1

        if not self.cross_count[symbol] in self.properties["entry_index"]: 
            return
        if tick_data['close'][-1] > tick_data['open'][-1] and tick_data['ma_short'][-1] > tick_data['ma_long'][-1]:
            self.broker.entry_long(symbol, msg=f"ma_long_{self.cross_count[symbol]}")
        elif tick_data['close'][-1] < tick_data['open'][-1] and tick_data['ma_short'][-1] < tick_data['ma_long'][-1]:
            self.broker.entry_short(symbol, msg=f"ma_short_{self.cross_count[symbol]}")


def run(period:str,properties={}):
    feed = {}
    for symbol in config.BACKTEST_SYMBOL:
        feed[symbol] = utils.read_files_to_df(symbol,period)
    mytest = EmaStrategy(period,feed,properties)
    mytest.start()
