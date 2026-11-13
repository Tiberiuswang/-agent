"""高德开放平台 Web 服务封装（仅用标准库）。坐标一律为 GCJ-02（高德坐标系）。
用到的接口：地理编码 /v3/geocode/geo、驾车路线规划 /v5/direction/driving、天气 /v3/weather/weatherInfo。"""
import json, math, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://restapi.amap.com"
FRIENDLY = {"10001": "Key无效或已被删除", "10003": "今日调用量已超限", "10009": "Key的服务平台类型不对，请创建“Web服务”类型的Key",
            "10044": "账号日调用量已超限"}
_cache = {}

class AmapError(Exception): pass

def _f(x):  # 高德对空字段常返回 [] 或 ""
    try: return float(x)
    except (TypeError, ValueError): return 0.0

def _get(path, params, key, timeout=10, retries=3):
    if not key: raise AmapError("未提供高德Key")
    url = f"{BASE}{path}?{urllib.parse.urlencode({**params, 'key': key})}"
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r: d = json.loads(r.read().decode("utf-8"))
        except Exception as e:  # 不回显URL，避免泄露Key
            if i == retries - 1: raise AmapError(f"网络请求失败：{type(e).__name__}") from None
            time.sleep(0.5 * (i + 1)); continue
        if str(d.get("status")) == "1": return d
        code, info = str(d.get("infocode", "")), str(d.get("info", ""))
        if ("QPS" in info.upper() or code in ("10019", "10020", "10021")) and i < retries - 1:
            time.sleep(0.7 * (i + 1)); continue  # 触发并发限制：退避重试
        raise AmapError(f"高德返回错误：{FRIENDLY.get(code, info)}（{code}）")
    raise AmapError("请求失败")

def geocode(address, key, city=None):
    ck = ("g", address, city)
    if ck in _cache: return _cache[ck]
    d = _get("/v3/geocode/geo", {"address": address, **({"city": city} if city else {})}, key)
    gs = d.get("geocodes") or []
    if not gs: raise AmapError(f"未找到地址：{address}")
    lng, lat = (float(x) for x in gs[0]["location"].split(","))
    r = {"lng": lng, "lat": lat, "adcode": gs[0].get("adcode"), "formatted": gs[0].get("formatted_address", "")}
    _cache[ck] = r
    return r

def drive(o, d, key, strategy=32):
    """o、d=(lng,lat)。strategy 32=高德推荐(同APP默认)。返回 公里/分钟/过路费(小客车口径)。"""
    ck = ("d", round(o[0], 5), round(o[1], 5), round(d[0], 5), round(d[1], 5), strategy)
    if ck in _cache: return _cache[ck]
    r = _get("/v5/direction/driving", {"origin": f"{o[0]:.6f},{o[1]:.6f}", "destination": f"{d[0]:.6f},{d[1]:.6f}",
                                       "strategy": strategy, "show_fields": "cost"}, key)
    paths = (r.get("route") or {}).get("paths") or []
    if not paths: raise AmapError("两点之间没有可达路线")
    p = paths[0]; c = p.get("cost") or {}
    dur, toll = _f(c.get("duration")), _f(c.get("tolls"))
    if not dur:  # 兜底：按路段累加
        steps = p.get("steps") or []
        dur = sum(_f((s.get("cost") or {}).get("duration")) for s in steps)
        toll = toll or sum(_f((s.get("cost") or {}).get("tolls")) for s in steps)
    out = {"km": _f(p.get("distance")) / 1000, "min": dur / 60, "toll": toll}
    _cache[ck] = out
    return out

def build_matrix(points, key, symmetric=True, workers=2):
    """points=[{lng,lat},...] → 距离(km)/耗时(分钟)/过路费矩阵。symmetric=True 只查一半方向，省一半额度。"""
    n = len(points)
    pairs = [(i, j) for i in range(n) for j in range(n) if i != j and (not symmetric or i < j)]
    def one(ij):
        i, j = ij
        return ij, drive((points[i]["lng"], points[i]["lat"]), (points[j]["lng"], points[j]["lat"]), key)
    M = {k: [[0.0] * n for _ in range(n)] for k in ("km", "min", "toll")}
    with ThreadPoolExecutor(workers) as ex:
        for (i, j), r in ex.map(one, pairs):
            for k, kk in (("km", "km"), ("min", "min"), ("toll", "toll")):
                M[k][i][j] = r[kk]
                if symmetric: M[k][j][i] = r[kk]
    M["calls"] = len(pairs)
    return M

def weather(adcode, key):
    d = _get("/v3/weather/weatherInfo", {"city": adcode, "extensions": "base"}, key)
    lv = (d.get("lives") or [None])[0]
    if not lv: raise AmapError("没有天气数据")
    return {"temp": _f(lv.get("temperature")), "weather": lv.get("weather", ""), "city": lv.get("city", ""), "time": lv.get("reporttime", "")}

# ---- WGS-84(GPS) → GCJ-02(高德) ----

def regeo(lng, lat, key):
    """逆地理编码：坐标 → 地址/名称。"""
    ck = ("r", round(lng, 5), round(lat, 5))
    if ck in _cache: return _cache[ck]
    d = _get("/v3/geocode/regeo", {"location": f"{lng:.6f},{lat:.6f}", "extensions": "base"}, key)
    regeocode = d.get("regeocode") or {}
    addr = regeocode.get("formatted_address") or ""
    comp = regeocode.get("addressComponent") or {}
    name = ""
    pois = (regeocode.get("pois") or [])
    if pois:
        name = pois[0].get("name") or ""
    if not name:
        name = comp.get("building") or comp.get("neighborhood", {}).get("name") if isinstance(comp.get("neighborhood"), dict) else comp.get("township") or addr[:20]
    r = {"lng": float(lng), "lat": float(lat), "address": addr, "name": name or addr[:16] or f"{lat:.4f},{lng:.4f}",
         "adcode": comp.get("adcode"), "city": comp.get("city") or comp.get("province") or ""}
    _cache[ck] = r
    return r

def wgs84_to_gcj02(lng, lat):
    a, ee, pi = 6378245.0, 0.00669342162296594323, math.pi
    x, y = lng - 105.0, lat - 35.0
    dlat = -100 + 2*x + 3*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
    dlat += (20*math.sin(6*x*pi) + 20*math.sin(2*x*pi)) * 2/3 + (20*math.sin(y*pi) + 40*math.sin(y/3*pi)) * 2/3
    dlat += (160*math.sin(y/12*pi) + 320*math.sin(y*pi/30)) * 2/3
    dlng = 300 + x + 2*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
    dlng += (20*math.sin(6*x*pi) + 20*math.sin(2*x*pi)) * 2/3 + (20*math.sin(x*pi) + 40*math.sin(x/3*pi)) * 2/3
    dlng += (150*math.sin(x/12*pi) + 300*math.sin(x/30*pi)) * 2/3
    rad = lat / 180 * pi; m = 1 - ee * math.sin(rad) ** 2; sm = math.sqrt(m)
    return lng + dlng * 180 / (a / sm * math.cos(rad) * pi), lat + dlat * 180 / (a * (1 - ee) / (m * sm) * pi)
