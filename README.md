# 🧊 冷链优化智能体（智谱 GLM-5.3-Flash + 高德 + Streamlit）

## 页面
🚚 路线优化（多车/载重/时间窗/高德真实路况）· 🌡️ 温度监控 · 🧊 库存效期(FEFO) · 📈 需求补货 · ✈️ 运输方式 · 🤖 智能体 · ⚙️ 参数依据

## 运行
    pip install -r requirements.txt
    cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # 填入两个Key
    streamlit run app.py

## 高德接入
1. 高德开放平台 → 控制台 → 创建应用 → 添加 Key，服务平台选 **Web服务**
2. 按控制台指引完成开发者认证；日配额与并发(QPS)以控制台为准
3. Key 填入侧边栏或 secrets（`AMAP_KEY`）

用到的接口：地理编码 `/v3/geocode/geo`、驾车路线规划 `/v5/direction/driving`（距离/耗时/过路费）、天气 `/v3/weather/weatherInfo`。
- 坐标系为 **GCJ-02**；GPS 的 WGS-84 坐标先用 `amap.wgs84_to_gcj02()` 转换
- N 个点默认只查一半方向（省额度）：N=7 约 21 次调用/次优化；相同两点有内存缓存
- 高德为小客车口径；本工具按车型加时长与过路费系数。**货车限行/限高限重未校验**，需另接高德货车路径规划
- 调用失败会自动回退到"直线×1.3÷车速"估算并在页面提示

## 参数
全部在 `cn_params.py`，每项标注依据：`[标准]` `[政策]` `[行业]` `[估算]`。`[估算]` 项必须用你们的数据校准
（载重/油耗/车价、冷机油耗、迟到罚金、Q10 变质系数、开门升温系数、铁路/航空运价）。

## 免费上线（Streamlit Community Cloud）
推 GitHub 公开仓库 → share.streamlit.io 新建应用(app.py) → Secrets 粘贴两个 Key → Deploy

## 注意
模型编码默认 `glm-5.3-flash`，以智谱控制台为准。疫苗药品处置须遵守 GSP 与厂家规定，本工具仅给建议。
