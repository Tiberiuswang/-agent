"""冷链运输优化工具集：纯 Python，可单独测试，也供智能体与网页共用。参数见 cn_params.py（含依据等级）。"""
import itertools, math, random, statistics
from cn_params import (PRODUCTS, VEHICLES, COST, MAX_CONT_DRIVE_MIN, REST_MIN, CITY_DELIVERY_SOFT_HOURS)

DEMO_STOPS = [  # win=时间窗(相对发车的分钟)，dwell=卸货停留分钟，demand=卸货量kg；坐标为GCJ-02(高德坐标系)，为示意位置
    {"name": "仓库", "address": "上海市黄浦区人民广场", "lat": 31.2304, "lng": 121.4737, "win": [0, 9999], "dwell": 0, "demand": 0},
    {"name": "浦东医院", "address": "上海市浦东新区世纪大道", "lat": 31.2220, "lng": 121.5440, "win": [30, 120], "dwell": 15, "demand": 300},
    {"name": "徐汇超市", "address": "上海市徐汇区漕溪北路", "lat": 31.1930, "lng": 121.4370, "win": [20, 90], "dwell": 20, "demand": 500},
    {"name": "闵行门店", "address": "上海市闵行区莘庄", "lat": 31.1110, "lng": 121.3820, "win": [60, 180], "dwell": 15, "demand": 400},
    {"name": "宝山配送站", "address": "上海市宝山区淞宝路", "lat": 31.4000, "lng": 121.4900, "win": [90, 240], "dwell": 20, "demand": 600},
    {"name": "嘉定餐厅", "address": "上海市嘉定区博乐路", "lat": 31.3800, "lng": 121.2600, "win": [120, 260], "dwell": 15, "demand": 350},
]

def _prod(key):
    return PRODUCTS.get(key)

def _bad(): return {"error": f"未知货品，可选：{list(PRODUCTS)}"}

def _km(a, b):
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dl = math.radians(b["lng"] - a["lng"])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h)) * 1.3  # 1.3=路网曲折系数(无高德数据时的估算)

def _loss_rate(temp, p):  # 每分钟消耗的"等效保质期(天)"
    return p["q10"] ** ((temp - p["set"]) / 10) / 1440

def _leg(a, b, ctx):
    """两点间 (公里, 分钟, 过路费)。有高德矩阵用高德，否则直线×1.3÷车速。"""
    r = ctx.get("road")
    if r:
        i, j = a["_i"], b["_i"]
        return r["km"][i][j], r["min"][i][j] * ctx["veh"]["time_factor"], r["toll"][i][j] * ctx["veh"]["toll_factor"]
    d = _km(a, b)
    return d, d / ctx["spd"] * 60, 0.0

def _simulate(order, stops, ctx, trace_on=False):
    """逐分钟模拟：行驶/等待时制冷机拉回设定温度，开门作业时向环境温度升温；并核算成本构成与合规提示。"""
    p, veh, c = ctx["p"], ctx["veh"], ctx["c"]
    S = {"t": 0, "temp": p["set"], "extra": 0.0, "out": 0, "peak": p["set"]}
    trace = [[0, p["set"]]]
    def tick(target, k):
        S["temp"] += (target - S["temp"]) * k; S["t"] += 1
        S["extra"] += _loss_rate(S["temp"], p) - 1 / 1440
        S["out"] += S["temp"] > p["hi"] or S["temp"] < p["lo"]
        S["peak"] = max(S["peak"], S["temp"])
        if trace_on: trace.append([S["t"], round(S["temp"], 2)])
    km = late = tolls = 0.0; arr = []; cur = stops[order[0]]; run = maxrun = 0
    for idx in order[1:]:
        s = stops[idx]; d, m, tl = _leg(cur, s, ctx); km += d; tolls += tl
        for _ in range(round(m)): tick(p["set"], veh["recover_k"]); run += 1
        maxrun = max(maxrun, run)
        arr.append([s["name"], S["t"]]); late += max(0, S["t"] - s["win"][1])
        wait = max(0, int(s["win"][0] - S["t"]))
        for _ in range(wait): tick(p["set"], veh["recover_k"])
        for _ in range(int(s["dwell"])): tick(ctx["amb"], veh["door_k"])
        if wait + s["dwell"] >= REST_MIN: run = 0  # 停车≥20分钟视为有效休息
        cur = s
    hours = S["t"] / 60; extra = max(S["extra"], 0)
    fixed_h = c["driver_per_h"] + (veh["price"] / c["life_years"] + veh["insurance"]) / c["hours_per_year"]
    bd = {"燃油+保养": km * (veh["drive_l100"] / 100 * c["fuel_price"] + c["maint_per_km"]),
          "制冷机组油耗": hours * veh["reefer_lph"] * c["fuel_price"],
          "司机+折旧+保险": hours * fixed_h, "过路费": tolls, "迟到罚金": late * c["late_per_min"],
          "品质损耗折价": extra / p["shelf"] * ctx["val"]}
    warns = []
    if maxrun > MAX_CONT_DRIVE_MIN: warns.append("连续驾驶超4小时且未停车休息≥20分钟，需插入休息（道路交通安全法实施条例第62条）")
    if hours > CITY_DELIVERY_SOFT_HOURS: warns.append(f"单趟{hours:.1f}小时，超过同城配送建议的4~6小时，货品品质与迟到风险上升")
    if S["out"]: warns.append(f"存在{S['out']}分钟超温，建议缩短单点卸货时间或拆分车次")
    r = {"km": round(km, 1), "hours": round(hours, 2), "late_min": round(late), "min_out_of_range": S["out"],
         "peak_temp_c": round(S["peak"], 1), "lost_shelf_days": round(extra, 4), "toll_yuan": round(tolls, 1),
         "cost_yuan": round(sum(bd.values()), 1), "cost_breakdown": {k: round(v, 1) for k, v in bd.items()},
         "arrivals_min": arr, "warnings": warns}
    if trace_on: r["trace"] = trace
    return r

def _best_order(stops, ctx):
    idx = list(range(1, len(stops)))
    cost = lambda o: _simulate([0, *o], stops, ctx)["cost_yuan"]
    if len(idx) <= 6: return list(min(itertools.permutations(idx), key=cost))  # 穷举
    order, left, cur = [], idx[:], 0  # 最近邻 + 两两交换改进
    while left:
        nx = min(left, key=lambda j: _leg(stops[cur], stops[j], ctx)[1]); order.append(nx); left.remove(nx); cur = nx
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

def optimize_delivery_route(product, stops=None, n_vehicles=1, vehicle="4.2m", capacity_kg=None, ambient_c=25,
                            speed_kmh=30, cargo_value_yuan=50000, include_trace=False, costs=None,
                            use_amap=False, road=None, _amap_key=None):
    """冷链配送路线优化（单/多车）。stops[0]为仓库，坐标为高德GCJ-02。按载重分车，再对每辆车的配送顺序求最优，
    综合：时间窗、开门升温、保质期损耗、油耗/冷机油耗/人工折旧/过路费/迟到罚金；对比原顺序。
    use_amap=True 且提供Key时，用高德驾车路线规划的真实距离、耗时(含路况)和过路费；否则用直线×1.3÷车速估算。"""
    p, veh = PRODUCTS.get(product), VEHICLES.get(vehicle)
    if not p: return _bad()
    if not veh: return {"error": f"未知车型，可选：{list(VEHICLES)}"}
    stops = [dict(s, _i=i) for i, s in enumerate(stops or DEMO_STOPS)]
    if len(stops) < 2: return {"error": "至少需要1个仓库和1个配送点"}
    for s in stops: s.setdefault("demand", 0)
    warnings, source = [], "直线距离×1.3÷车速（估算）"
    if use_amap:
        if not _amap_key: warnings.append("未提供高德Key，已改用估算距离")
        else:
            try:
                import amap
                road = amap.build_matrix(stops, _amap_key)
                source = f"高德驾车路线规划（{road['calls']}次调用，含实时路况，小客车口径×车型系数）"
            except Exception as e:  # 失败不中断：回退估算并提示
                warnings.append(f"高德调用失败，已改用估算距离：{e}")
    cap = capacity_kg or veh["payload"]
    ctx = {"p": p, "veh": veh, "c": {**COST, **(costs or {})}, "amb": ambient_c, "spd": speed_kmh,
           "val": cargo_value_yuan, "road": road}
    gs = _groups(stops[1:], stops[0], int(n_vehicles), cap)
    if gs is None:
        return {"error": f"载重不足：总需求{sum(s['demand'] for s in stops[1:]):.0f}kg，{n_vehicles}辆×{cap:.0f}kg装不下，请增加车辆或换大车型"}
    vehicles, base_cost = [], 0.0
    for i, g in enumerate(gs, 1):
        sub = [stops[0], *g]
        best = _best_order(sub, ctx)
        r = _simulate([0, *best], sub, ctx, include_trace)
        base_cost += _simulate(list(range(len(sub))), sub, ctx)["cost_yuan"]
        r.update(vehicle=i, load_kg=sum(s["demand"] for s in g), path=[sub[j]["name"] for j in best])
        vehicles.append(r)
    total = round(sum(v["cost_yuan"] for v in vehicles), 1)
    bd = {k: round(sum(v["cost_breakdown"][k] for v in vehicles), 1) for k in vehicles[0]["cost_breakdown"]}
    return {"product": p["name"], "vehicle_type": veh["name"], "road_source": source, "warnings": warnings,
            "vehicles": vehicles, "total_cost_yuan": total, "cost_breakdown": bd,
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

def compare_transport_modes(product, distance_km, weight_kg, cargo_value_yuan=50000, ambient_c=25):
    """比较冷藏卡车/冷藏铁路/航空冷链的时效与总成本(运费+品质损耗折价)。
    费率(元/吨·公里)为[估算]占位：公路参考行业测算(普通重卡0.35~0.45，冷链上浮至约0.7)，铁路/航空请填入实际询价。"""
    p = PRODUCTS.get(product)
    if not p: return _bad()
    t = weight_kg / 1000
    modes = {"冷藏卡车": (60, 0.75, 5, .04), "冷藏铁路": (45, 0.45, 24, .04), "航空冷链": (700, 10.0, 6, .08)}
    res = []
    for n, (spd, rate, fixed_h, k) in modes.items():
        hrs = distance_km / spd + fixed_h + (distance_km / spd // 4) * REST_MIN / 60 * (n == "冷藏卡车")  # 公路含4小时休20分钟
        loss = max((_loss_rate(p["set"] + (ambient_c - p["set"]) * k, p) - 1 / 1440) * hrs * 60, 0)
        fr = distance_km * t * rate
        res.append({"mode": n, "hours": round(hrs, 1), "freight_yuan": round(fr), "lost_shelf_days": round(loss, 4),
                    "total_cost_yuan": round(fr + loss / p["shelf"] * cargo_value_yuan)})
    return {"product": p["name"], "ranked_by_total_cost": sorted(res, key=lambda r: r["total_cost_yuan"]),
            "note": "费率为估算占位，请替换为实际报价"}

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

def geocode_address(address, city=None, _amap_key=None):
    """地址转坐标(高德地理编码，GCJ-02)。"""
    import amap
    try: return amap.geocode(address, _amap_key, city)
    except amap.AmapError as e: return {"error": str(e)}

def get_weather(city, _amap_key=None):
    """查询城市实时气温(高德天气)，可作为路线优化的环境温度。city可为城市名或adcode。"""
    import amap
    try:
        ad = city if str(city).isdigit() else amap.geocode(city, _amap_key)["adcode"]
        return amap.weather(ad, _amap_key)
    except amap.AmapError as e: return {"error": str(e)}

def list_products(): return PRODUCTS
def list_vehicles(): return VEHICLES
def get_demo_stops(): return DEMO_STOPS

# ---- 工具声明(OpenAI/智谱 function calling) ----
_n, _s = {"type": "number"}, {"type": "string"}
_o = lambda props, req=(): {"type": "object", "properties": props, "required": list(req)}
_arr = lambda item: {"type": "array", "items": item}
_PK = {"type": "string", "enum": list(PRODUCTS)}
_STOP = _o({"name": _s, "lat": _n, "lng": _n, "win": _arr(_n), "dwell": _n, "demand": _n}, ["name", "lat", "lng", "win", "dwell"])
_RD = _o({"t_min": _n, "temp": _n, "door_open": {"type": "boolean"}}, ["t_min", "temp"])
SPEC = [
 {"name": "optimize_delivery_route", "description": "冷链配送路线优化(多车、载重、时间窗、开门升温、保质期损耗、中国成本模型)。stops第一个为仓库，坐标为高德GCJ-02；不传stops用演示数据；win为相对发车的分钟时间窗。use_amap=true 用高德真实路况。",
  "parameters": _o({"product": _PK, "stops": _arr(_STOP), "n_vehicles": _n, "vehicle": {"type": "string", "enum": list(VEHICLES)}, "capacity_kg": _n,
                    "ambient_c": _n, "speed_kmh": _n, "cargo_value_yuan": _n, "use_amap": {"type": "boolean"}}, ["product"])},
 {"name": "geocode_address", "description": "地址转经纬度(高德)。", "parameters": _o({"address": _s, "city": _s}, ["address"])},
 {"name": "get_weather", "description": "查询城市实时气温(高德)，用作环境温度。", "parameters": _o({"city": _s}, ["city"])},
 {"name": "list_vehicles", "description": "列出冷藏车型参数。", "parameters": _o({})},
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
                                    forecast_replenishment, compare_transport_modes, list_products, list_vehicles,
                                    get_demo_stops, geocode_address, get_weather)}
NEEDS_KEY = {"optimize_delivery_route", "geocode_address", "get_weather"}  # 这些工具由系统注入高德Key，模型看不到
