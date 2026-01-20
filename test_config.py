# test_config.py
"""
测试配置是否正确加载
"""
import yaml
import sys
sys.path.append('.')

def test_config():
    print("🧪 测试配置文件...")
    
    # 1. 加载配置
    with open('config/sectors.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    print("✅ 配置文件加载成功")
    
    # 2. 检查focus_sectors
    focus_sectors = config.get('focus_sectors', [])
    print(f"✅ 关注板块数量: {len(focus_sectors)}")
    
    for i, sector in enumerate(focus_sectors, 1):
        print(f"   {i}. {sector['name']} (代码: {sector['code']})")
    
    # 3. 检查scan_params
    scan_params = config.get('scan_params', {})
    print(f"\n✅ 扫描参数数量: {len(scan_params)}")
    
    # 检查关键参数是否存在
    required_params = ['min_price', 'max_price', 'min_volume', 'min_trading_days']
    for param in required_params:
        if param in scan_params:
            print(f"   ✅ {param}: {scan_params[param]}")
        else:
            print(f"   ❌ {param}: 缺失!")
    
    # 4. 测试权重配置
    weights = scan_params.get('weights', {})
    print(f"\n✅ 权重配置:")
    for key, value in weights.items():
        print(f"   {key}: {value}")
    
    return config

if __name__ == "__main__":
    config = test_config()