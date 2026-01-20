# test_direct_akshare.py
"""
直接测试akshare接口，找出问题根源
"""
import akshare as ak
import pandas as pd
from datetime import datetime

def test_direct():
    print("=" * 60)
    print("直接测试akshare接口")
    print("=" * 60)
    
    # 测试1: 测试平安银行
    print("\n1. 测试平安银行 (000001.SZ):")
    try:
        df = ak.stock_zh_a_hist(
            symbol="000001",
            period="daily",
            start_date="20250101",
            end_date="20250112",
            adjust="qfq"
        )
        
        print(f"数据形状: {df.shape}")
        print(f"列名: {list(df.columns)}")
        print(f"数据类型:\n{df.dtypes}")
        
        print("\n前3行数据:")
        print(df.head(3))
        
        print("\n列详细信息:")
        for i, col in enumerate(df.columns):
            print(f"  {i}: '{col}' (类型: {df[col].dtype})")
            
            # 显示前几个值
            if len(df) > 0:
                sample = df[col].iloc[0]
                print(f"      示例值: {sample} (类型: {type(sample)})")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试2: 测试贵州茅台
    print("\n" + "=" * 60)
    print("2. 测试贵州茅台 (600519.SS):")
    try:
        df = ak.stock_zh_a_hist(
            symbol="600519",
            period="daily",
            start_date="20250101",
            end_date="20250112",
            adjust="qfq"
        )
        
        print(f"数据形状: {df.shape}")
        print(f"前3行数据:")
        print(df.head(3))
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试3: 测试akshare的版本和可用性
    print("\n" + "=" * 60)
    print("3. 测试akshare版本和功能:")
    try:
        print(f"akshare版本: {ak.__version__}")
        
        # 测试其他接口
        print("\n测试其他数据接口:")
        
        # 测试A股列表
        stock_list = ak.stock_info_a_code_name()
        print(f"A股列表: {len(stock_list)} 只股票")
        
        # 测试板块列表
        sector_list = ak.stock_board_industry_name_em()
        print(f"板块列表: {len(sector_list)} 个板块")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试4: 测试创业板股票
    print("\n" + "=" * 60)
    print("4. 测试创业板股票 (300337.SZ - 银邦股份):")
    try:
        df = ak.stock_zh_a_hist(
            symbol="300337",
            period="daily",
            start_date="20250101",
            end_date="20250112",
            adjust="qfq"
        )
        
        print(f"数据形状: {df.shape}")
        print(f"列名: {list(df.columns)}")
        print(f"前3行数据:")
        print(df.head(3))
        
        # 详细分析列
        print("\n列详细分析:")
        for col in df.columns:
            print(f"\n列 '{col}':")
            print(f"  类型: {df[col].dtype}")
            print(f"  非空值数量: {df[col].notna().sum()}/{len(df)}")
            if df[col].notna().sum() > 0:
                print(f"  示例值: {df[col].dropna().iloc[0]}")
                if df[col].dtype in ['float64', 'int64']:
                    print(f"  数值范围: [{df[col].min()}, {df[col].max()}]")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("直接测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_direct()
