"""
板块视图
"""
import streamlit as st
import pandas as pd
from typing import Dict, List

def render_sector_view(sector_info: Dict, stocks: List[Dict]):
    """渲染板块视图"""
    st.header(f"📁 {sector_info['sector_name']}")
    
    st.subheader("板块信息")
    col1, col2, col3 = st.columns(3)
    col1.metric("强度得分", f"{sector_info.get('score', 0):.1f}")
    col2.metric("风险等级", sector_info.get('risk_level', 'medium'))
    col3.metric("推荐强度", sector_info.get('strength', '中性'))
    
    st.subheader("板块内个股")
    if stocks:
        stocks_df = pd.DataFrame(stocks)
        st.dataframe(stocks_df, use_container_width=True)
    else:
        st.info("该板块暂无推荐个股")
