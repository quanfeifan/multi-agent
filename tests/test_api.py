import os
from openai import OpenAI

# 从环境变量读取 API key
api_key = os.getenv("SILICONFLOW_API_KEY")
if not api_key:
    print("错误: 请设置 SILICONFLOW_API_KEY 环境变量")
    print("获取 API Key: https://siliconflow.cn/")
    exit(1)

client = OpenAI(
    api_key=api_key,
    base_url="https://api.siliconflow.cn/v1"
)

response = client.chat.completions.create(
    model="Qwen/Qwen3-8B",
    messages=[
        {"role": "system", "content": "你是一个有用的助手"},
        {"role": "user", "content": "你好，请介绍一下你自己"}
    ],
    temperature=0.7,
    max_tokens=1000
)
print(response.choices[0].message.content)
