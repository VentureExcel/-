# V4.1 / V4.2 回测框架

```
pip install pandas numpy pyyaml openpyxl matplotlib        # 非 SQLite 库另装 sqlalchemy + 驱动
python selftest.py                                         # ① 先自检(合成数据),必须全部 PASS
cp config.example.yaml config.yaml                         # ② 改成你的库/表/列
python run_backtest.py --config config.yaml --exp E1       # ③ 先跑单因子体检,看信号有没有
python run_backtest.py --config config.yaml --exp E2,E3,E4,E5,E6,E7,E8,E9 --out out/
python run_backtest.py --config config.synthetic.yaml --synthetic --exp E1,E2 --out out_synth/   # 无库时演示
```

| 模块 | 作用 |
|---|---|
| `bt/data.py` | 数据库→宽表面板;列映射;数据体检(缺失、单位、复权异常) |
| `bt/factors.py` | 特征与因子(资金占成交额比、60 日异常 z、净流入连续天数、涨跌停价等);V4.1 的 Overheat/压力位按报告口径复刻 |
| `bt/strategies.py` | `v41`(复刻)与 `v42`(优化版:中性化、动量/反转子策略、大盘闸门);`V41_HOOK` 可挂生产评分函数 |
| `bt/engine.py` | T 收盘出信号→T+1 开盘成交;T+1、涨停买不到、停牌、跌停锁死、止损/止盈/时间退出;佣金/印花税/过户费/滑点/冲击;容量约束 |
| `bt/metrics.py` | IC/RankIC、NW t 值、分层收益、夏普/回撤/超额/信息比率、通缩夏普、块自助法 |
| `bt/experiments.py` | E1~E9 实验矩阵 |

## 已知近似(请在报告中披露)
1. 组合为"逐日分仓、固定名义"近似,未逐日再平衡漂移;未按 100 股取整(以权重计)。
2. 止损用最低价(次日起)触发,跳空按开盘价成交;未模拟盘中涨跌停打开的细节。
3. V4.1 的子因子(资金集中度、加速度、"跌透反弹"加分等)按报告文字复刻,**必须与生产脚本对齐**(见 CLAUDE_CODE_TASK.md 第 3 步)。
4. 合成数据的结果只证明"机器没坏",**不是策略证据**。
