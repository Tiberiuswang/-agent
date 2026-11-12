# 冷链优化智能体

智谱 GLM + 高德 + Streamlit

## 功能

- 路线优化：城市配送 / 干线运输，多车、载重、时间窗、真实路况
- 温度监控
- 库存效期 FEFO
- 需求补货
- 运输方式对比
- 智能体对话

## 运行

```bash
pip install -r requirements.txt
# 可选：配置 secrets
mkdir -p .streamlit
# 在 .streamlit/secrets.toml 写入 ZHIPU_API_KEY
streamlit run app.py
```

## 密钥

- 高德 Key 已内置默认值，也可通过 `AMAP_KEY` secrets 覆盖
- 智谱 API Key 仅用于「智能体」页，通过 secrets 或环境变量 `ZHIPU_API_KEY` 配置
- 界面不展示任何 Key 输入框

## 高德说明

用到的接口：地理编码、驾车路线规划、天气。坐标系 GCJ-02。失败时自动回退直线估算。

## 注意

模型默认 `glm-5.3-flash`。疫苗药品处置须遵守 GSP 与厂家规定，本工具仅给建议。
