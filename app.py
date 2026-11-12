"""冷链优化智能体 · Streamlit 前端"""
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import amap, tools
from cn_params import COST_NOTES
from tools import PRODUCTS, VEHICLES, COST

st.set_page_config(
    page_title="冷链优化智能体",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    html, body, [class*="css"]  {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    }
    .stApp { background-color: #0a0a0a; }
    section[data-testid="stSidebar"] {
        background-color: #111111;
        border-right: 1px solid #2a2a2a;
    }
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p {
        color: #e8d5a3 !important;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: #141414;
        padding: 4px;
        border-radius: 8px;
        border: 1px solid #2a2a2a;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
        color: #a89060;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #1a1508 0%, #2a2210 100%) !important;
        color: #f0d78c !important;
        border: 1px solid #c9a227 !important;
    }
    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #141414 0%, #1a1508 100%);
        border: 1px solid #3d3420;
        border-radius: 10px;
        padding: 14px 16px;
        box-shadow: 0 2px 8px rgba(201, 162, 39, 0.08);
    }
    [data-testid="stMetricLabel"] { color: #c9a227; font-size: 0.85rem; }
    [data-testid="stMetricValue"] { color: #f5e6b8 !important; }
    /* Buttons */
    .stButton > button {
        border-radius: 6px;
        font-weight: 500;
        border: 1px solid #3d3420;
        background: #1a1a1a;
        color: #e8d5a3;
    }
    .stButton > button:hover {
        border-color: #c9a227;
        color: #f0d78c;
        background: #1f1a0a;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #c9a227 0%, #a67c00 100%);
        border-color: #c9a227;
        color: #0a0a0a;
        font-weight: 600;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #dfb73a 0%, #c9a227 100%);
        border-color: #dfb73a;
        color: #0a0a0a;
    }
    /* Inputs */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div,
    .stTextArea textarea {
        background-color: #141414 !important;
        border: 1px solid #3d3420 !important;
        border-radius: 6px !important;
        color: #f5e6b8 !important;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: #c9a227 !important;
        box-shadow: 0 0 0 1px #c9a22733 !important;
    }
    /* Slider */
    .stSlider [data-baseweb="slider"] div[role="slider"] {
        background-color: #c9a227 !important;
    }
    /* Dataframe */
    .stDataFrame {
        border: 1px solid #3d3420;
        border-radius: 8px;
        overflow: hidden;
    }
    hr { border-color: #2a2a2a; }
    .stCaption { color: #a89060 !important; font-size: 0.8rem; }
    /* Headers & text */
    h1, h2, h3, h4 { color: #f0d78c !important; }
    p, span, label, .stMarkdown { color: #d4c4a0; }
    /* Radio / checkbox */
    .stRadio label, .stCheckbox label { color: #e8d5a3 !important; }
    /* Expander */
    .streamlit-expanderHeader {
        background: #141414 !important;
        color: #e8d5a3 !important;
        border: 1px solid #3d3420 !important;
        border-radius: 6px !important;
    }
    /* Success / warning / error / info */
    .stAlert { border-radius: 8px; }
    /* Chat */
    [data-testid="stChatMessage"] {
        background: #141414;
        border: 1px solid #2a2a2a;
        border-radius: 10px;
    }
    footer { visibility: hidden; }
    /* Scrollbar */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: #0a0a0a; }
    ::-webkit-scrollbar-thumb { background: #3d3420; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #c9a227; }
</style>
""", unsafe_allow_html=True)

PK = list(PRODUCTS)
fmt = lambda k: f"{PRODUCTS[k]['name']}  {PRODUCTS[k]['lo']}~{PRODUCTS[k]['hi']}℃"
COLS = ["name", "address", "lat", "lng", "win_start", "win_end", "dwell", "demand"]
COLORS = ["#c9a227", "#e8d5a3", "#a67c00", "#f0d78c", "#8b7355", "#dfb73a"]

DEFAULT_AMAP_KEY = "ea39c391cab1aaf7bfb9d23189c383fc"

def to_df(stops):
    return pd.DataFrame(
        [[s["name"], s.get("address", ""), s["lat"], s["lng"], s["win"][0], s["win"][1], s["dwell"], s.get("demand", 0)]
         for s in stops],
        columns=COLS,
    )

def to_stops(df):
    nz = lambda v, d: d if pd.isna(v) else float(v)
    df = df.dropna(subset=["name"])
    miss = df[df.lat.isna() | df.lng.isna()]
    if len(miss):
        raise ValueError(f"「{'、'.join(map(str, miss['name']))}」缺少坐标，请先解析地址或手动填写经纬度")
    return [
        {
            "name": str(r.name_),
            "address": "" if pd.isna(r.address) else str(r.address),
            "lat": float(r.lat),
            "lng": float(r.lng),
            "win": [nz(r.win_start, 0), nz(r.win_end, 9999)],
            "dwell": nz(r.dwell, 0),
            "demand": nz(r.demand, 0),
        }
        for r in df.rename(columns={"name": "name_"}).itertuples()
    ]

URBAN_PRESETS = {
    "疫苗配送 · 上海": dict(
        product="vaccine", ambient=25, nveh=2, veh="4.2m", cap=1500, stops=tools.DEMO_STOPS
    ),
    "生鲜日配 · 广州": dict(
        product="fresh", ambient=30, nveh=1, veh="4.2m", cap=1500,
        stops=[
            {"name": "中心仓", "lat": 23.13, "lng": 113.26, "win": [0, 9999], "dwell": 0, "demand": 0},
            {"name": "天河超市", "lat": 23.14, "lng": 113.36, "win": [20, 100], "dwell": 15, "demand": 400},
            {"name": "越秀菜场", "lat": 23.12, "lng": 113.24, "win": [10, 70], "dwell": 15, "demand": 300},
            {"name": "番禺门店", "lat": 22.94, "lng": 113.35, "win": [60, 160], "dwell": 15, "demand": 350},
            {"name": "白云餐厅", "lat": 23.25, "lng": 113.28, "win": [40, 140], "dwell": 10, "demand": 250},
        ],
    ),
    "冷冻肉配送 · 北京": dict(
        product="frozen", ambient=15, nveh=1, veh="6.8m", cap=6000,
        stops=[
            {"name": "冷库", "lat": 39.90, "lng": 116.40, "win": [0, 9999], "dwell": 0, "demand": 0},
            {"name": "朝阳批发", "lat": 39.92, "lng": 116.50, "win": [20, 120], "dwell": 25, "demand": 900},
            {"name": "海淀超市", "lat": 39.99, "lng": 116.30, "win": [30, 150], "dwell": 20, "demand": 700},
            {"name": "丰台门店", "lat": 39.85, "lng": 116.28, "win": [60, 200], "dwell": 20, "demand": 600},
        ],
    ),
}

TRUNK_PRESETS = {
    "武汉 → 长沙": dict(
        product="vaccine", ambient=28, nveh=1, veh="9.6m", cap=12000,
        stops=[
            {"name": "武汉冷库", "address": "武汉市东西湖区", "lat": 30.6190, "lng": 114.1370, "win": [0, 9999], "dwell": 0, "demand": 0},
            {"name": "长沙配送中心", "address": "长沙市岳麓区", "lat": 28.2340, "lng": 112.9310, "win": [180, 480], "dwell": 40, "demand": 8000},
        ],
    ),
    "上海 → 杭州": dict(
        product="dairy", ambient=26, nveh=1, veh="6.8m", cap=6000,
        stops=[
            {"name": "上海中心仓", "address": "上海市嘉定区", "lat": 31.3750, "lng": 121.2500, "win": [0, 9999], "dwell": 0, "demand": 0},
            {"name": "杭州前置仓", "address": "杭州市余杭区", "lat": 30.2740, "lng": 120.1550, "win": [120, 360], "dwell": 30, "demand": 4500},
        ],
    ),
    "北京 → 天津": dict(
        product="frozen", ambient=12, nveh=1, veh="6.8m", cap=6000,
        stops=[
            {"name": "北京冷库", "address": "北京市大兴区", "lat": 39.7260, "lng": 116.3410, "win": [0, 9999], "dwell": 0, "demand": 0},
            {"name": "天津中转站", "address": "天津市西青区", "lat": 39.1410, "lng": 117.1100, "win": [90, 300], "dwell": 35, "demand": 5000},
        ],
    ),
}

def load_preset(name, mode="urban"):
    src = URBAN_PRESETS if mode == "urban" else TRUNK_PRESETS
    p = src[name]
    st.session_state.update(
        product=p["product"],
        ambient=p["ambient"],
        nveh=p["nveh"],
        veh=p["veh"],
        cap=p["cap"],
        stops_df=to_df(p["stops"]),
        ver=st.session_state.get("ver", 0) + 1,
        route_res=None,
        route_mode=mode,
    )

if "stops_df" not in st.session_state:
    load_preset("疫苗配送 · 上海", "urban")
    st.session_state.update(
        speed=30,
        val=50000,
        hist=None,
        msgs=[],
        log=None,
        wmsg="",
        c_fuel=COST["fuel_price"],
        c_driver=COST["driver_per_h"],
        c_late=COST["late_per_min"],
        route_mode="urban",
        use_amap=True,
    )

def fetch_weather(city, key):
    try:
        g = amap.geocode(city, key)
        w = amap.weather(g["adcode"], key)
        st.session_state.ambient = int(max(-20, min(45, round(w["temp"]))))
        st.session_state.wmsg = f"{w['city']} {w['weather']} {w['temp']:.0f}℃"
    except amap.AmapError as e:
        st.session_state.wmsg = f"天气获取失败：{e}"

def band(fig, p):
    fig.add_hrect(
        y0=p["lo"], y1=p["hi"],
        fillcolor="rgba(201, 162, 39, 0.12)",
        line_width=0,
        annotation_text="合规温区",
        annotation_position="top left",
    )

with st.sidebar:
    st.markdown("### 🧊 冷链优化智能体")
    st.caption("路线 · 温度 · 库存 · 补货")

    st.markdown("---")
    st.markdown("**场景**")
    mode = st.radio(
        "运输类型",
        ["城市配送", "干线运输"],
        horizontal=True,
        key="sidebar_mode",
        label_visibility="collapsed",
    )
    route_mode = "urban" if mode == "城市配送" else "trunk"
    presets = URBAN_PRESETS if route_mode == "urban" else TRUNK_PRESETS
    preset_name = st.selectbox("预设方案", list(presets.keys()), key="preset")
    if st.button("载入场景", use_container_width=True):
        load_preset(preset_name, route_mode)
        st.rerun()

    st.markdown("---")
    try:
        api_key = st.secrets.get("ZHIPU_API_KEY", "")
    except Exception:
        api_key = ""
    try:
        amap_key = st.secrets.get("AMAP_KEY", DEFAULT_AMAP_KEY) or DEFAULT_AMAP_KEY
    except Exception:
        amap_key = DEFAULT_AMAP_KEY

    model = st.text_input("模型", value="glm-5.3-flash")
    city = st.text_input("城市", value="上海")
    use_amap = st.checkbox("使用高德真实路况", value=True)

    st.markdown("---")
    st.caption("计算在本地完成。智能体对话会调用大模型。")

T_ROUTE, T_TEMP, T_INV, T_FC, T_MODE, T_AGENT, T_PARAM = st.tabs(
    ["路线优化", "温度监控", "库存效期", "需求补货", "运输方式", "智能体", "参数说明"]
)

product = st.session_state.product
p = PRODUCTS[product]

with T_ROUTE:
    current_mode = st.session_state.get("route_mode", "urban")
    mode_label = "城市配送" if current_mode == "urban" else "干线运输"
    st.markdown(f"**当前模式：{mode_label}**")

    a, b = st.columns([1, 2], gap="large")
    with a:
        st.selectbox("货品", PK, format_func=fmt, key="product")
        st.selectbox(
            "车型",
            list(VEHICLES),
            format_func=lambda k: VEHICLES[k]["name"],
            key="veh",
            on_change=lambda: st.session_state.update(cap=VEHICLES[st.session_state.veh]["payload"]),
        )
        st.number_input("单车载重 kg", 100, 30000, step=100, key="cap")
        st.number_input("车辆数", 1, 6, key="nveh")
        st.slider("环境温度 ℃", -20, 45, key="ambient")
        if st.button("获取当前气温", use_container_width=True, disabled=not amap_key):
            fetch_weather(city, amap_key)
            st.rerun()
        if st.session_state.wmsg:
            st.caption(st.session_state.wmsg)
        st.number_input("货值 元", 1000, 5000000, step=5000, key="val")
        st.slider("估算车速 km/h", 15, 80, key="speed")
        with st.expander("成本参数"):
            st.number_input("柴油 元/升", 5.0, 15.0, step=0.1, key="c_fuel")
            st.number_input("司机 元/小时", 10.0, 100.0, step=1.0, key="c_driver")
            st.number_input("迟到罚金 元/分钟", 0.0, 50.0, step=0.5, key="c_late")

    with b:
        if current_mode == "urban":
            st.markdown("**配送点** · 第 1 行为仓库，时间窗为发车后分钟数")
        else:
            st.markdown("**起终点** · 第 1 行为发货冷库，其余为中转或收货点")

        edited = st.data_editor(
            st.session_state.stops_df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"ed{st.session_state.ver}",
            column_config={
                "name": "名称",
                "address": "地址",
                "lat": st.column_config.NumberColumn("纬度", format="%.5f"),
                "lng": st.column_config.NumberColumn("经度", format="%.5f"),
                "win_start": "最早到",
                "win_end": "最晚到",
                "dwell": "停留",
                "demand": "货量 kg",
            },
        )
        g1, g2 = st.columns(2)
        if g1.button("地址解析坐标", use_container_width=True):
            if not amap_key:
                st.error("高德 Key 不可用")
            else:
                try:
                    df, n = edited.copy(), 0
                    for i, r in df.iterrows():
                        if str(r.get("address") or "").strip() and (pd.isna(r.lat) or pd.isna(r.lng)):
                            g = amap.geocode(str(r.address), amap_key, city)
                            df.loc[i, ["lat", "lng"]] = [g["lat"], g["lng"]]
                            n += 1
                    st.session_state.stops_df = df
                    st.session_state.ver += 1
                    st.session_state.wmsg = f"已解析 {n} 个地址"
                    st.rerun()
                except amap.AmapError as e:
                    st.error(str(e))
        if g2.button("开始优化", type="primary", use_container_width=True):
            try:
                stops = to_stops(edited)
                st.session_state.route_stops = stops
                st.session_state.route_res = tools.optimize_delivery_route(
                    st.session_state.product,
                    stops,
                    st.session_state.nveh,
                    st.session_state.veh,
                    st.session_state.cap,
                    st.session_state.ambient,
                    st.session_state.speed,
                    st.session_state.val,
                    include_trace=True,
                    costs={
                        "fuel_price": st.session_state.c_fuel,
                        "driver_per_h": st.session_state.c_driver,
                        "late_per_min": st.session_state.c_late,
                    },
                    use_amap=use_amap,
                    _amap_key=amap_key or None,
                )
            except ValueError as e:
                st.error(str(e))
                st.session_state.route_res = None

    res = st.session_state.get("route_res")
    stops = st.session_state.get("route_stops")
    if res and "error" in res:
        st.error(res["error"])
    elif res:
        st.caption(f"{res['vehicle_type']} · {res['road_source']}")
        for w in res["warnings"]:
            st.warning(w)
        for v in res["vehicles"]:
            for w in v["warnings"]:
                st.warning(f"车 {v['vehicle']}：{w}")

        m = st.columns(4)
        m[0].metric("总成本", f"¥{res['total_cost_yuan']:,.0f}", f"{-res['saving_yuan']:+,.0f} vs 原顺序", delta_color="inverse")
        m[1].metric("总里程", f"{res['total_km']} km")
        m[2].metric("超温分钟", sum(v["min_out_of_range"] for v in res["vehicles"]))
        m[3].metric("迟到分钟", sum(v["late_min"] for v in res["vehicles"]))

        pos = {s["name"]: (s["lat"], s["lng"]) for s in stops}
        c1, c2 = st.columns(2)
        fm = go.Figure()
        for v in res["vehicles"]:
            names = [stops[0]["name"], *v["path"]]
            fm.add_trace(
                go.Scatter(
                    x=[pos[n][1] for n in names],
                    y=[pos[n][0] for n in names],
                    mode="lines+markers+text",
                    name=f"车{v['vehicle']} {v['load_kg']:.0f}kg",
                    text=["仓"] + [str(i + 1) for i in range(len(v["path"]))],
                    textposition="top center",
                    hovertext=names,
                    line=dict(color=COLORS[(v["vehicle"] - 1) % 6], width=2.5),
                    marker=dict(size=8),
                )
            )
        fm.update_layout(
            title="配送路线",
            xaxis_title="经度",
            yaxis_title="纬度",
            yaxis_scaleanchor="x",
            height=380,
            margin=dict(t=40, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e8d5a3"),
        )
        c1.plotly_chart(fm, use_container_width=True)

        ft = go.Figure()
        for v in res["vehicles"]:
            tr = pd.DataFrame(v["trace"], columns=["t", "temp"])
            ft.add_trace(
                go.Scatter(
                    x=tr.t, y=tr.temp,
                    name=f"车{v['vehicle']}",
                    line=dict(color=COLORS[(v["vehicle"] - 1) % 6], width=2),
                )
            )
        band(ft, PRODUCTS[st.session_state.product])
        ft.update_layout(
            title="车厢温度曲线",
            xaxis_title="发车后分钟",
            yaxis_title="℃",
            height=380,
            margin=dict(t=40, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e8d5a3"),
        )
        c2.plotly_chart(ft, use_container_width=True)

        fb = go.Figure(
            go.Bar(
                x=["原始顺序", "优化后"],
                y=[res["baseline_cost_yuan"], res["total_cost_yuan"]],
                marker_color=["#3d3420", "#c9a227"],
                text=[f"¥{res['baseline_cost_yuan']:,.0f}", f"¥{res['total_cost_yuan']:,.0f}"],
                textposition="outside",
            )
        )
        fb.update_layout(
            title="成本对比",
            height=260,
            margin=dict(t=40, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e8d5a3"),
        )
        c1.plotly_chart(fb, use_container_width=True)

        bd = res["cost_breakdown"]
        fc = go.Figure(
            go.Bar(
                x=list(bd.values()),
                y=list(bd.keys()),
                orientation="h",
                text=[f"¥{v:,.0f}" for v in bd.values()],
                marker_color="#c9a227",
            )
        )
        fc.update_layout(
            title="成本构成",
            height=260,
            margin=dict(t=40, b=10),
            yaxis_autorange="reversed",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e8d5a3"),
        )
        c2.plotly_chart(fc, use_container_width=True)

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "车": v["vehicle"],
                        "路线": " → ".join(v["path"]),
                        "里程 km": v["km"],
                        "用时 h": v["hours"],
                        "超温分钟": v["min_out_of_range"],
                        "峰值 ℃": v["peak_temp_c"],
                        "过路费": v["toll_yuan"],
                        "损耗天数": v["lost_shelf_days"],
                        "成本": v["cost_yuan"],
                    }
                    for v in res["vehicles"]
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

with T_TEMP:
    src = st.radio(
        "数据来源",
        ["模拟 · 正常", "模拟 · 开门过久", "模拟 · 制冷故障", "上传 CSV"],
        horizontal=True,
    )
    if src == "上传 CSV":
        up = st.file_uploader("CSV 需包含 t_min, temp 列，可选 door_open", type="csv")
        log = None
        if up:
            d = pd.read_csv(up)
            d["door_open"] = d["door_open"].fillna(False).astype(bool) if "door_open" in d else False
            log = d.to_dict("records")
    else:
        scenario_map = {
            "模拟 · 正常": "normal",
            "模拟 · 开门过久": "door_open",
            "模拟 · 制冷故障": "compressor_fault",
        }
        log = tools.simulate_temperature_log(product, 240, scenario_map[src])

    if log:
        tmax = int(max(r["t_min"] for r in log))
        now = st.slider("回放到第 N 分钟", 0, tmax, min(100, tmax), step=2)
        cur = [r for r in log if r["t_min"] <= now]
        al = tools.temperature_alerts(product, cur) if cur else None
        df = pd.DataFrame(log)
        f = go.Figure()
        f.add_trace(go.Scatter(x=df.t_min, y=df.temp, name="全程", line=dict(color="#3d3420")))
        d2 = df[df.t_min <= now]
        f.add_trace(go.Scatter(x=d2.t_min, y=d2.temp, name="已发生", line=dict(color="#c9a227", width=2.5)))
        band(f, p)
        f.update_layout(
            height=360,
            xaxis_title="分钟",
            yaxis_title="℃",
            margin=dict(t=20, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e8d5a3"),
        )
        l, r = st.columns([2, 1])
        l.plotly_chart(f, use_container_width=True)
        if al:
            status_fn = {"正常": r.success, "预警": r.warning, "报警": r.error}[al["status"]]
            status_fn(f"状态：{al['status']} · 当前 {al['latest_temp']}℃")
            for x in al["alerts"]:
                r.markdown(f"**{x['message']}**  \n{x['action']}")
            if len(cur) >= 2:
                s = tools.assess_temperature_log(product, cur)
                r.caption(
                    f"累计超温 {s['minutes_out_of_range']:.0f} 分钟 · 估算损耗 {s['lost_shelf_pct']}% · {s['verdict']}"
                )

with T_INV:
    st.markdown("**先到期先出**")
    c1, c2 = st.columns(2)
    inv = c1.data_editor(
        pd.DataFrame(
            [
                ["牛奶", "B01", 200, 3, "A区"],
                ["牛奶", "B02", 300, 9, "A区"],
                ["牛奶", "B03", 400, 18, "B区"],
                ["酸奶", "Y01", 150, 5, "A区"],
                ["酸奶", "Y02", 250, 12, "B区"],
                ["牛奶", "B00", 30, 0, "C区"],
            ],
            columns=["sku", "batch", "qty", "days_left", "location"],
        ),
        num_rows="dynamic",
        key="inv",
        use_container_width=True,
    )
    od = c2.data_editor(
        pd.DataFrame(
            [["牛奶", 350, 7], ["酸奶", 300, 0], ["牛奶", 300, 0]],
            columns=["sku", "qty", "min_days_left"],
        ),
        num_rows="dynamic",
        key="od",
        use_container_width=True,
    )
    nd = st.slider("临期阈值 天", 1, 30, 7)
    inv = inv.dropna(subset=["sku", "batch"])
    od = od.dropna(subset=["sku", "qty"])
    r = tools.fefo_inventory(inv.to_dict("records"), od.fillna(0).to_dict("records"), nd)

    left = inv.copy()
    left["label"] = left["sku"].astype(str) + "-" + left["batch"].astype(str)
    fig = go.Figure(
        go.Bar(
            x=left.label,
            y=left.days_left,
            marker_color=["#f85149" if d <= 0 else "#d29922" if d <= nd else "#3fb950" for d in left.days_left],
        )
    )
    fig.update_layout(
        title="各批次剩余效期",
        height=300,
        yaxis_title="天",
        margin=dict(t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e8d5a3"),
    )
    st.plotly_chart(fig, use_container_width=True)

    k = st.columns(3)
    k[0].metric("缺货订单", len(r["shortages"]))
    k[1].metric("临期未售", len(r["near_expiry_remaining"]))
    k[2].metric("过期批次", len(r["expired"]))

    st.dataframe(pd.DataFrame(r["allocations"]), use_container_width=True, hide_index=True)
    for s in r["shortages"]:
        st.warning(f"{s['sku']} 缺货 {s['short_qty']:.0f}")
    for x in r["near_expiry_remaining"]:
        st.info(f"{x['sku']}-{x['batch']} 剩 {x['days_left']} 天、{x['qty']:.0f} 件 → {x['advice']}")
    for x in r["expired"]:
        st.error(f"{x['sku']}-{x['batch']} 已过期 {x['qty']:.0f} 件")

with T_FC:
    c1, c2 = st.columns([1, 2])
    h = c1.text_area("近期每日需求", "120,135,128,140,152,149,160,158,171,165,180,176,190,185")
    stock = c1.number_input("当前库存", 0, 1000000, 300)
    lead = c1.slider("补货提前期 天", 1, 14, 2)
    sl = c1.select_slider("服务水平", [0.90, 0.95, 0.99], 0.95, format_func=lambda x: f"{x:.0%}")
    shelf = c1.slider("货架期 天", 1, 365, 7)
    try:
        hist = [float(x) for x in h.replace("，", ",").split(",") if x.strip()]
        f = tools.forecast_replenishment(
            hist, stock, lead, {0.90: 1.28, 0.95: 1.65, 0.99: 2.33}[sl], shelf
        )
    except ValueError:
        f = {"error": "请输入有效数字"}
    if "error" in f:
        c2.error(f["error"])
    else:
        n = len(hist)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(range(1, n + 1)), y=hist, name="历史需求", line=dict(color="#c9a227")))
        fig.add_trace(
            go.Scatter(
                x=list(range(n + 1, n + 1 + len(f["forecast"]))),
                y=f["forecast"],
                name="预测",
                line=dict(dash="dash", color="#f0d78c"),
            )
        )
        fig.update_layout(
            height=320,
            xaxis_title="天",
            margin=dict(t=20, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e8d5a3"),
        )
        c2.plotly_chart(fig, use_container_width=True)
        m = c2.columns(4)
        m[0].metric("建议订货", f"{f['suggested_order_qty']}")
        m[1].metric("再订货点", f["reorder_point"])
        m[2].metric("安全库存", f["safety_stock"])
        m[3].metric("可售天数", f["stock_cover_days"])
        if f["need_reorder_now"]:
            c2.error("库存已低于再订货点，建议立即补货")
        else:
            c2.success("库存充足")
        if f["capped_by_shelf_life"]:
            c2.info("订货量已按货架期上限截断")

with T_MODE:
    c1, c2 = st.columns([1, 2])
    dist = c1.slider("距离 km", 50, 5000, 1200)
    wt = c1.number_input("重量 kg", 10, 100000, 500)
    r = tools.compare_transport_modes(
        product, dist, wt, st.session_state.val, st.session_state.ambient
    )["ranked_by_total_cost"]
    df = pd.DataFrame(r)
    fig = go.Figure(
        [
            go.Bar(x=df["mode"], y=df.freight_yuan, name="运费", marker_color="#c9a227"),
            go.Bar(
                x=df["mode"],
                y=df.total_cost_yuan - df.freight_yuan,
                name="品质损耗折价",
                marker_color="#8b7355",
            ),
        ]
    )
    fig.update_layout(
        barmode="stack",
        title="总成本构成",
        height=320,
        margin=dict(t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e8d5a3"),
    )
    c2.plotly_chart(fig, use_container_width=True)
    c2.dataframe(
        df.rename(
            columns={
                "mode": "方式",
                "hours": "时效 h",
                "freight_yuan": "运费",
                "lost_shelf_days": "损耗天数",
                "total_cost_yuan": "总成本",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )
    c2.success(f"总成本最低：{r[0]['mode']} · 最快：{min(r, key=lambda x: x['hours'])['mode']}")

with T_AGENT:
    import agent

    st.caption("用自然语言调用路线、温度、库存、补货等能力")
    ctx = st.checkbox("附带当前路线方案")
    for m in st.session_state.msgs:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            for t in m.get("tools", []):
                st.caption(f"调用 {t}")
    q = st.chat_input("例如：车辆减到 1 辆会怎样？疫苗在途超温如何处置？")
    if q:
        if not api_key:
            st.error("请在 secrets 中配置 ZHIPU_API_KEY")
        else:
            if st.session_state.hist is None:
                st.session_state.hist = [{"role": "system", "content": agent.SYSTEM}]
            full = q
            if ctx and st.session_state.get("route_res"):
                full += "\n\n【当前页面方案】" + json.dumps(
                    {
                        "product": product,
                        "ambient_c": st.session_state.ambient,
                        "stops": st.session_state.route_stops,
                        "n_vehicles": st.session_state.nveh,
                        "vehicle": st.session_state.veh,
                        "capacity_kg": st.session_state.cap,
                        "result": [
                            {
                                k: v[k]
                                for k in (
                                    "vehicle",
                                    "path",
                                    "km",
                                    "hours",
                                    "late_min",
                                    "min_out_of_range",
                                    "cost_yuan",
                                )
                            }
                            for v in st.session_state.route_res["vehicles"]
                        ],
                    },
                    ensure_ascii=False,
                )
            st.session_state.msgs.append({"role": "user", "content": q})
            with st.chat_message("user"):
                st.markdown(q)
            used = []
            with st.chat_message("assistant"), st.spinner("处理中…"):
                try:
                    st.session_state.hist.append({"role": "user", "content": full})
                    ans = agent.chat(
                        st.session_state.hist,
                        agent.make_client(api_key),
                        model,
                        secrets={"amap_key": amap_key},
                        on_tool=lambda n, a, r_: used.append(
                            f"{n}({json.dumps(a, ensure_ascii=False)[:60]}…)"
                        ),
                    )
                except Exception as e:
                    ans = f"调用失败：{e}"
                    st.session_state.hist.pop()
                st.markdown(ans)
                for t in used:
                    st.caption(f"调用 {t}")
            st.session_state.msgs.append({"role": "assistant", "content": ans, "tools": used})

with T_PARAM:
    st.markdown("**依据等级**")
    st.markdown(
        "`[标准]` 国标/行标/团标　`[政策]` 官方数据　`[行业]` 行业惯例　`[估算]` 需用实际数据校准"
    )
    st.subheader("货品温区")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "货品": v["name"],
                    "允许温区 ℃": f"{v['lo']}~{v['hi']}",
                    "机组设定 ℃": v["set"],
                    "基准保质期 天": v["shelf"],
                    "Q10": v["q10"],
                    "依据": v["basis"],
                }
                for v in PRODUCTS.values()
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
    st.subheader("冷藏车型")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "车型": v["name"],
                    "载重 kg": v["payload"],
                    "行驶油耗 L/100km": v["drive_l100"],
                    "冷机 L/小时": v["reefer_lph"],
                    "车价": v["price"],
                    "依据": v["basis"],
                }
                for v in VEHICLES.values()
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
    st.subheader("成本参数")
    st.dataframe(
        pd.DataFrame(
            [{"参数": k, "默认值": COST[k], "说明": COST_NOTES[k]} for k in COST]
        ),
        hide_index=True,
        use_container_width=True,
    )
    st.info(
        "连续驾驶超 4 小时须停车休息 ≥20 分钟。《道路交通安全法实施条例》第 62 条。"
        "同城配送建议 4~6 小时内完成。高德距离为小客车口径，已按车型系数调整。"
    )
