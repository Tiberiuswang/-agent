"""冷链供应链智能体：智谱 GLM-5.3-Flash + function calling。命令行用法：python agent.py"""
import json, os
from tools import SPEC, REGISTRY, NEEDS_KEY

MODEL = os.getenv("GLM_MODEL", "glm-5.3-flash")  # 以智谱开放平台控制台显示的模型编码为准
BASE_URL = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
SYSTEM = ("你是冷链物流优化智能体。涉及路线、温度、库存效期、补货、运输方式的结论必须调用工具获取，不得凭空估算。"
          "先说结论与节省/风险，再给依据与行动建议；药品疫苗的放行/报废只能给出建议，最终由质量负责人决定。简体中文，简洁。")
TOOLS = [{"type": "function", "function": f} for f in SPEC]

def make_client(api_key=None):
    from openai import OpenAI
    return OpenAI(api_key=api_key or os.environ["ZHIPU_API_KEY"], base_url=BASE_URL)

def run_tool(name, args, secrets=None):
    args = {k: v for k, v in args.items() if not k.startswith("_")}  # 模型不能自带密钥参数
    if name in NEEDS_KEY and secrets and secrets.get("amap_key"): args["_amap_key"] = secrets["amap_key"]
    try:
        return json.dumps(REGISTRY[name](**args), ensure_ascii=False)
    except Exception as e:  # 错误回传给模型，让它自行修正参数
        return json.dumps({"error": str(e)}, ensure_ascii=False)

def chat(messages, client, model=MODEL, max_steps=8, on_tool=None, secrets=None):
    """messages 会被原地追加。on_tool(name, args, result) 可用于界面展示工具调用。"""
    for _ in range(max_steps):
        msg = client.chat.completions.create(model=model, messages=messages, tools=TOOLS).choices[0].message
        messages.append(msg.model_dump(exclude_none=True))  # 原样保留，含思考内容字段
        if not msg.tool_calls:
            return msg.content
        for c in msg.tool_calls:
            args = json.loads(c.function.arguments or "{}")
            result = run_tool(c.function.name, args, secrets)
            if on_tool: on_tool(c.function.name, args, result)
            messages.append({"role": "tool", "tool_call_id": c.id, "content": result})
    return "（工具调用轮数超限，请换个问法）"

if __name__ == "__main__":
    client, history = make_client(), [{"role": "system", "content": SYSTEM}]
    print("冷链智能体已就绪，输入 q 退出。例：用演示数据，2辆车每辆1200kg，优化疫苗配送")
    while (q := input("\n你> ").strip()) not in ("q", "quit"):
        if q:
            history.append({"role": "user", "content": q})
            print("\n" + chat(history, client, on_tool=lambda n, a, r: print(f"  🔧 {n}"), secrets={"amap_key": os.getenv("AMAP_KEY")}))
