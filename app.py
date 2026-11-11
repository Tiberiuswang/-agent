"""冷链优化智能体 · 可视化网站（Streamlit）。运行：streamlit run app.py"""
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import tools
from tools import PRODUCTS

st.set_page_config(page_title="冷链优化智能体", page_icon="🧊", layout="wide")
PK = list(PRODUCTS)
fmt = lambda k: f"{PRODUCTS[k]['name']}  {PRODUCTS[k]['lo']}~{PRODUCTS[k]['hi']}℃"
COLS = ["name", "lat", "lng", "win_start", "win_end", "dwell", "demand"]
COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b"]

def to_df(stops):
    return pd.DataFrame([[s["name"], s["lat"], s["lng"], s["win"][0], s["win"][1], s["dwell"], s.get("demand", 0)] for s in stops], columns=COLS)

def to_stops(df):
    nz = lambda v, d: d if pd.isna(v) else float(v)  # 新增行的空单元格给默认值
    df = df.dropna(subset=["name", "lat", "lng"])
    return [{"name": str(r.name_), "lat": float(r.lat), "lng": float(r.lng), "win": [nz(r.win_start, 0), nz(r.win_end, 9999)],
             "dwell": nz(r.dwell, 0), "demand": nz(r.demand, 0)} for r in df.rename(columns={"name": "name_"}).itertuples()]

PRESETS = {
    "💉 疫苗配送 · 上海": dict(product="vaccine", ambient=30, nveh=2, cap=1200, stops=tools.DEMO_STOPS),
    "🐟 生鲜日配 · 广州": dict(product="fresh", ambient=34, nveh=1, cap=2000, stops=[
        {"name": "中心仓", "lat": 23.13, "lng": 113.26, "win": [0, 9999], "dwell": 0, "demand": 0},
        {"name": "天河超市", "lat": 23.14, "lng": 113.36, "win": [20, 100], "dwell": 15, "demand": 400},
        {"name": "越秀菜场", "lat": 23.12, "lng": 113.24, "win": [10, 70], "dwell": 15, "demand": 300},
        {"name": "番禺门店", "lat": 22.94, "lng": 113.35, "win": [60, 160], "dwell": 15, "demand": 350},
        {"name": "白云餐厅", "lat": 23.25, "lng": 113.28, "win": [40, 140], "dwell": 10, "demand": 250}]),
    "🥩 冷冻肉配送 · 北京": dict(product="frozen", ambient=28, nveh=1, cap=3000, stops=[
        {"name": "冷库", "lat": 39.90, "lng": 116.40, "win": [0, 9999], "dwell": 0, "demand": 0},
        {"name": "朝阳批发", "lat": 39.92, "lng": 116.50, "win": [20, 120], "dwell": 25, "demand": 900},
        {"name": "海淀超市", "lat": 39.99, "lng": 116.30, "win": [30, 150], "dwell": 20, "demand": 700},
        {"name": "丰台门店", "lat": 39.85, "lng": 116.28, "win": [60, 200], "dwell": 20, "demand": 600}]),
}

def load_preset(name):
    p = PRESETS[name]
    st.session_state.update(product=p["product"], ambient=p["ambient"], nveh=p["nveh"], cap=p["cap"],
                            stops_df=to_df(p["stops"]), ver=st.session_state.get("ver", 0) + 1, route_res=None)

if "stops_df" not in st.session_state:
    load_preset("💉 疫苗配送 · 上海")
    st.session_state.update(speed=40, val=50000, hist=None, msgs=[], log=None)

def band(fig, p):  # 温区色带
    fig.add_hrect(y0=p["lo"], y1=p["hi"], fillcolor="green", opacity=0.12, line_width=0, annotation_text="合规温区")

with st.sidebar:
    st.title("🧊 冷链优化智能体")
    st.selectbox("🧩 场景积木（一键载入）", list(PRESETS), key="preset")
    st.button("载入场景", on_click=load_preset, args=(st.session_state.get("preset", list(PRESETS)[0]),), use_container_width=True)
    st.divider()
    try: default_key = st.secrets.get("ZHIPU_API_KEY", "")
    except Exception: default_key = ""
    api_key = st.text_input("智谱 API Key", value=default_key, type="password", help="仅用于「智能体」页，不会被保存")
    model = st.text_input("模型编码", value="glm-5.3-flash", help="以智谱开放平台控制台显示为准")
    st.caption("所有计算工具在本地运行；只有「智能体」页会调用大模型。")

T_ROUTE, T_TEMP, T_INV, T_FC, T_MODE, T_AGENT = st.tabs(["🚚 路线优化", "🌡️ 温度监控", "🧊 库存效期", "📈 需求补货", "✈️ 运输方式", "🤖 智能体"])
product = st.session_state.product
p = PRODUCTS[product]

# ---------------- 路线优化 ----------------
with T_ROUTE:
    a, b = st.columns([1, 2])
    with a:
        st.radio("① 货品", PK, format_func=fmt, key="product")
        st.slider("② 环境温度 ℃", 0, 45, key="ambient")
        st.slider("③ 车速 km/h", 20, 80, key="speed")
        st.number_input("④ 车辆数", 1, 6, key="nveh")
        st.number_input("单车载重 kg", 100, 20000, step=100, key="cap")
        st.number_input("货值 元", 1000, 5000000, step=5000, key="val")
    with b:
        st.markdown("**⑤ 配送点**（第 1 行=仓库起点；点表格底部 ➕ 增行，选中行按 Delete 删除；时间窗为发车后的分钟数）")
        edited = st.data_editor(st.session_state.stops_df, num_rows="dynamic", use_container_width=True, key=f"ed{st.session_state.ver}",
                                column_config={"name": "名称", "lat": st.column_config.NumberColumn("纬度", format="%.4f"),
                                               "lng": st.column_config.NumberColumn("经度", format="%.4f"),
                                               "win_start": "最早到(分)", "win_end": "最晚到(分)", "dwell": "卸货(分)", "demand": "卸货量(kg)"})
        if st.button("🚀 开始优化", type="primary", use_container_width=True):
            stops = to_stops(edited)
            st.session_state.route_stops = stops
            st.session_state.route_res = tools.optimize_delivery_route(
                st.session_state.product, stops, st.session_state.nveh, st.session_state.cap, st.session_state.ambient,
                st.session_state.speed, st.session_state.val, include_trace=True)
    res, stops = st.session_state.get("route_res"), st.session_state.get("route_stops")
    if res and "error" in res: st.error(res["error"])
    elif res:
        m = st.columns(4)
        m[0].metric("优化后总成本", f"¥{res['total_cost_yuan']:,.0f}", f"{-res['saving_yuan']:+,.0f} 元 vs 原顺序", delta_color="inverse")
        m[1].metric("总里程", f"{res['total_km']} km")
        m[2].metric("总超温分钟", sum(v["min_out_of_range"] for v in res["vehicles"]))
        m[3].metric("迟到分钟", sum(v["late_min"] for v in res["vehicles"]))
        pos = {s["name"]: (s["lat"], s["lng"]) for s in stops}
        c1, c2 = st.columns(2)
        fm = go.Figure()
        for v in res["vehicles"]:
            names = [stops[0]["name"], *v["path"]]
            fm.add_trace(go.Scatter(x=[pos[n][1] for n in names], y=[pos[n][0] for n in names], mode="lines+markers+text", name=f"车{v['vehicle']}（{v['load_kg']:.0f}kg）",
                                    text=["仓"] + [str(i + 1) for i in range(len(v["path"]))], textposition="top center", hovertext=names,
                                    line=dict(color=COLORS[(v["vehicle"] - 1) % 6], width=3)))
        fm.update_layout(title="配送路线（数字=顺序）", xaxis_title="经度", yaxis_title="纬度", yaxis_scaleanchor="x", height=380, margin=dict(t=40, b=10))
        c1.plotly_chart(fm, use_container_width=True)
        ft = go.Figure()
        for v in res["vehicles"]:
            tr = pd.DataFrame(v["trace"], columns=["t", "temp"])
            ft.add_trace(go.Scatter(x=tr.t, y=tr.temp, name=f"车{v['vehicle']}", line=dict(color=COLORS[(v["vehicle"] - 1) % 6])))
        band(ft, PRODUCTS[st.session_state.product])
        ft.update_layout(title="车厢温度曲线（开门卸货时升温）", xaxis_title="发车后分钟", yaxis_title="℃", height=380, margin=dict(t=40, b=10))
        c2.plotly_chart(ft, use_container_width=True)
        fb = go.Figure(go.Bar(x=["原始顺序", "优化后"], y=[res["baseline_cost_yuan"], res["total_cost_yuan"]], marker_color=["#999", "#2ca02c"], text=[f"¥{res['baseline_cost_yuan']:,.0f}", f"¥{res['total_cost_yuan']:,.0f}"]))
        fb.update_layout(title="成本对比（运输+制冷+迟到罚金+品质损耗折价）", height=260, margin=dict(t=40, b=10))
        c1.plotly_chart(fb, use_container_width=True)
        c2.dataframe(pd.DataFrame([{"车": v["vehicle"], "路线": " → ".join(v["path"]), "里程km": v["km"], "用时h": v["hours"], "超温分钟": v["min_out_of_range"],
                                     "峰值℃": v["peak_temp_c"], "损耗保质期(天)": v["lost_shelf_days"], "成本¥": v["cost_yuan"]} for v in res["vehicles"]]), use_container_width=True, hide_index=True)

# ---------------- 温度监控 ----------------
with T_TEMP:
    src = st.radio("数据来源", ["模拟：正常", "模拟：开门过久", "模拟：制冷故障", "上传 CSV"], horizontal=True)
    if src == "上传 CSV":
        up = st.file_uploader("CSV 列：t_min, temp, door_open(可选)", type="csv")
        log = None
        if up:
            d = pd.read_csv(up); d["door_open"] = d["door_open"].fillna(False).astype(bool) if "door_open" in d else False
            log = d.to_dict("records")
    else:
        log = tools.simulate_temperature_log(product, 240, {"模拟：正常": "normal", "模拟：开门过久": "door_open", "模拟：制冷故障": "compressor_fault"}[src])
    if log:
        tmax = int(max(r["t_min"] for r in log))
        now = st.slider("⏱ 回放到第 N 分钟（拖动模拟实时监控）", 0, tmax, min(100, tmax), step=2)
        cur = [r for r in log if r["t_min"] <= now]
        al = tools.temperature_alerts(product, cur) if cur else None
        df = pd.DataFrame(log)
        f = go.Figure()
        f.add_trace(go.Scatter(x=df.t_min, y=df.temp, name="全程", line=dict(color="#ccc")))
        d2 = df[df.t_min <= now]
        f.add_trace(go.Scatter(x=d2.t_min, y=d2.temp, name="已发生", line=dict(color="#d62728", width=3)))
        band(f, p); f.update_layout(height=360, xaxis_title="分钟", yaxis_title="℃", margin=dict(t=20, b=10))
        l, r = st.columns([2, 1])
        l.plotly_chart(f, use_container_width=True)
        if al:
            {"正常": r.success, "预警": r.warning, "报警": r.error}[al["status"]](f"状态：{al['status']} · 当前 {al['latest_temp']}℃")
            for x in al["alerts"]: r.markdown(f"**{x['message']}**  \n↳ {x['action']}")
            if len(cur) >= 2:
                s = tools.assess_temperature_log(product, cur)
                r.caption(f"累计超温 {s['minutes_out_of_range']:.0f} 分钟 · 估算损耗保质期 {s['lost_shelf_pct']}% · {s['verdict']}")

# ---------------- 库存效期 ----------------
with T_INV:
    st.markdown("**冷库先到期先出（FEFO）**：左表=在库批次，右表=待出库订单（可增删行）")
    c1, c2 = st.columns(2)
    inv = c1.data_editor(pd.DataFrame([["牛奶", "B01", 200, 3, "A区"], ["牛奶", "B02", 300, 9, "A区"], ["牛奶", "B03", 400, 18, "B区"], ["酸奶", "Y01", 150, 5, "A区"], ["酸奶", "Y02", 250, 12, "B区"], ["牛奶", "B00", 30, 0, "C区"]],
                                      columns=["sku", "batch", "qty", "days_left", "location"]), num_rows="dynamic", key="inv", use_container_width=True)
    od = c2.data_editor(pd.DataFrame([["牛奶", 350, 7], ["酸奶", 300, 0], ["牛奶", 300, 0]], columns=["sku", "qty", "min_days_left"]), num_rows="dynamic", key="od", use_container_width=True)
    nd = st.slider("临期阈值(天)", 1, 30, 7)
    inv, od = inv.dropna(subset=["sku", "batch"]), od.dropna(subset=["sku", "qty"])
    r = tools.fefo_inventory(inv.to_dict("records"), od.fillna(0).to_dict("records"), nd)
    left = inv.copy(); left["label"] = left["sku"].astype(str) + "-" + left["batch"].astype(str)
    fig = go.Figure(go.Bar(x=left.label, y=left.days_left, marker_color=["#d62728" if d <= 0 else "#ff7f0e" if d <= nd else "#2ca02c" for d in left.days_left]))
    fig.update_layout(title="各批次剩余效期（红=过期，橙=临期）", height=300, yaxis_title="天", margin=dict(t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)
    k = st.columns(3)
    k[0].metric("缺货订单", len(r["shortages"])); k[1].metric("临期未售批次", len(r["near_expiry_remaining"])); k[2].metric("过期批次", len(r["expired"]))
    st.dataframe(pd.DataFrame(r["allocations"]), use_container_width=True, hide_index=True)
    for s in r["shortages"]: st.warning(f"{s['sku']} 缺货 {s['short_qty']:.0f}")
    for x in r["near_expiry_remaining"]: st.info(f"{x['sku']}-{x['batch']} 剩 {x['days_left']} 天、{x['qty']:.0f} 件 → {x['advice']}")
    for x in r["expired"]: st.error(f"{x['sku']}-{x['batch']} 已过期 {x['qty']:.0f} 件，需报废处置")

# ---------------- 需求补货 ----------------
with T_FC:
    c1, c2 = st.columns([1, 2])
    h = c1.text_area("近期每日需求（逗号分隔，≥7天）", "120,135,128,140,152,149,160,158,171,165,180,176,190,185")
    stock = c1.number_input("当前库存", 0, 1000000, 300)
    lead = c1.slider("补货提前期(天)", 1, 14, 2)
    sl = c1.select_slider("服务水平", [0.90, 0.95, 0.99], 0.95, format_func=lambda x: f"{x:.0%}")
    shelf = c1.slider("货架期(天)", 1, 365, 7)
    try:
        hist = [float(x) for x in h.replace("，", ",").split(",") if x.strip()]
        f = tools.forecast_replenishment(hist, stock, lead, {0.90: 1.28, 0.95: 1.65, 0.99: 2.33}[sl], shelf)
    except ValueError: f = {"error": "请输入数字"}
    if "error" in f: c2.error(f["error"])
    else:
        n = len(hist); fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(range(1, n + 1)), y=hist, name="历史需求"))
        fig.add_trace(go.Scatter(x=list(range(n + 1, n + 1 + len(f["forecast"]))), y=f["forecast"], name="预测", line=dict(dash="dash")))
        fig.update_layout(height=320, xaxis_title="天", margin=dict(t=20, b=10)); c2.plotly_chart(fig, use_container_width=True)
        m = c2.columns(4)
        m[0].metric("建议订货", f"{f['suggested_order_qty']}"); m[1].metric("再订货点", f["reorder_point"])
        m[2].metric("安全库存", f["safety_stock"]); m[3].metric("库存可售天数", f["stock_cover_days"])
        (c2.error if f["need_reorder_now"] else c2.success)("库存已低于再订货点，建议立即补货" if f["need_reorder_now"] else "库存充足")
        if f["capped_by_shelf_life"]: c2.info("订货量已按货架期上限截断，避免囤货过期")

# ---------------- 运输方式 ----------------
with T_MODE:
    c1, c2 = st.columns([1, 2])
    dist = c1.slider("距离 km", 50, 5000, 1200); wt = c1.number_input("重量 kg", 10, 100000, 500)
    r = tools.compare_transport_modes(product, dist, wt, st.session_state.val, st.session_state.ambient)["ranked_by_total_cost"]
    df = pd.DataFrame(r)
    fig = go.Figure([go.Bar(x=df["mode"], y=df.freight_yuan, name="运费"), go.Bar(x=df["mode"], y=df.total_cost_yuan - df.freight_yuan, name="品质损耗折价")])
    fig.update_layout(barmode="stack", title="总成本构成（¥）", height=320, margin=dict(t=40, b=10))
    c2.plotly_chart(fig, use_container_width=True)
    c2.dataframe(df.rename(columns={"mode": "方式", "hours": "时效h", "freight_yuan": "运费¥", "lost_shelf_days": "损耗(天)", "total_cost_yuan": "总成本¥"}), hide_index=True, use_container_width=True)
    c2.success(f"总成本最低：{r[0]['mode']}；最快：{min(r, key=lambda x: x['hours'])['mode']}")

# ---------------- 智能体 ----------------
with T_AGENT:
    import agent
    st.caption("用自然语言调用以上所有工具。可勾选把当前页面的路线方案一并告诉它。")
    ctx = st.checkbox("附带当前路线方案")
    for m in st.session_state.msgs:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            for t in m.get("tools", []): st.caption(f"🔧 {t}")
    q = st.chat_input("例如：把这个方案的车辆减到1辆会怎样？疫苗在途超温怎么处置？")
    if q:
        if not api_key: st.error("请先在左侧填入智谱 API Key")
        else:
            if st.session_state.hist is None: st.session_state.hist = [{"role": "system", "content": agent.SYSTEM}]
            full = q
            if ctx and st.session_state.get("route_res"):
                full += "\n\n【当前页面方案】" + json.dumps({"product": product, "ambient_c": st.session_state.ambient, "stops": st.session_state.route_stops,
                        "n_vehicles": st.session_state.nveh, "capacity_kg": st.session_state.cap, "result": [{k: v[k] for k in ("vehicle", "path", "km", "hours", "late_min", "min_out_of_range", "cost_yuan")} for v in st.session_state.route_res["vehicles"]]}, ensure_ascii=False)
            st.session_state.msgs.append({"role": "user", "content": q})
            with st.chat_message("user"): st.markdown(q)
            used = []
            with st.chat_message("assistant"), st.spinner("思考中…"):
                try:
                    st.session_state.hist.append({"role": "user", "content": full})
                    ans = agent.chat(st.session_state.hist, agent.make_client(api_key), model, on_tool=lambda n, a, r_: used.append(f"{n}({json.dumps(a, ensure_ascii=False)[:60]}…)"))
                except Exception as e:
                    ans = f"调用失败：{e}"; st.session_state.hist.pop()
                st.markdown(ans)
                for t in used: st.caption(f"🔧 {t}")
            st.session_state.msgs.append({"role": "assistant", "content": ans, "tools": used})
