# 短线稳健策略执行系统

一个基于Python的智能量化交易策略执行系统，专注于A股市场的板块轮动分析和个股筛选。系统通过多维度技术分析和风险管理，为短线交易提供数据驱动的决策支持。

## 📋 项目概述

本系统是一个完整的量化交易策略执行框架，主要功能包括：

- **市场环境分析**：实时分析板块强度，识别当前市场主线方向
- **智能个股筛选**：基于技术面和基本面多维度综合评分
- **风险管理**：内置止损止盈和仓位管理规则
- **趋势跟随**：基于均线系统的趋势判断和入场信号
- **数据管理**：高效的数据获取、缓存和验证机制

## 🎯 核心功能

### 1. 市场环境分析 (`src/core/market_analyzer.py`)

- **板块强度扫描**：分析配置板块的动量、资金关注度和整体表现
- **趋势识别**：判断板块当前趋势（强势/中性/弱势）
- **推荐板块生成**：基于综合得分和策略权重推荐关注板块
- **板块内强势股分析**：识别板块内表现突出的个股

**核心指标**：
- 动量得分（基于上涨股票比例和平均涨幅）
- 成交量得分（资金关注度）
- 综合得分（加权计算）
- 趋势方向（上升/下降/震荡）

### 2. 个股筛选器 (`src/core/stock_filter.py`)

多维度筛选机制，确保选出的股票符合短线稳健策略要求：

**筛选维度**：
- **价格筛选**：过滤异常价格和ST股
- **趋势分析**：基于多周期均线判断趋势方向
- **动量评估**：5日、20日涨跌幅分析
- **成交量健康度**：近期放量/缩量判断
- **波动率控制**：过滤波动率过高的股票
- **技术形态**：均线排列、价格位置等

**评分系统**：
- 趋势得分（25%）：均线系统、价格位置
- 动量得分（25%）：短期涨幅、相对强度
- 成交量得分（20%）：放量情况、成交活跃度
- 波动率得分（15%）：风险控制
- 位置得分（15%）：价格相对位置

**输出信息**：
- 综合评分（0-100分）
- 入场信号（买入/观望/卖出）
- 止损位置建议
- 详细评分理由

### 3. 数据获取模块 (`src/data/data_fetcher.py`)

- **板块数据获取**：获取板块成分股列表和实时行情
- **历史数据获取**：支持1个月、3个月、6个月历史K线数据
- **数据标准化**：自动识别和转换列名，处理不同数据源格式
- **速率控制**：内置请求频率限制，避免API限制
- **板块名称映射**：支持板块名称别名，提高兼容性
- **调试工具**：`debug_print_all_sectors()` 函数可查看所有可用板块名称

**数据字段**：
- 股票代码、名称、当前价格、涨跌幅
- 历史K线：开盘、最高、最低、收盘、成交量

### 4. 风险管理模块 (`src/strategy/risk_manager.py`)

- **仓位管理**：根据风险等级计算最大仓位
  - 高风险股票：最大10%仓位
  - 中风险股票：最大15%仓位
  - 低风险股票：最大20%仓位
- **板块仓位限制**：单个板块最大40%仓位
- **止损止盈**：
  - 止损线：-5%（可配置）
  - 止盈线：+15%（可配置）

### 5. 趋势跟随策略 (`src/strategy/trend_follower.py`)

- **均线系统**：5日、20日均线趋势判断
- **信号生成**：看涨/看跌/中性信号
- **强度评估**：趋势强度量化评分

### 6. 数据验证与缓存

- **数据验证器** (`src/data/data_validator.py`)：验证数据完整性和质量
- **缓存管理器** (`src/data/cache_manager.py`)：减少API调用，提高效率

## 🏗️ 项目结构

```
short_term_robust_trading/
├── src/
│   ├── core/                    # 核心分析模块
│   │   ├── market_analyzer.py   # 市场环境分析器
│   │   ├── sector_scanner.py   # 板块扫描器
│   │   └── stock_filter.py     # 个股筛选器
│   │
│   ├── data/                    # 数据获取和处理
│   │   ├── data_fetcher.py     # 数据获取器（主）
│   │   ├── data_fetcher_fixed.py  # 数据获取器（修复版）
│   │   ├── cache_manager.py    # 缓存管理
│   │   └── data_validator.py   # 数据验证
│   │
│   ├── strategy/                # 策略模块
│   │   ├── trend_follower.py    # 趋势跟随策略
│   │   ├── risk_manager.py      # 风险管理
│   │   └── position_sizer.py   # 仓位计算
│   │
│   └── ui/                      # 用户界面（可选）
│       ├── dashboard.py         # 主仪表板
│       ├── sector_view.py       # 板块视图
│       └── stock_detail.py      # 个股详情
│
├── config/                      # 配置文件
│   ├── sectors.yaml            # 关注的板块配置
│   ├── strategy_params.yaml    # 策略参数
│   └── risk_rules.yaml         # 风控规则
│
├── cache/                      # 缓存数据
├── results/                    # 扫描结果（CSV格式）
├── backtests/                  # 回测结果
│
├── main.py                     # 主程序入口
├── debug_sectors.py            # 板块名称调试工具
├── test_*.py                   # 测试脚本
├── requirements.txt            # 依赖包
└── README.md                   # 项目说明
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- 推荐使用 conda 或 venv 创建虚拟环境

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

**主要依赖**：
- `akshare>=1.12.0` - 股票数据获取
- `pandas>=1.5.0` - 数据处理
- `numpy>=1.24.0` - 数值计算
- `pyyaml>=6.0` - 配置文件解析
- `streamlit>=1.28.0` - Web界面（可选）
- `plotly>=5.18.0` - 数据可视化（可选）

### 3. 配置板块

编辑 `config/sectors.yaml`，配置关注的板块：

```yaml
focus_sectors:
  - name: "有色金属"
    code: "有色金属"      # AKShare中的板块代码
    weight: 0.35         # 策略权重
    risk_level: "medium" # 风险等级：low/medium/high
```

**重要提示**：板块代码必须与AKShare中的名称完全匹配。可使用调试工具验证：

```bash
python debug_sectors.py
```

### 4. 运行主程序

```bash
python main.py
```

程序将：
1. 加载配置文件
2. 分析市场环境
3. 推荐关注板块
4. 筛选符合策略的个股
5. 生成分析报告并保存到 `results/` 目录

## ⚙️ 配置说明

### 板块配置 (`config/sectors.yaml`)

```yaml
focus_sectors:
  - name: "板块显示名称"
    code: "AKShare板块代码"  # 必须准确匹配
    weight: 0.35            # 策略权重（0-1）
    risk_level: "medium"     # low/medium/high

scan_params:
  data_period: "6mo"         # 数据周期：1mo/3mo/6mo
  min_trading_days: 60       # 最少交易日
  min_avg_volume: 10000000  # 最小日均成交量
  max_stocks_per_sector: 20 # 每板块最多分析股票数
```

### 策略参数 (`config/strategy_params.yaml`)

```yaml
strategy:
  trend_following:
    ma_short: 5      # 短期均线周期
    ma_long: 20      # 长期均线周期
  
  filters:
    min_price: 5.0      # 最低价格
    max_price: 200.0    # 最高价格
    min_volume_ratio: 1.2  # 最小成交量比率
    max_volatility: 0.4    # 最大波动率
```

### 风控规则 (`config/risk_rules.yaml`)

```yaml
risk_management:
  position:
    max_position_per_stock: 0.2    # 单股最大仓位
    max_position_per_sector: 0.4   # 单板块最大仓位
    max_total_position: 0.8        # 最大总仓位
  
  stop_loss:
    enabled: true
    loss_threshold: -0.05    # 止损线 -5%
  
  stop_profit:
    enabled: true
    profit_threshold: 0.15  # 止盈线 +15%
```

## 📊 输出结果

程序运行后会生成两个CSV文件：

1. **完整版** (`recommendations_YYYYMMDD_HHMMSS.csv`)：包含所有分析字段
2. **简化版** (`simple_recommendations_YYYYMMDD_HHMMSS.csv`)：仅包含关键字段

**关键字段说明**：
- `symbol`: 股票代码
- `name`: 股票名称
- `price`: 当前价格
- `change_pct`: 涨跌幅
- `total_score`: 综合评分（0-100）
- `entry_signal`: 入场信号（买入/观望/卖出）
- `stop_loss`: 建议止损位置
- `risk_level`: 风险等级
- `rank_reasons`: 推荐理由

## 🛠️ 调试工具

### 1. 板块名称调试

```bash
python debug_sectors.py
```

功能：
- 显示所有AKShare支持的板块名称
- 检查配置文件中的板块名称是否匹配
- 提供不匹配板块的建议修正

### 2. 数据获取测试

```bash
python src/data/data_fetcher.py
```

测试数据获取模块是否正常工作。

### 3. 市场分析器测试

```bash
python src/core/market_analyzer.py
```

测试市场环境分析功能。

## 📝 使用示例

### 基本使用流程

1. **配置板块**：编辑 `config/sectors.yaml`，设置关注的板块
2. **运行分析**：执行 `python main.py`
3. **查看结果**：在 `results/` 目录查看生成的CSV文件
4. **调整策略**：根据结果调整配置参数

### 自定义筛选条件

在 `config/sectors.yaml` 的 `scan_params` 中调整：

```yaml
scan_params:
  min_price: 10.0        # 提高最低价格要求
  max_volatility: 0.3    # 降低波动率上限
  min_5d_change: 3.0     # 提高5日涨幅要求
```

## ⚠️ 重要提示

1. **仅供学习研究**：本系统仅供学习研究使用，不构成投资建议
2. **数据来源**：使用akshare获取数据，请注意API调用频率限制
3. **实盘验证**：建议在实盘使用前进行充分回测验证
4. **风险提示**：股市有风险，投资需谨慎
5. **板块名称**：确保配置文件中的板块代码与AKShare完全匹配

## 🔧 故障排除

### 问题1：无法获取板块数据

**解决方案**：
1. 运行 `python debug_sectors.py` 查看可用板块名称
2. 检查 `config/sectors.yaml` 中的板块代码是否正确
3. 检查网络连接和akshare库版本

### 问题2：个股数据全为NaN

**解决方案**：
1. 检查股票代码格式是否正确（如：000001.SZ）
2. 尝试使用主板股票（60、00开头）而非科创板（68开头）
3. 检查日期范围是否合理

### 问题3：模块导入错误

**解决方案**：
1. 确保在项目根目录运行
2. 检查Python路径设置
3. 确认所有依赖已正确安装

## 📚 技术架构

### 数据流

```
配置文件 → 数据获取器 → 市场分析器 → 个股筛选器 → 结果输出
    ↓           ↓            ↓            ↓
  sectors   akshare    板块强度分析   多维度评分    CSV文件
```

### 核心算法

1. **板块强度计算**：
   ```
   综合得分 = 动量得分 × 0.5 + 成交量得分 × 0.3 + 涨跌幅得分 × 0.2
   ```

2. **个股评分**：
   ```
   总评分 = 趋势得分 × 0.25 + 动量得分 × 0.25 + 成交量得分 × 0.20 
         + 波动率得分 × 0.15 + 位置得分 × 0.15
   ```

3. **入场信号**：
   - 买入：总评分 ≥ 70 且趋势向上
   - 观望：总评分 60-70 或趋势不明
   - 卖出：总评分 < 60 或趋势向下

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📧 联系方式

如有问题或建议，请通过GitHub Issues联系。

---

**免责声明**：本系统仅供学习和研究使用，不构成任何投资建议。使用本系统进行实盘交易的所有风险由用户自行承担。
