"""冷链运输优化工具集：纯 Python、无第三方依赖，可单独测试，也供智能体与网页共用。"""
import itertools, math, random, statistics

# 货品档案：温区、设定温度、基准保质期(天)、Q10(温度每升10℃，变质速率放大倍数)——示意值，请按实际替换
PRODUCTS = {
    "vaccine":  {"name": "疫苗",     "lo": 2,   "hi": 8,   "set": 5,   "shelf": 365, "q10": 3.0},
    "fresh":    {"name": "生鲜水产", "lo": 0,   "hi": 4,   "set": 2,   "shelf": 7,   "q10": 2.5},
    "frozen":   {"name": "冷冻肉类", "lo": -25, "hi": -15, "set": -18, "shelf": 180, "q10": 2.2},
    "icecream": {"name": "冰淇淋",   "lo": -30, "hi": -22, "set": -25, "shelf": 365, "q10": 2.0},
}
DEMO_STOPS = [  # win=时间窗(相对发车的分钟)，dwell=卸货停留分钟，demand=卸货量kg
    {"name": "仓库", "lat": 31.23, "lng": 121.47, "win": [0, 9999], "dwell": 0, "demand": 0},
    {"name": "浦东医院", "lat": 31.22, "lng": 121.54, "win": [30, 120], "dwell": 15, "demand": 300},
    {"name": "徐汇超市", "lat": 31.19, "lng": 121.44, "win": [20, 90], "dwell": 20, "demand": 500},
    {"name": "闵行门店", "lat": 31.11, "lng": 121.38, "win": [60, 180], "dwell": 15, "demand": 400},
    {"name": "宝山配送站", "lat": 31.40, "lng": 121.49, "win": [90, 240], "dwell": 20, "demand": 600},
    {"name": "嘉定餐厅", "lat": 31.38, "lng": 121.26, "win": [120, 260], "dwell": 15, "demand": 350},
]

def _prod(key):
    return PRODUCTS.get(key)

def _bad(): return {"error": f"未知货品，可选：{list(PRODUCTS)}"}

def _km(a, b):
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dl = math.radians(b["lng"] - a["lng"])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h)) * 1.3  # 1.3=路网曲折系数

def _loss_rate(temp, p):  # 每分钟消耗的"等效保质期(天)"
    return p["q10"] ** ((temp - p["set"]) / 10) / 1440

def _simulate(order, stops, p, ambient, speed, value, trace_on=False):
    """逐分钟模拟：行驶/等待时制冷机拉回设定温度，开门作业时向环境温度升温。"""
    S = {"t": 0, "temp": p["set"], "extra": 0.0, "out": 0, "peak": p["set"]}
    trace = [[0, p["set"]]]
    def tick(target, k):
        S["temp"] += (target - S["temp"]) * k; S["t"] += 1
        S["extra"] += _loss_rate(S["temp"], p) - 1 / 1440
        S["out"] += S["temp"] > p["hi"] or S["temp"] < p["lo"]
        S["peak"] = max(S["peak"], S["temp"])
        if trace_on: trace.append([S["t"], round(S["temp"], 2)])
    km = late = 0.0; arr = []; cur = stops[order[0]]
    for idx in order[1:]:
        s = stops[idx]; d = _km(cur, s); km += d
        for _ in range(round(d / speed * 60)): tick(p["set"], 0.05)
        arr.append([s["name"], S["t"]]); late += max(0, S["t"] - s["win"][1])
        for _ in range(max(0, int(s["win"][0] - S["t"]))): tick(p["set"], 0.05)
        for _ in range(int(s["dwell"])): tick(ambient, 0.012)
        cur = s
    hours = S["t"] / 60; extra = max(S["extra"], 0)
    cost = km * 4.5 + hours * 8 + late * 2 + extra / p["shelf"] * value
    r = {"km": round(km, 1), "hours": round(hours, 2), "late_min": round(late), "min_out_of_range": S["out"],
         "peak_temp_c": round(S["peak"], 1), "lost_shelf_days": round(extra, 4),
         "cost_yuan": round(cost, 1), "arrivals_min": arr}
    if trace_on: r["trace"] = trace
    return r

def _best_order(stops, p, amb, spd, val):
    idx = list(range(1, len(stops)))
    cost = lambda o: _simulate([0, *o], stops, p, amb, spd, val)["cost_yuan"]
    if len(idx) <= 6: return list(min(itertools.permutations(idx), key=cost))  # 穷举
    order, left, cur = [], idx[:], 0  # 最近邻 + 两两交换改进
    while left:
        nx = min(left, key=lambda j: _km(stops[cur], stops[j])); order.append(nx); left.remove(nx); cur = nx
    best = cost(order)
    for _ in range(2):
        for i, j in itertools.combinations(range(len(order)), 2):
            o = order[:]; o[i], o[j] = o[j], o[i]; c = cost(o)
            if c < best - 1e-6: order, best = o, c
    return order

def _groups(cust, depot, n, cap):
    """按仓库极角扫描分组，受载重限制。"""
    cust = sorted(cust, key=lambda s: math.atan2(s["lat"] - depot["lat"], s["lng"] - depot["lng"]))
    total = sum(s.get("demand", 0) for s in cust)
    for limit in (min(cap, max(total / n * 1.2, max([s.get("demand", 0) for s in cust] + [0]))), cap):
        gs, load = [[]], 0
        for s in cust:
            d = s.get("demand", 0)
            if load + d > limit and gs[-1]: gs.append([]); load = 0
            gs[-1].append(s); load += d
        if len(gs) <= n and all(sum(x.get("demand", 0) for x in g) <= cap for g in gs): return gs
    return None

def optimize_delivery_route(product, stops=None, n_vehicles=1, capacity_kg=1e9, ambient_c=30,
                            speed_kmh=40, cargo_value_yuan=50000, include_trace=False):
    """冷链配送路线优化（单/多车）：按载重分车，再对每辆车的配送顺序求最优，
    综合时间窗、开门升温、保质期损耗与成本；并给出与原始顺序的对比。stops[0]为仓库。"""
    p = _prod(product)
    if not p: return _bad()
    stops = stops or DEMO_STOPS
    if len(stops) < 2: return {"error": "至少需要1个仓库和1个配送点"}
    for s in stops: s.setdefault("demand", 0)
    gs = _groups(stops[1:], stops[0], int(n_vehicles), capacity_kg)
    if gs is None:
        return {"error": f"载重不足：总需求{sum(s['demand'] for s in stops[1:])}kg，{n_vehicles}辆×{capacity_kg}kg装不下，请增加车辆或载重"}
    vehicles, base_cost = [], 0.0
    for i, g in enumerate(gs, 1):
        sub = [stops[0], *g]
        best = _best_order(sub, p, ambient_c, speed_kmh, cargo_value_yuan)
        r = _simulate([0, *best], sub, p, ambient_c, speed_kmh, cargo_value_yuan, include_trace)
        base_cost += _simulate(list(range(len(sub))), sub, p, ambient_c, speed_kmh, cargo_value_yuan)["cost_yuan"]
        r.update(vehicle=i, load_kg=sum(s["demand"] for s in g), path=[sub[j]["name"] for j in best])
        vehicles.append(r)
    total = round(sum(v["cost_yuan"] for v in vehicles), 1)
    return {"product": p["name"], "vehicles": vehicles, "total_cost_yuan": total,
            "baseline_cost_yuan": round(base_cost, 1), "saving_yuan": round(base_cost - total, 1),
            "total_km": round(sum(v["km"] for v in vehicles), 1)}

def assess_temperature_log(product, log):
    """温度日志诊断：统计超温时长、估算保质期损耗并给出处置建议。log=[{"t_min":0,"temp":4.2},...]"""
    p = _prod(product)
    if not p: return _bad()
    log = sorted(log, key=lambda r: r["t_min"])
    if len(log) < 2: return {"error": "日志至少需要2个点"}
    out = worst = extra = 0.0
    for a, b in zip(log, log[1:]):
        dt = b["t_min"] - a["t_min"]; tmp = (a["temp"] + b["temp"]) / 2
        extra += (_loss_rate(tmp, p) - 1 / 1440) * dt
        hi_t, lo_t = max(a["temp"], b["temp"]), min(a["temp"], b["temp"])
        if hi_t > p["hi"] or lo_t < p["lo"]:  # 任一端点越界即计入该时段
            out += dt; worst = max(worst, hi_t - p["hi"], p["lo"] - lo_t)
    if out == 0: verdict = "温度全程合规，可放行"
    elif out <= 30 and worst <= 2: verdict = "轻微偏离，建议隔离并抽检后决定是否放行"
    else: verdict = "偏离较严重，建议暂扣，交质量部门/厂家依据稳定性数据判定"
    extra = max(extra, 0)
    return {"product": p["name"], "allowed_range": [p["lo"], p["hi"]], "minutes_out_of_range": out,
            "max_deviation_c": round(worst, 1), "lost_shelf_days": round(extra, 3),
            "lost_shelf_pct": round(extra / p["shelf"] * 100, 3), "verdict": verdict,
            "note": "基于Q10模型估算；疫苗/药品须按GSP及厂家规定处置"}

def temperature_alerts(product, readings):
    """实时温度告警：越限、临界预警、升/降温趋势预测何时越限、开门过久、累计超温。readings 到'当前'为止。"""
    p = _prod(product)
    if not p: return _bad()
    rs = sorted(readings, key=lambda r: r["t_min"])
    if not rs: return {"error": "没有读数"}
    lo, hi, T = p["lo"], p["hi"], rs[-1]["temp"]; al = []
    add = lambda sev, msg, act: al.append({"severity": sev, "message": msg, "action": act})
    if T > hi or T < lo:
        dev = max(T - hi, lo - T)
        add("critical" if dev > 2 else "high", f"当前{T}℃，超出温区[{lo},{hi}]达{dev:.1f}℃",
            "立即检查制冷机组与车门；转入备用冷链设备；记录并隔离该批次")
    elif T > hi - 1 or T < lo + 1:
        add("warning", f"当前{T}℃，已逼近温区边界[{lo},{hi}]", "提前检查机组设定与门封，减少开门")
    rec = rs[-6:]; dt = rec[-1]["t_min"] - rec[0]["t_min"]; slope = (rec[-1]["temp"] - rec[0]["temp"]) / dt if dt > 0 else 0
    if slope > 0.02 and T <= hi:
        eta = (hi - T) / slope
        add("warning" if eta <= 30 else "info", f"升温速率{slope*10:.2f}℃/10分钟，预计{eta:.0f}分钟后超上限", "排查制冷故障或门未关")
    elif slope < -0.02 and T >= lo:
        eta = (T - lo) / -slope
        add("warning" if eta <= 30 else "info", f"降温速率{-slope*10:.2f}℃/10分钟，预计{eta:.0f}分钟后低于下限", "检查机组是否过冷，防冻伤")
    start = None
    for r in reversed(rs):
        if r.get("door_open"): start = r["t_min"]
        else: break
    if start is not None and rs[-1]["t_min"] - start >= 10:
        add("warning", f"车门已持续打开{rs[-1]['t_min']-start:.0f}分钟", "尽快关门；拆分卸货批次缩短开门时间")
    if len(rs) >= 2:
        out = assess_temperature_log(product, rs)["minutes_out_of_range"]
        if out >= 30: add("critical", f"累计超温{out:.0f}分钟", "该批次进入质量评估流程，禁止直接放行")
    rank = {"critical": 3, "high": 3, "warning": 2, "info": 1}
    top = max([rank[a["severity"]] for a in al] + [0])
    return {"status": "报警" if top == 3 else "预警" if top == 2 else "正常", "latest_temp": T,
            "slope_c_per_min": round(slope, 3), "alerts": al}

def fefo_inventory(items, orders, near_expiry_days=7):
    """冷库库存先到期先出(FEFO)：按剩余效期分配订单，找出缺货、临期与过期批次。
    items=[{sku,batch,qty,days_left,location}]；orders=[{sku,qty,min_days_left(可选，客户要求最短剩余效期)}]"""
    expired = [i for i in items if i["days_left"] <= 0]
    bs = sorted([dict(i) for i in items if i["days_left"] > 0], key=lambda b: b["days_left"])
    alloc, short = [], []
    for o in orders:
        need = o["qty"]
        for b in bs:
            if need <= 0: break
            if b["sku"] != o["sku"] or b["qty"] <= 0 or b["days_left"] < o.get("min_days_left", 0): continue
            take = min(need, b["qty"]); b["qty"] -= take; need -= take
            alloc.append({"sku": o["sku"], "batch": b["batch"], "qty": take, "days_left": b["days_left"], "location": b.get("location", "")})
        if need > 0: short.append({"sku": o["sku"], "short_qty": need})
    near = [{"sku": b["sku"], "batch": b["batch"], "qty": b["qty"], "days_left": b["days_left"],
             "advice": "优先促销/调拨/加急配送" if b["days_left"] <= near_expiry_days / 2 else "优先安排出库"}
            for b in bs if b["qty"] > 0 and b["days_left"] <= near_expiry_days]
    return {"allocations": alloc, "shortages": short, "near_expiry_remaining": near,
            "expired": [{"sku": e["sku"], "batch": e["batch"], "qty": e["qty"]} for e in expired]}

def forecast_replenishment(history, stock, lead_days=2, service_z=1.65, shelf_days=7, horizon=7):
    """需求预测与补货：近7日均值+趋势预测，安全库存=z·σ·√提前期，订货量受货架期上限约束(避免囤到过期)。"""
    if len(history) < 7: return {"error": "至少需要7天历史需求"}
    w = history[-14:]; ma = statistics.mean(history[-7:])
    slope = statistics.linear_regression(list(range(len(w))), w).slope if len(w) >= 3 else 0
    fc = [round(max(0, ma + slope * (i + 1)), 1) for i in range(horizon)]
    avg = statistics.mean(fc); sd = statistics.pstdev(w)
    ss = service_z * sd * math.sqrt(lead_days); rop = avg * lead_days + ss
    target = avg * (lead_days + horizon) + ss; cap = avg * shelf_days * 0.8
    qty = max(0, min(target - stock, cap))
    return {"forecast": fc, "avg_daily_demand": round(avg, 1), "trend_per_day": round(slope, 2),
            "safety_stock": round(ss), "reorder_point": round(rop), "stock_cover_days": round(stock / avg, 1) if avg else None,
            "suggested_order_qty": round(qty), "need_reorder_now": stock <= rop,
            "capped_by_shelf_life": target - stock > cap}

def compare_transport_modes(product, distance_km, weight_kg, cargo_value_yuan=50000, ambient_c=30):
    """比较冷藏卡车/冷藏铁路/航空冷链的时效、总成本(运费+品质损耗折价)。"""
    p = _prod(product)
    if not p: return _bad()
    modes = {"冷藏卡车": (60, 3.2, 5, .04), "冷藏铁路": (45, 1.6, 24, .04), "航空冷链": (700, 18.0, 6, .08)}
    res = []
    for n, (spd, rate, fixed_h, k) in modes.items():
        hrs = distance_km / spd + fixed_h
        loss = max((_loss_rate(p["set"] + (ambient_c - p["set"]) * k, p) - 1 / 1440) * hrs * 60, 0)
        res.append({"mode": n, "hours": round(hrs, 1), "freight_yuan": round(distance_km * weight_kg / 1000 * rate),
                    "lost_shelf_days": round(loss, 4), "total_cost_yuan": round(distance_km * weight_kg / 1000 * rate + loss / p["shelf"] * cargo_value_yuan)})
    return {"product": p["name"], "ranked_by_total_cost": sorted(res, key=lambda r: r["total_cost_yuan"])}

def simulate_temperature_log(product, minutes=240, scenario="normal", seed=1):
    """生成演示温度日志(每分钟)。scenario: normal / door_open(90分钟起开门25分钟) / compressor_fault(120分钟起机组失效)"""
    p = _prod(product)
    if not p: return _bad()
    rnd = random.Random(seed); T, out = p["set"], []
    for t in range(0, minutes + 1, 2):
        door = scenario == "door_open" and 90 <= t < 115
        if scenario == "compressor_fault" and t >= 120: T += (30 - T) * 0.02
        elif door: T += (30 - T) * 0.024
        else: T += (p["set"] - T) * 0.1
        out.append({"t_min": t, "temp": round(T + rnd.uniform(-.15, .15), 2), "door_open": door})
    return out

def list_products(): return PRODUCTS
def get_demo_stops(): return DEMO_STOPS

# ---- 工具声明(OpenAI/智谱 function calling) ----
_n, _s = {"type": "number"}, {"type": "string"}
_o = lambda props, req=(): {"type": "object", "properties": props, "required": list(req)}
_arr = lambda item: {"type": "array", "items": item}
_PK = {"type": "string", "enum": list(PRODUCTS)}
_STOP = _o({"name": _s, "lat": _n, "lng": _n, "win": _arr(_n), "dwell": _n, "demand": _n}, ["name", "lat", "lng", "win", "dwell"])
_RD = _o({"t_min": _n, "temp": _n, "door_open": {"type": "boolean"}}, ["t_min", "temp"])
SPEC = [
 {"name": "optimize_delivery_route", "description": "冷链配送路线优化(支持多车、载重、时间窗、开门升温、保质期损耗)。stops第一个为仓库；不传stops用演示数据；win为相对发车的分钟时间窗。",
  "parameters": _o({"product": _PK, "stops": _arr(_STOP), "n_vehicles": _n, "capacity_kg": _n, "ambient_c": _n, "speed_kmh": _n, "cargo_value_yuan": _n}, ["product"])},
 {"name": "assess_temperature_log", "description": "分析一段完整温度日志：超温时长、保质期损耗、放行/暂扣建议。",
  "parameters": _o({"product": _PK, "log": _arr(_RD)}, ["product", "log"])},
 {"name": "temperature_alerts", "description": "对截至当前的温度读数做实时告警：越限、趋势预测、开门过久、累计超温。",
  "parameters": _o({"product": _PK, "readings": _arr(_RD)}, ["product", "readings"])},
 {"name": "fefo_inventory", "description": "冷库先到期先出(FEFO)订单分配，并找出缺货、临期、过期批次。",
  "parameters": _o({"items": _arr(_o({"sku": _s, "batch": _s, "qty": _n, "days_left": _n, "location": _s}, ["sku", "batch", "qty", "days_left"])),
                    "orders": _arr(_o({"sku": _s, "qty": _n, "min_days_left": _n}, ["sku", "qty"])), "near_expiry_days": _n}, ["items", "orders"])},
 {"name": "forecast_replenishment", "description": "需求预测与补货建议(安全库存、再订货点、货架期约束)。",
  "parameters": _o({"history": _arr(_n), "stock": _n, "lead_days": _n, "service_z": _n, "shelf_days": _n, "horizon": _n}, ["history", "stock"])},
 {"name": "compare_transport_modes", "description": "比较冷藏卡车/铁路/航空冷链的时效与总成本。",
  "parameters": _o({"product": _PK, "distance_km": _n, "weight_kg": _n, "cargo_value_yuan": _n, "ambient_c": _n}, ["product", "distance_km", "weight_kg"])},
 {"name": "list_products", "description": "列出支持的货品及温区参数。", "parameters": _o({})},
 {"name": "get_demo_stops", "description": "获取上海演示配送点。", "parameters": _o({})},
]
REGISTRY = {f.__name__: f for f in (optimize_delivery_route, assess_temperature_log, temperature_alerts, fefo_inventory,
                                    forecast_replenishment, compare_transport_modes, list_products, get_demo_stops)}
