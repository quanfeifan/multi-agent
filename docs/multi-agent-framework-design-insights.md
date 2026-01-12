# 多智能体协同框架设计借鉴要点

> 基于 Shannon + MiroFlow + LangGraph 框架分析的架构设计参考

## 框架对比概览

| 特性 | Shannon | MiroFlow | LangGraph | 推荐方案 |
|------|---------|----------|-----------|----------|
| **架构风格** | 微服务分层 | 单体 Python | 图式状态机 | 分层图式架构 |
| **编排方式** | Temporal + 模式库 | 主从 + 分层 | StateGraph + Edges | 图式编排 + 模式库 |
| **状态管理** | PostgreSQL + Redis | TaskTracer Pydantic | TypedDict + Reducer | 统一状态定义 |
| **工具管理** | 内置 + MCP | MCP 原生 | LangChain Tools | MCP 统一接口 |
| **子 Agent** | P2P 自动依赖 | 分层独立会话 | Supervisor + Subgraph | Supervisor + Subgraph |
| **人工干预** | OPA 策略审批 | 提示增强 | HITL 原生 | Interrupts + Checkpoints |
| **追踪系统** | Temporal UI + OTEL | TaskTracer JSON | LangSmith | LangSmith 风格 |

---

## 核心洞察

> **多智能体框架 = 图式编排 + 状态驱动 + MCP 工具 + 智能容错**

| 框架 | 核心贡献 |
|------|----------|
| **Shannon** | 模式可组合、P2P 自动协调、时间旅行调试 |
| **MiroFlow** | MCP 原生、智能容错、TaskTracer、提示增强 |
| **LangGraph** | TypedDict 状态机、HITL 原生、子图组合 |

---

## 一、状态机模型 (LangGraph 核心)

### 核心四要素

```python
from typing import TypedDict, Annotated

# 1. State - 状态定义
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # 使用 reducer
    next_action: str | None

# 2. Reducer - 状态归约函数
def add_messages(left: list, right: list) -> list:
    return left + right  # 追加而非覆盖

# 3. Node - 处理状态的纯函数
def llm_node(state: AgentState) -> AgentState:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

# 4. Edge - 定义流转
# 普通边：workflow.add_edge("a", "b")
# 条件边：workflow.add_conditional_edges("a", route_fn, {"b": "b", END: END})

# 构建图
workflow = StateGraph(AgentState)
workflow.add_node("agent", llm_node)
workflow.add_edge("agent", END)
app = workflow.compile()
```

**关键优势**：
- **类型安全**：TypedDict + IDE 友好
- **声明式流转**：边定义流转，节点专注业务
- **状态驱动**：所有决策基于状态，避免隐式传递
- **图式可视化**：天然可可视化，易于理解

---

## 二、MCP 工具统一接口 (MiroFlow 核心)

```python
class MCPToolManager:
    """MCP 协议原生工具管理器"""

    async def get_all_tool_definitions(self):
        """连接所有 MCP 服务器获取工具定义"""
        for config in self.server_configs:
            # 支持 stdio 本地 和 SSE 远程 两种连接
            if isinstance(config["params"], StdioServerParameters):
                async with stdio_client(config["params"]) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_response = await session.list_tools()
                        return self._parse_tools(tools_response)

    async def execute_tool_call(self, server_name, tool_name, arguments):
        """执行工具，带自动纠错"""
        result = await self._call_tool(server_name, tool_name, arguments)

        # 服务器未找到时，自动搜索并纠正
        if "Server not found" in result:
            suggested = await self._find_servers_with_tool(tool_name)
            if len(suggested) == 1:
                return await self._call_tool(suggested[0], tool_name, arguments)
        return result
```

**关键优势**：
- **统一接口**：所有工具通过 MCP 接入
- **自动纠错**：LLM 调错工具时系统自动纠正
- **双连接模式**：本地 stdio + 远程 SSE

---

## 三、P2P 自动协调 (Shannon 核心)

```python
class P2PCoordinator:
    """点对点协调器 - 无需手动编排"""

    def execute(self, tasks: List[SubTask]):
        """基于依赖自动调度"""
        # LLM 自动检测 produces/consumes
        # task_1 produces: ["sales-analysis"]
        # task_2 consumes: ["sales-analysis"]

        dag = self._build_dag(tasks)  # 构建依赖图
        for batch in dag.topological_batches():
            self._execute_parallel(batch)  # 并行执行无依赖任务
```

**关键优势**：
- **自动依赖检测**：LLM 分析数据依赖，无需手动配置
- **智能调度**：自动并行无依赖任务，串行有依赖任务

---

## 四、分层子 Agent 编排

```python
class Orchestrator:
    """分层编排器 - 主从 + 分层子 Agent"""

    async def run_main_agent(self, task):
        """主 Agent 循环"""
        while turn_count < max_turns:
            response, tool_calls = await self._llm_call(...)

            for call in tool_calls:
                if call["server_name"].startswith("agent-"):
                    # 路由到子 Agent
                    result = await self.run_sub_agent(
                        call["server_name"],
                        call["arguments"]
                    )
                else:
                    # 普通工具调用
                    result = await self._execute_tool(...)

    async def run_sub_agent(self, sub_agent_name, task):
        """子 Agent 独立执行"""
        session_id = self.task_log.start_sub_agent_session(sub_agent_name, task)
        # ... 子 Agent 独立循环
        return self._generate_summary()  # 返回摘要，减少上下文压力
```

**关键优势**：
- **工具化子 Agent**：子 Agent 暴露为主 Agent 的"工具"
- **独立会话追踪**：每个子 Agent 会话独立记录
- **摘要返回**：返回摘要而非完整对话

---

## 五、人工干预 (HITL) 原生支持 (LangGraph)

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

# 配置 checkpointer
memory = MemorySaver()
app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["human_review"]
)

# 人工审核节点
def human_review_node(state):
    """在需要人工决策的节点中断"""
    feedback = interrupt({"question": "请审核", "actions": ["approve", "reject"]})
    return {"status": feedback["action"]}

# 使用
config = {"configurable": {"thread_id": "thread-123"}}
result = app.invoke({"messages": ["任务"]}, config)

# 人工审核后恢复
state = app.get_state(config)
if state.next == "human_review":
    app.update_state(config, {"action": "approve"})
    result = app.invoke(None, config)  # 继续执行
```

**关键优势**：
- **中断灵活**：可在任意节点暂停，时间跨度灵活（分钟到天）
- **状态持久化**：支持 Redis、PostgreSQL 等
- **时间旅行**：可查看任意历史时间点的状态

---

## 六、智能容错机制

```python
# 1. 超时装饰器
@with_timeout(900)  # 15 分钟超时
async def execute_tool(...):
    return await tool.call()

# 2. 智能降级
try:
    result = await scrape(url)
except Exception:
    # 特定错误触发备用方案
    result = await markitdown.convert(url)

# 3. 上下文超限处理
while True:
    response = await llm_call(message_history)
    if response:
        return response

    # 渐进式移除对话，保留尽可能多上下文
    if message_history[-1]["role"] == "assistant":
        message_history.pop()
    task_failed = True  # 标记失败

    if len(message_history) <= 2:
        break  # 只剩初始消息，停止
```

**关键策略**：
- **可配置超时**：装饰器灵活设置
- **智能降级**：特定错误触发备用方案
- **渐进式降级**：逐个移除对话
- **失败感知**：不假装成功

---

## 七、TaskTracer 追踪系统

```python
class TaskTracer(BaseModel):
    """基于 Pydantic 的结构化任务追踪器"""

    task_id: str
    status: Literal["pending", "running", "completed", "failed"]

    # 子 Agent 管理
    current_sub_agent_session_id: str | None
    sub_agent_message_history_sessions: dict[str, dict]  # 会话隔离

    # 消息历史
    step_logs: list[StepRecord]

    def log_step(self, step_name: str, message: str, status="info"):
        """记录执行步骤"""
        self.step_logs.append(StepRecord(
            step_name=step_name,
            message=message,
            timestamp=datetime.now(),
            status=status
        ))

    def save(self):
        """增量保存，崩溃不丢失"""
        with open(self.log_path, "w") as f:
            f.write(self.model_dump_json(indent=2))
```

**关键优势**：
- **Pydantic 驱动**：自动序列化/反序列化
- **会话隔离**：主/子 Agent 消息历史分开存储
- **增量保存**：每个 step 后保存

---

## 八、模式可组合设计 (Shannon)

```python
# 模式库
patterns = {
    "react": ReactPattern,          # 思考-行动-观察
    "reflection": ReflectionPattern,# 自我反思
    "cot": ChainOfThoughtPattern,   # 思维链
    "debate": DebatePattern,        # 多智能体辩论
}

# 工作流组合
class ResearchWorkflow:
    patterns = ["react", "reflection"]

class ScientificWorkflow:
    patterns = ["cot", "debate", "tot", "reflection"]
```

**核心思想**：模式像乐高积木，工作流自由组合

---

## 九、推荐融合架构

```
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              Orchestrator (StateGraph + 模式库)              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Supervisor │  │  P2P 协调   │  │   模式库           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
┌───────▼────┐ ┌─────▼────┐ ┌───▼────────┐
│ Main Agent │ │Sub-Agent1│ │Sub-Agent N │
│            │ │          │ │            │
│ ┌────────┐ │ │ ┌──────┐ │ │ ┌────────┐ │
│ │  LLM   │ │ │ │ LLM  │ │ │ │  LLM   │ │
│ └────────┘ │ │ └──────┘ │ │ └────────┘ │
│            │ │          │ │            │
│ ┌────────┐ │ │ ┌──────┐ │ │ ┌────────┐ │
│ │  MCP   │ │ │ │ MCP  │ │ │ │  MCP   │ │
│ └────────┘ │ │ └──────┘ │ │ └────────┘ │
└────────────┘ └──────────┘ └────────────┘
        │             │             │
        └─────────────┼─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │    MCP Servers (统一工具)   │
        │  Search │ Browse │ Code   │
        └─────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                    Data & Storage                          │
│  PostgreSQL │  Redis  │  Qdrant  │  TaskTracer (JSON)       │
└─────────────────────────────────────────────────────────────┘
```

---

## 十、实施建议

### MVP 优先级

| 优先级 | 功能 | 来源 |
|--------|------|------|
| P0 | StateGraph 状态机 | LangGraph |
| P0 | MCP 工具管理 | MiroFlow |
| P0 | TaskTracer 追踪 | MiroFlow |
| P1 | React + Reflection 模式 | Shannon |
| P1 | Supervisor 子 Agent | LangGraph |
| P1 | 智能容错+降级 | MiroFlow |
| P2 | P2P 数据依赖 | Shannon |
| P2 | Interrupts HITL | LangGraph |

### 技术选型

| 组件 | 推荐技术 |
|------|----------|
| 状态定义 | TypedDict + Annotated Reducer |
| 工具协议 | MCP |
| 追踪系统 | Pydantic + JSON |
| 容错机制 | asyncio + retry |
| 可观测性 | 结构化日志 + UI |

### 关键注意事项

1. **从简单开始**：3-4 个节点起步，避免过度设计
2. **MCP 优先**：所有工具统一通过 MCP 接入
3. **会话隔离**：主/子 Agent 消息历史分开存储
4. **状态驱动**：所有决策基于状态，避免隐式传递
5. **智能降级**：工具失败时要有备用方案

---

## 十一、AI 测试闭环 ⭐ 最值钱的实践

**核心洞察**：让 AI 自己运行测试形成闭环，质量可提升 2-3 倍。

```
传统模式：开发者写代码 → AI 改代码 → 开发者手动测试 → 发现问题...
AI 闭环：AI 写代码 → AI 运行测试 → AI 分析失败 → AI 修复 → 通过
```

**配置方式** (在 CLAUDE.md 中)：

```markdown
## 验证方法

每次修改代码后必须运行：
- Python: `pytest tests/ -v`
- JS: `npm test`

测试闭环要求：
1. 修改代码
2. **自动运行测试**（必须）
3. 测试失败 → 自己分析 → 自己修复 → 重新测试
4. 测试通过 → 报告"✅ 测试已通过"

**不要问我要不要运行测试 —— 自动运行，形成闭环**
```

---

## Sources

- [Shannon GitHub](https://github.com/Kocoro-lab/Shannon)
- [MiroFlow GitHub](https://github.com/MiroMindAI/MiroFlow)
- [LangGraph Documentation](https://www.langchain.com/langgraph)
