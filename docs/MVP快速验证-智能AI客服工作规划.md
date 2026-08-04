# MVP快速验证 - 智能AI客服详细工作规划

> 从"企业级财务年报分析智能RAG-Agent"到"智能AI客服"的MVP验证阶段
> 原则：不破坏现有财务分析功能，以独立模块叠加方式构建

**文档版本**: v1.0
**创建日期**: 2026-08-02
**预计MVP周期**: 3-4周

---

## 零、总览：MVP目标

### MVP完成后的用户可感知效果

```text
用户在 Streamlit 页面左侧看到一个模式切换按钮：

  [财务年报分析]  |  [企业智能客服]    <-- 新增标签页

选择"企业智能客服"后：
  1. 系统先检查FAQ库，命中则直接返回标准答案（<1秒）
  2. FAQ未命中 → 检索企业产品知识库 → RAG生成回答（2-3秒）
  3. 对话支持多轮上下文记忆（如客户说"那价格呢？"，能关联到之前问的产品）
  4. 识别到客户有负面情绪或明确要求时，触发转人工流程（弹出联系方式/留言表单）
  5. 所有客服对话有独立会话窗口，不影响财务分析功能
```

### MVP不做的事情（明确边界）

- 不做多渠道接入（仅Streamlit）
- 不做工单系统、质检、坐席工作台
- 不做数据分析看板
- 不做模型微调
- 不修改现有财务分析的任何代码逻辑

---

## 一、任务总览表

| 编号 | 任务 | 优先级 | 预估工时 | 依赖 |
|------|------|--------|---------|------|
| T1 | 客服知识库准备 | 高 | 0.5天 | 无 |
| T2 | 客服会话管理层 | 高 | 2天 | 无 |
| T3 | FAQ快速匹配引擎 | 高 | 1.5天 | T1 |
| T4 | 客服意图分类器 | 高 | 2天 | 无 |
| T5 | 情感检测模块 | 中 | 1天 | 无 |
| T6 | 客服检索与生成 | 高 | 1.5天 | T1 |
| T7 | 转人工机制 | 中 | 1天 | T4, T5 |
| T8 | Streamlit UI整合 | 高 | 1.5天 | T2-T7 |
| T9 | 端到端联调与测试 | 高 | 2天 | T8 |
| T10 | 试运行与反馈收集 | 中 | 持续 | T9 |

---

## 二、逐任务详细设计

---

### T1：客服知识库准备

**目标**: 为客服场景准备一个独立的知识库，不与财务知识库混用。

#### 1.1 知识库内容设计

在 `data/` 下创建 `customer_service_kb/` 目录：

```
data/customer_service_kb/
├── faq.json              # FAQ结构化数据（高频问答对）
├── product_docs/         # 产品文档（Markdown格式）
│   ├── 产品A介绍.md
│   ├── 产品B介绍.md
│   ├── 定价说明.md
│   ├── 售后服务政策.md
│   └── 常见问题汇总.md
├── databases/            # 向量数据库产出目录（由ingestion生成）
│   └── chunked_reports/
└── subset.csv            # 文档元数据（格式复用现有subset.csv）
```

#### 1.2 FAQ数据结构（`faq.json`）

```json
[
  {
    "id": "faq_001",
    "category": "产品咨询",
    "question_variants": [
      "产品A支持哪些功能？",
      "产品A有什么功能？",
      "产品A的功能介绍"
    ],
    "standard_answer": "产品A是一款企业级数据分析平台，支持...",
    "keywords": ["产品A", "功能", "介绍"],
    "priority": 1
  }
]
```

#### 1.3 向量化流程

复用现有 `src/ingestion.py` 的向量化逻辑，新增方法 `build_customer_service_index()`：

```python
# 在 src/ingestion.py 中新增方法
def build_customer_service_index(
    data_dir: str = "data/customer_service_kb",
    vector_db_dir: str = "data/customer_service_kb/databases",
    ...
):
    """构建客服知识库向量索引（不修改现有财务索引）"""
```

#### 1.4 产出物

| 文件 | 说明 |
|------|------|
| `data/customer_service_kb/faq.json` | 初始FAQ数据（至少10条） |
| `data/customer_service_kb/product_docs/` | 产品文档（至少3个文档） |
| `data/customer_service_kb/databases/chunked_reports/` | 向量化后的JSON分块 |
| `data/customer_service_kb/databases/` 下的 FAISS/BM25索引文件 | 检索索引 |

#### 1.5 操作步骤

1. 编写FAQ内容（结合实际业务场景）
2. 整理产品文档为Markdown格式
3. 编写 `build_customer_service_index()` 方法
4. 运行脚本生成索引文件
5. 验证检索可用

---

### T2：客服会话管理层

**目标**: 构建独立于财务分析的客服专用会话管理，支持多轮对话上下文保持。

#### 2.1 技术方案

**不修改** `src/conversation.py` 和 `src/agent_memory.py`，新建 `src/cs/` 目录，构建客服专用模块。

#### 2.2 新建文件：`src/cs/__init__.py`

```python
"""客服模块 - 企业智能AI客服核心"""
from .cs_session import CustomerServiceSession
from .cs_session import SessionState
```

#### 2.3 新建文件：`src/cs/cs_session.py`

核心类 `CustomerServiceSession`：

```python
class SessionState(Enum):
    """会话状态枚举"""
    ACTIVE = "active"           # 活跃中
    WAITING = "waiting"         # 等待客户回复
    TRANSFERRING = "transferring"  # 转人工中
    CLOSED = "closed"           # 已关闭

class CustomerServiceSession:
    """客服专用会话管理器
    
    与现有 ConversationManager 的区别：
    - 支持会话生命周期（状态机）
    - 内置客户画像字段
    - 支持未解决问题追踪
    - 记录情绪标签
    """
    
    def __init__(self, session_id: str, max_turns: int = 20):
        self.session_id: str = session_id
        self.state: SessionState = SessionState.ACTIVE
        self.messages: List[Dict] = []       # 消息列表
        self.max_turns: int = max_turns
        self.created_at: str = ""            # 创建时间
        self.last_activity: str = ""         # 最后活跃时间
        
        # 客户画像
        self.customer_profile: Dict = {
            "name": None,
            "level": "normal",               # normal / vip
            "preferred_language": "zh-CN",
        }
        
        # 问题追踪
        self.unresolved_topics: List[str] = []  # 未解决问题主题
        
        # 情绪追踪
        self.sentiment_history: List[Dict] = []  # [{"turn": 1, "sentiment": "neutral"}]
```

**需要实现的方法**：

| 方法 | 功能 |
|------|------|
| `add_message(role, content)` | 添加消息并做轮数截断 |
| `get_context(max_turns)` | 获取最近N轮对话上下文 |
| `mark_unresolved(topic)` | 标记未解决问题 |
| `set_state(state)` | 更新会话状态 |
| `add_sentiment(turn, sentiment)` | 记录情绪标签 |
| `is_expired(timeout_minutes=30)` | 判断会话是否超时 |
| `to_dict()` | 序列化（用于未来持久化） |

#### 2.4 修改文件：`src/api_service.py`

在 `ConversationStore` 旁边新增 `CustomerServiceSessionStore`：

```python
class CustomerServiceSessionStore:
    """客服会话存储（内存，MVP阶段）"""
    
    def __init__(self, max_sessions: int = 100):
        self._sessions: Dict[str, CustomerServiceSession] = {}
        self._max_sessions = max_sessions
    
    def get_or_create(self, conversation_id: str) -> CustomerServiceSession:
        """获取或创建客服会话"""
        ...
```

#### 2.5 产出物

| 文件 | 说明 |
|------|------|
| `src/cs/__init__.py` | 客服模块入口 |
| `src/cs/cs_session.py` | 客服会话管理器 |

---

### T3：FAQ快速匹配引擎

**目标**: 客户问题首先匹配FAQ库，命中则直接返回标准答案（不经过RAG流程），实现<1秒响应。

#### 3.1 技术方案

**双路匹配策略**：
- **路径A - 语义匹配**: 用向量相似度匹配FAQ问题变体
- **路径B - 关键词匹配**: 用关键词/分类做快速过滤

**匹配流程**：
```
用户输入 → 向量化 → 与FAQ库所有问法计算相似度
              │
    相似度 >= 阈值(0.85)  →  返回标准答案（<1秒）
    相似度 >= 阈值(0.70)  →  列出Top3 FAQ作为推荐，同时走RAG
    相似度 <  阈值(0.70)  →  直接走RAG检索
```

#### 3.2 新建文件：`src/cs/faq_engine.py`

```python
class FAQEngine:
    """FAQ快速匹配引擎"""
    
    def __init__(self, faq_file: str = "data/customer_service_kb/faq.json",
                 api_key: str = None):
        self.faq_data: List[Dict] = []          # 加载的FAQ数据
        self.faq_embeddings: List = []           # FAQ问法的向量嵌入
        self.embedding_model = "text-embedding-v3"
        self.semantic_threshold: float = 0.85    # 语义匹配阈值
        self.fuzzy_threshold: float = 0.70       # 模糊匹配阈值
    
    def load_faqs(self) -> None:
        """加载FAQ数据并向量化所有问法变体"""
        ...
    
    def match(self, query: str) -> Dict:
        """匹配FAQ
        返回格式:
        {
            "matched": bool,          # 是否命中
            "confidence": float,      # 置信度
            "faq_id": str | None,     # FAQ ID
            "standard_answer": str | None,  # 标准答案
            "suggestions": List[Dict]  # 推荐的其他FAQ（模糊匹配时）
        }
        """
        ...
    
    def _embed_query(self, query: str) -> List[float]:
        """调用DashScope生成查询向量"""
        ...
    
    def _cosine_similarity(self, a, b) -> float:
        """余弦相似度计算"""
        ...
```

#### 3.3 新增API端点

在 `src/api_service.py` 中新增：

```python
@app.post("/api/cs/faq/search")
async def faq_search(request: FAQSearchRequest):
    """FAQ快速搜索（不经过RAG）"""
    ...
```

#### 3.4 FAQ管理后台（简易版）

在Streamlit的客服页面中，提供一个FAQ管理区域（可选，MVP后期加入）：
- 显示当前FAQ列表
- 支持搜索和预览

#### 3.5 产出物

| 文件 | 说明 |
|------|------|
| `src/cs/faq_engine.py` | FAQ匹配引擎 |

---

### T4：客服意图分类器

**目标**: 识别客户问题的意图类型，决定路由到FAQ/RAG/转人工等不同处理路径。

#### 4.1 客服意图分类体系

不同于财务分析的6类意图，客服场景使用以下分类：

```python
CUSTOMER_SERVICE_INTENTS = {
    "product_inquiry": "产品咨询",        # 产品功能、特性
    "pricing_inquiry": "价格咨询",        # 价格、优惠
    "order_status": "订单查询",          # 订单状态（MVP暂不支持实际操作）
    "after_sales": "售后服务",           # 退换货、保修
    "complaint": "投诉建议",             # 投诉、不满
    "account_issue": "账户问题",         # 登录、注册
    "human_service": "转人工",           # 明确要求人工
    "greeting": "问候寒暄",             # 你好、再见
    "out_of_scope": "超出范围",          # 不相关的问题
    "financial_analysis": "财务分析",    # 转发到财务分析模块
}
```

#### 4.2 技术方案

**设计原则**: 不修改 `src/query_processor.py`，新建客服专用查询处理器。

#### 4.3 新建文件：`src/cs/intent_router.py`

```python
class CustomerServiceIntentRouter:
    """客服意图分类与路由
    
    与现有 QueryProcessor 的区别：
    - 使用客服专用意图分类体系
    - 内置路由决策逻辑
    - 支持简单问题的快速响应（不经过LLM意图分类）
    """
    
    def __init__(self, api_key: str = None):
        self.model = "qwen-plus"
        self.api_key = api_key
        self.intent_prompt_template = CS_INTENT_PROMPT  # 客服专用Prompt
    
    def route(self, query: str, session: CustomerServiceSession) -> RouteDecision:
        """核心方法：意图识别 + 路由决策
        
        返回 RouteDecision:
        {
            "intent": str,              # 意图类别
            "confidence": float,        # 置信度
            "action": str,              
                # "faq_first"      - 先查FAQ再决定
                # "rag"            - 走RAG检索生成
                # "direct_reply"   - 直接回复（如问候语）
                # "transfer"       - 触发转人工
                # "delegate"       - 委托给财务分析模块
                # "reject"         - 拒绝回答
            "direct_message": str|None, # action=direct_reply时的直接回复
            "reasoning": str,           # 推理过程
        }
        """
        ...
    
    def _classify_intent(self, query: str, context: str) -> Dict:
        """LLM意图分类（客服专用Prompt）"""
        ...
    
    def _rule_based_precheck(self, query: str) -> Optional[Dict]:
        """规则前置检查：问候语、明确转人工等零Token场景"""
        ...
```

#### 4.4 客服意图分类Prompt模板（`CS_INTENT_PROMPT`）

```text
你是一个智能客服系统的意图分类器。请分析客户问题，输出JSON。

## 意图类别：
1. product_inquiry    - 咨询产品功能、特性、使用方式
2. pricing_inquiry    - 咨询价格、套餐、优惠活动
3. order_status       - 查订单状态、物流、修改订单
4. after_sales        - 退换货、保修、维修进度
5. complaint          - 投诉、表达不满、要求赔偿
6. account_issue      - 账号注册、登录、权限问题
7. human_service      - 明确要求转人工客服
8. greeting           - 问候、寒暄、无关闲聊
9. out_of_scope       - 与本公司业务完全无关
10. financial_analysis - 需要专业财务数据分析

## 输出格式：
{
    "intent": "类别名",
    "confidence": 0.0-1.0,
    "sub_intent": "更细粒度的意图",
    "key_entities": ["提取的关键实体"],
    "sentiment": "positive/neutral/negative",
    "reasoning": "推理过程"
}
```

#### 4.5 产出物

| 文件 | 说明 |
|------|------|
| `src/cs/intent_router.py` | 客服意图分类与路由 |

---

### T5：情感检测模块

**目标**: 检测客户对话中的情绪，用于触发安抚话术或转人工决策。

#### 5.1 技术方案

采用轻量级方案，不引入额外模型（MVP阶段）：

**方案一（推荐MVP用）**: 在意图分类的Prompt中附带情感检测（T4的Prompt已含 `sentiment` 字段），零额外成本。

**方案二（后续优化）**: 若需要更精细的情感分析，可接入独立的 `qwen-plus` 调用或本地规则。

#### 5.2 新建文件：`src/cs/sentiment.py`

```python
class SentimentDetector:
    """情感检测器
    
    MVP阶段：利用意图分类Prompt中的sentiment字段
    后续可扩展为独立的情感分析模型调用
    """
    
    # 负面情绪关键词（规则快速检测）
    NEGATIVE_PATTERNS = [
        "投诉", "差评", "退款", "骗", "坑", "垃圾",
        "太差", "烂", "失望", "愤怒", "气死", "坑爹",
        "什么破", "无语", "服了", "坑人",
    ]
    
    # 情绪升级关键词（触发转人工）
    ESCALATION_PATTERNS = [
        "投诉", "找你们领导", "曝光", "举报", "12315",
        "再也不用了", "退钱", "索赔",
    ]
    
    def detect_by_rules(self, text: str) -> Dict:
        """规则快速检测（零Token消耗）

        返回:
        {
            "sentiment": "negative"|"neutral",
            "should_escalate": bool,
            "matched_keywords": []
        }
        """
        ...
    
    def should_escalate(self, session: CustomerServiceSession) -> bool:
        """判断是否应该触发转人工
        
        触发条件：
        1. 当前消息包含升级关键词
        2. 连续3轮以上负面情绪
        """
        ...
    
    def generate_empathetic_response(self, base_response: str, 
                                      sentiment: str) -> str:
        """在回复中注入安抚话术"""
        ...
```

#### 5.3 产出物

| 文件 | 说明 |
|------|------|
| `src/cs/sentiment.py` | 情感检测器 |

---

### T6：客服检索与生成

**目标**: 基于客服知识库构建RAG检索和回答生成能力。

#### 6.1 技术方案

**核心思路**: 复用 `HybridRetriever` + `RAGGenerator` 的模式，但使用客服知识库和客服专用Prompt。

#### 6.2 新建文件：`src/cs/cs_retrieval.py`

```python
class CustomerServiceRetriever:
    """客服专用检索器
    
    封装 HybridRetriever，指向客服知识库路径
    去掉财务专用的公司名过滤、营收数据保底等逻辑
    """
    
    def __init__(self, kb_dir: str, api_key: str = None):
        self.kb_dir = kb_dir
        self.api_key = api_key
        self._retriever: Optional[HybridRetriever] = None
    
    def search(self, query: str, top_n: int = 5) -> List[Dict]:
        """检索客服知识库"""
        ...
```

#### 6.3 客服专用Prompt模板

不同于财务分析的5种意图Prompt，客服场景使用统一的客服回答Prompt：

```text
你是一位专业、友好的企业客服代表。

## 角色要求：
- 回答简洁明了，非必要不罗列长篇内容
- 语气友好热情，使用"您好""感谢咨询"等敬语
- 对产品功能咨询，给出准确的功能描述和使用方式
- 对价格咨询，给出明确的价格信息，不清楚时不编造
- 对售后问题，表达理解和关注，引导进入售后流程

## 参考知识：
{context}

## 对话历史：
{conversation_history}

## 当前问题：
{query}

## 回答：
```

#### 6.4 新增API端点

```python
@app.post("/api/cs/query")
async def cs_query(request: CustomerServiceQueryRequest):
    """客服RAG查询（完整流程：FAQ匹配 → 意图路由 → 检索 → 生成）"""
    ...
```

#### 6.5 产出物

| 文件 | 说明 |
|------|------|
| `src/cs/cs_retrieval.py` | 客服检索器 |
| `src/cs/cs_generator.py` | 客服回答生成器 |

---

### T7：转人工机制

**目标**: 当系统无法解决客户问题或检测到升级需求时，触发转人工流程。

#### 7.1 触发条件

| 触发条件 | 检测位置 | 优先级 |
|---------|---------|--------|
| 客户明确说"转人工""找人工客服""人工服务" | 意图分类 | 高 |
| 情绪升级（投诉、愤怒） | 情感检测 | 高 |
| RAG生成置信度低（LLM明确说不知道） | 生成后检查 | 中 |
| FAQ未命中 + RAG检索结果为空 | 检索后检查 | 中 |
| 同一问题追问超过3轮未解决 | 会话管理 | 低 |

#### 7.2 转人工流程（MVP简化版）

```text
触发转人工 → 设置会话状态为 TRANSFERRING
           → 生成转人工引导消息
           → 收集客户联系方式（可选）
           → 创建简易工单记录（写入JSON文件）
           → 返回确认消息给客户
```

#### 7.3 新建文件：`src/cs/human_handoff.py`

```python
class HumanHandoff:
    """转人工处理器（MVP简易版）"""
    
    def __init__(self, ticket_dir: str = "data/cs_tickets/"):
        self.ticket_dir = ticket_dir
    
    def should_transfer(self, session: CustomerServiceSession,
                         intent: str, sentiment: str,
                         retrieval_count: int) -> TransferDecision:
        """综合判断是否应该转人工"""
        ...
    
    def execute_transfer(self, session: CustomerServiceSession,
                          reason: str) -> Dict:
        """执行转人工流程
        
        返回:
        {
            "message": str,              # 给客户的回复
            "ticket_id": str,            # 工单ID
            "collected_info": Dict,      # 收集的信息
        }
        """
        ...
    
    def collect_customer_info(self, session: CustomerServiceSession) -> Dict:
        """收集客户联系方式（返回结构化表单提示）"""
        ...
```

#### 7.4 产出物

| 文件 | 说明 |
|------|------|
| `src/cs/human_handoff.py` | 转人工处理 |
| `data/cs_tickets/` | 工单存储目录 |

---

### T8：Streamlit UI整合

**目标**: 在现有Streamlit应用中新增客服标签页，与财务分析功能并存。

#### 8.1 页面布局设计

```text
┌─────────────────────────────────────────────┐
│  企业智能平台                                │
│  ┌──────────────┬──────────────────────────┐ │
│  │ 侧边栏       │                          │ │
│  │              │                          │ │
│  │ [模式选择]   │   右侧主区域              │ │
│  │  ○ 财务年报  │                          │ │
│  │  ○ 企业客服  │   ➤ 当前选中的功能界面   │ │
│  │              │                          │ │
│  │ [客服专区]   │                          │ │
│  │  - 会话列表  │                          │ │
│  │  - 新建会话  │                          │ │
│  │  - FAQ管理   │                          │ │
│  │              │                          │ │
│  └──────────────┴──────────────────────────┘ │
└─────────────────────────────────────────────┘
```

#### 8.2 修改文件：`app_streamlit.py`

**修改策略**：不修改现有财务分析的代码逻辑，在文件末尾追加客服页面渲染函数。

新增的函数：

```python
# ==================== 客服模块 ====================

def render_cs_sidebar():
    """渲染客服侧边栏"""
    ...

def render_cs_chat():
    """渲染客服聊天界面"""
    ...

def cs_send_message(query: str, session_id: str):
    """发送客服消息（调用 /api/cs/query）"""
    ...

def cs_create_new_session():
    """创建新客服会话"""
    ...

def run_customer_service_mode():
    """客服模式主入口"""
    ...

# ==================== 主入口修改 ====================
def main():
    st.title("企业智能平台")
    
    # 模式选择
    mode = st.sidebar.radio(
        "选择模式",
        ["财务年报分析", "企业智能客服"],  # 新增选项
    )
    
    if mode == "财务年报分析":
        run_financial_analysis_mode()  # 现有逻辑，不改动
    elif mode == "企业智能客服":
        run_customer_service_mode()    # 新增
```

#### 8.3 客服聊天界面特性

- 消息气泡样式区分用户/客服
- 显示FAQ匹配状态（"FAQ快速回答" vs "AI生成回答"）
- 转人工提示卡片
- 会话切换/新建按钮
- 简易FAQ预览面板（可折叠）

#### 8.4 产出物

**修改文件**:
| 文件 | 修改内容 |
|------|---------|
| `app_streamlit.py` | 新增客服模式渲染函数 |

---

### T9：端到端联调与测试

**目标**: 确保整个客服链路顺畅运行，与财务分析功能互不干扰。

#### 9.1 测试用例清单

##### 场景A：FAQ快速匹配

| 编号 | 输入 | 预期输出 |
|------|------|---------|
| A1 | "产品A有哪些功能？" | FAQ命中 → 直接返回标准答案 |
| A2 | "你们A产品能做什么？" | FAQ命中（语义变体匹配） |
| A3 | "今天天气怎么样？" | FAQ未命中 → 检测为 out_of_scope → 礼貌拒答 |

##### 场景B：多轮对话

| 编号 | 输入序列 | 预期行为 |
|------|---------|---------|
| B1-1 | "你们有产品B吗？" | RAG回答产品B介绍 |
| B1-2 | "价格呢？" | 关联上文的产品B，回答价格信息 |
| B1-3 | "和产品A比呢？" | 能关联产品A和产品B进行对比 |

##### 场景C：情绪检测与转人工

| 编号 | 输入 | 预期行为 |
|------|------|---------|
| C1 | "你们这个太烂了，我要投诉" | 检测到负面情绪 → 安抚话术 + 触发转人工 |
| C2 | "转人工" | 直接触发转人工流程 |
| C3 | "好的谢谢" | 正常结束，不触发转人工 |

##### 场景D：与财务分析隔离

| 编号 | 操作 | 预期行为 |
|------|------|---------|
| D1 | 切换到财务分析模式 | 原有功能完全正常 |
| D2 | 客服模式问"中芯国际年报" | 识别为financial_analysis意图 → 提示切换模式或委托处理 |
| D3 | 财务模式问"产品价格" | 财务模式正常拒答（保持不变） |

##### 场景E：边界情况

| 编号 | 输入 | 预期行为 |
|------|------|---------|
| E1 | 超长输入（5000字） | 截断处理后正常回答 |
| E2 | 空输入 | 提示请输入问题 |
| E3 | 纯表情/特殊字符 | 礼貌引导客户提供文字描述 |
| E4 | 连续10轮对话 | 历史截断正常，不丢失关键上下文 |

#### 9.2 性能测试

| 指标 | 目标值 | 说明 |
|------|--------|------|
| FAQ匹配响应 | < 1秒 | 含向量化和相似度计算 |
| RAG检索响应 | < 3秒 | 含检索+重排+生成 |
| 首次Token生成 | < 2秒 | LLM开始输出时间 |
| 并发会话数 | 10+ | Streamlit本地测试 |

#### 9.3 产出物

| 文件 | 说明 |
|------|------|
| `tests/test_cs_session.py` | 客服会话管理单元测试 |
| `tests/test_cs_faq.py` | FAQ匹配引擎单元测试 |
| `tests/test_cs_intent.py` | 意图路由单元测试 |
| `tests/test_cs_sentiment.py` | 情感检测单元测试 |
| `tests/test_cs_e2e.py` | 端到端集成测试 |

---

### T10：试运行与反馈收集

**目标**: 在小范围内试运行，收集真实反馈后迭代。

#### 10.1 试运行计划

| 阶段 | 范围 | 时长 | 目标 |
|------|------|------|------|
| 内测 | 开发团队 + 1-2名业务同事 | 3-5天 | 发现明显Bug和体验问题 |
| 小范围 | 内部社群（5-10人） | 1周 | 收集真实使用反馈 |
| 总结 | 整理反馈报告 | 1天 | 产出改进清单 |

#### 10.2 反馈收集机制

在Streamlit页面底部增加简单的反馈组件：
- 每条回复下方：  [有用] [没用]
- 会话结束：星级评分（1-5星）+ 文字反馈
- 反馈数据存入 `data/cs_feedback/` 目录

#### 10.3 反馈分析维度

| 维度 | 关注指标 |
|------|---------|
| FAQ覆盖率 | FAQ命中率、未命中高频问题 |
| 回答质量 | 有用率、无用率、用户修正率 |
| 转人工率 | 触发转人工的比例及原因分布 |
| 用户满意度 | 星级评分分布 |

---

## 三、文件变更清单总览

### 新建文件

```
src/cs/                          # 客服模块（新目录）
├── __init__.py                  # 模块入口
├── cs_session.py                # T2: 客服会话管理
├── faq_engine.py                # T3: FAQ匹配引擎
├── intent_router.py             # T4: 客服意图分类与路由
├── sentiment.py                 # T5: 情感检测器
├── cs_retrieval.py              # T6: 客服知识库检索
├── cs_generator.py              # T6: 客服回答生成器
└── human_handoff.py             # T7: 转人工机制

data/customer_service_kb/        # 客服知识库（新目录）
├── faq.json                     # T1: FAQ数据
├── product_docs/                # T1: 产品文档
│   ├── 产品A介绍.md
│   └── ...
├── databases/                   # T1: 向量索引
└── subset.csv                   # T1: 元数据

data/cs_tickets/                 # T7: 工单存储

tests/
├── test_cs_session.py           # T9: 会话测试
├── test_cs_faq.py               # T9: FAQ测试
├── test_cs_intent.py            # T9: 意图测试
├── test_cs_sentiment.py         # T9: 情感测试
└── test_cs_e2e.py               # T9: 端到端测试
```

### 修改文件

| 文件 | 修改内容 | 影响范围 |
|------|---------|---------|
| `app_streamlit.py` | 新增客服模式渲染函数 + 模式切换 | 仅追加代码，不修改现有逻辑 |
| `src/api_service.py` | 新增客服相关API端点 + `CustomerServiceSessionStore` | 追加新端点和类 |
| `src/ingestion.py` | 新增 `build_customer_service_index()` | 追加方法 |

### 不修改的文件（零影响）

- `src/retrieval.py` - 保持不变（客服检索器通过封装复用，不侵入）
- `src/query_processor.py` - 保持不变
- `src/conversation.py` - 保持不变
- `src/agent_memory.py` - 保持不变
- `src/agent_core.py` - 保持不变
- `src/tools/*` - 保持不变
- 所有现有测试文件 - 保持不变

---

## 四、依赖关系与执行顺序

```text
T1(知识库准备) ─────────────────────────────┐
                                            │
T2(会话管理) ─────────────────────────────  ├── T8(UI整合) ── T9(联调测试) ── T10(试运行)
                                            │
T3(FAQ引擎) ────── 依赖 T1 ────────────────┐│
                                           ││
T4(意图路由) ──────────────────────────────┤│
                                           ││
T5(情感检测) ──────────────────────────────┤│
                                           ││
T6(检索生成) ────── 依赖 T1 ───────────────┤│
                                           ││
T7(转人工) ──────── 依赖 T4, T5 ───────────┘┘
```

**并行执行策略**：
- T1、T2、T4、T5 可并行开发（无相互依赖）
- T3 和 T6 需等 T1 完成
- T7 需等 T4、T5 完成
- T8 需等 T2-T7 全部完成
- T9 需等 T8 完成

**推荐执行顺序（2人并行）**：
- 第1天：开发者A做 T1+T3，开发者B做 T2+T4+T5
- 第2-3天：开发者A做 T6+T7，开发者B做 T8
- 第4-5天：两人共同做 T9

---

## 五、风险提示

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| FAQ向量化与现有ChromaDB版本冲突 | T3阻塞 | 使用独立目录隔离，不共享索引 |
| LLM意图分类延迟过高（>3秒） | T4体验差 | 规则前置快速路由，减少LLM调用场景 |
| Streamlit不支持多标签页 | T8方案需调整 | 使用radio切换代替tab切换 |
| 客服Prompt不够好导致回答质量低 | T6体验差 | 预留Prompt迭代空间，收集反馈后快速调整 |
| 内存中存储大量会话导致OOM | 系统稳定性 | ConversationStore上限控制 + LRU淘汰 |

---

*本文档为MVP阶段实施规划，各任务的具体实现代码将在开发阶段逐一完成。*
