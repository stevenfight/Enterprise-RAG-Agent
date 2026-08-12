# Phase 3 详细代码实现方案

> 编码: UTF-8 | 日期: 2026-08-09 | 变更: modern-ui Phase 3
> 修订: v1.2 (修复 3 致命问题 + 2 设计缺陷 + Spin/import 细节)

---

## 审查记录

| # | 问题 | 严重性 | 修复 |
|---|------|:--:|------|
| 1 | SettingsPage 的 Slider/Switch/Select 只存在 localStorage，从未传给后端 API，属于"假功能" | 致命 | 改为只读监控面板，去掉所有交互控件 |
| 2 | SettingsPage 每次 onMount 从后端覆盖用户 localStorage | 致命 | 去掉 localStorage 逻辑，直接读 status 渲染 |
| 3 | `_load_agent_config()` key 名称错误（`agent_model` 应为 `model`）且重复读取 YAML | 致命 | 修正 key，复用模块级变量 |
| 4 | 上传无文件大小限制，可被撑爆磁盘 | 设计缺陷 | 加 50MB 上限 |
| 5 | 删除 PDF 不清理向量索引 | 设计缺陷 | 已知限制，留待后续处理 |

---

## 文件变更清单

| # | 文件 | 操作 | 行数估算 |
|---|------|:--:|:--:|
| 1 | `src/knowledge_service.py` | 新建 | ~120 |
| 2 | `src/api_service.py` | 修改(新增路由+模型) | +70 |
| 3 | `frontend/src/services/knowledgeService.ts` | 新建 | ~50 |
| 4 | `frontend/src/services/systemService.ts` | 新建 | ~30 |
| 5 | `frontend/src/pages/KnowledgePage.tsx` | 重写 | ~200 |
| 6 | `frontend/src/pages/SettingsPage.tsx` | 重写 | ~160 |
| 7 | `frontend/src/App.tsx` | 修改(React.lazy) | +25 |
| 8 | `frontend/src/styles/responsive.css` | 新建 | ~40 |
| 9 | `frontend/src/types/chat.ts` | 修改(新增类型) | +30 |
| 10 | `frontend/src/main.tsx` | 修改(追加 CSS 导入) | +1 |

---

## 一、后端: src/knowledge_service.py (新建)

```python
# -*- coding: utf-8 -*-
"""
知识库管理模块

提供 PDF 文档的列表、上传、删除功能。
数据源: data/stock_data/pdf_reports/ (PDF 文件)
索引状态对照: data/stock_data/databases/vector_dbs/ (已索引的公司目录)

已知限制:
- 删除 PDF 不会清理对应的向量索引数据，需手动重建索引
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import List

logger = logging.getLogger("knowledge_service")

# 路径常量
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PDF_DIR = _PROJECT_ROOT / "data" / "stock_data" / "pdf_reports"
_VECTOR_DB_DIR = _PROJECT_ROOT / "data" / "stock_data" / "databases" / "vector_dbs"

# 上传限制: 50MB
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


def get_documents() -> List[dict]:
    """获取所有 PDF 文档列表，含索引状态"""
    _PDF_DIR.mkdir(parents=True, exist_ok=True)

    # 获取已索引的公司名（vector_dbs 下的子目录）
    indexed_companies = set()
    if _VECTOR_DB_DIR.exists():
        for d in _VECTOR_DB_DIR.iterdir():
            if d.is_dir():
                indexed_companies.add(d.name)

    documents = []
    for pdf_file in sorted(_PDF_DIR.glob("*.pdf"),
                           key=lambda f: f.stat().st_mtime, reverse=True):
        stat = pdf_file.stat()
        filename = pdf_file.name

        # 判断索引状态：文件名包含已索引的公司名
        indexed = any(company in filename for company in indexed_companies)

        documents.append({
            "filename": filename,
            "size": stat.st_size,
            "size_mb": round(stat.st_size / 1024 / 1024, 2),
            "upload_time": datetime.fromtimestamp(stat.st_mtime)
                .strftime("%Y-%m-%d %H:%M:%S"),
            "indexed": indexed,
        })

    return documents


def upload_pdf(file_content: bytes, filename: str) -> dict:
    """上传 PDF 文件

    Raises:
        ValueError: 文件非 PDF 或超过大小限制
    """
    # 安全检查：只允许 .pdf
    if not filename.lower().endswith(".pdf"):
        raise ValueError("仅支持 PDF 文件")

    # 文件大小限制
    if len(file_content) > MAX_UPLOAD_SIZE:
        size_mb = round(len(file_content) / 1024 / 1024, 2)
        raise ValueError(
            f"文件过大 ({size_mb} MB)，最大允许 50 MB")

    _PDF_DIR.mkdir(parents=True, exist_ok=True)

    # 防止路径遍历攻击
    safe_name = Path(filename).name
    dest_path = _PDF_DIR / safe_name

    with open(dest_path, "wb") as f:
        f.write(file_content)

    logger.info("[knowledge] PDF 上传成功: %s (%d bytes)",
                 safe_name, len(file_content))

    return {
        "filename": safe_name,
        "size": len(file_content),
        "size_mb": round(len(file_content) / 1024 / 1024, 2),
    }


def delete_pdf(filename: str) -> bool:
    """删除 PDF 文件（不清理对应的向量索引数据）"""
    filepath = _PDF_DIR / filename
    if not filepath.exists():
        return False

    filepath.unlink()
    logger.info("[knowledge] PDF 已删除: %s", filename)
    return True
```

---

## 二、后端: src/api_service.py (新增 Pydantic 模型 + 路由)

### 2.1 新增 Pydantic 模型

插入位置: 现有 QueryRequest / QueryResponse 等模型定义区域之后

```python
class KnowledgeDocument(BaseModel):
    """知识库文档信息"""
    filename: str
    size: int
    size_mb: float
    upload_time: str
    indexed: bool


class KnowledgeListResponse(BaseModel):
    """知识库文档列表响应"""
    documents: list = []
    total: int = 0


class KnowledgeUploadResponse(BaseModel):
    """上传响应"""
    success: bool = True
    filename: str = ""
    size: int = 0
    size_mb: float = 0.0


class SystemStatusResponse(BaseModel):
    """系统状态响应"""
    model: dict = {}
    vector_db: dict = {}
    memory: dict = {}
    monitoring: dict = {}
    tools: dict = {}
```

### 2.2 新增路由

追加位置: 文件末尾

```python
# ==================== 知识库管理 & 系统状态 API ====================

from .knowledge_service import get_documents, upload_pdf, delete_pdf

@app.get("/api/knowledge/documents",
         response_model=KnowledgeListResponse,
         summary="获取知识库文档列表")
async def api_knowledge_documents():
    """返回 PDF 文档列表，包含索引状态"""
    logger.info("[api_service] 收到 /api/knowledge/documents 请求")
    docs = get_documents()
    return {"documents": docs, "total": len(docs)}


@app.post("/api/knowledge/upload",
          response_model=KnowledgeUploadResponse,
          summary="上传 PDF 文档")
async def api_knowledge_upload(request: Request):
    """上传 PDF 文件到知识库（最大 50MB）"""
    logger.info("[api_service] 收到 /api/knowledge/upload 请求")
    try:
        # 粗略大小检查（在读取文件内容之前）
        content_length = request.headers.get("content-length")
        if content_length:
            cl = int(content_length)
            if cl > 50 * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail="文件过大，最大允许 50 MB")

        form = await request.form()
        file = form.get("file")
        if file is None:
            raise HTTPException(status_code=400, detail="缺少文件")
        content = await file.read()
        filename = file.filename or "unnamed.pdf"
        result = upload_pdf(content, filename)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/knowledge/documents/{filename}",
            summary="删除 PDF 文档")
async def api_knowledge_delete(filename: str):
    """删除指定的 PDF 文档"""
    logger.info("[api_service] 收到 DELETE /api/knowledge/documents/%s",
                 filename)
    from urllib.parse import unquote
    filename = unquote(filename)
    if not delete_pdf(filename):
        raise HTTPException(status_code=404,
                            detail=f"文档不存在: {filename}")
    return {"success": True, "filename": filename}


@app.get("/api/system/status",
         response_model=SystemStatusResponse,
         summary="获取系统状态")
async def api_system_status():
    """返回系统运行状态（只读监控数据）"""
    from .monitoring import (LANGSMITH_ENABLED, LANGSMITH_PROJECT,
                              LANGSMITH_ENDPOINT)

    # 复用已有的模块级变量，避免重复读取 YAML
    global rag_generator, vector_db_dir

    # --- 模型状态 ---
    agent_cfg = _load_agent_config()
    model_status = {
        "name": agent_cfg.get("model", "qwen-max"),
        "status": "loaded" if rag_generator is not None else "not_loaded",
        "temperature": agent_cfg.get("temperature", 0.3),
        "max_steps": agent_cfg.get("max_steps", 5),
    }

    # --- 向量数据库状态 ---
    vb_counts = 0
    if vector_db_dir.exists():
        vb_counts = sum(1 for d in vector_db_dir.iterdir() if d.is_dir())
    vector_db_status = {
        "path": str(vector_db_dir),
        "status": "available" if vector_db_dir.exists() else "unavailable",
        "company_count": vb_counts,
    }

    # --- 长期记忆状态 ---
    memory_status = {
        "long_term_enabled":
            agent_cfg.get("memory_enable_long_term", False),
        "working_memory_limit":
            agent_cfg.get("memory_working_memory_limit", 10),
    }

    # --- LangSmith 监控状态 ---
    monitoring_status = {
        "langsmith_available": LANGSMITH_ENABLED,
        "langsmith_project": LANGSMITH_PROJECT,
        "langsmith_endpoint": LANGSMITH_ENDPOINT,
    }

    # --- 工具列表（当前全部启用，只读） ---
    tools_status = {
        "retrieve": True,
        "calculator": True,
        "compare": True,
        "chart": True,
        "verify": True,
        "delegate": True,
    }

    return {
        "model": model_status,
        "vector_db": vector_db_status,
        "memory": memory_status,
        "monitoring": monitoring_status,
        "tools": tools_status,
    }
```

### 2.3 依赖验证

以上代码依赖的模块级变量/函数均已在 `api_service.py` 中存在:

| 引用 | 定义位置 | 状态 |
|------|------|:--:|
| `Request` | 第 24 行 `from fastapi import FastAPI, HTTPException, Request` | 已存在 |
| `rag_generator` | 第 60 行 `rag_generator: Optional[RAGGenerator] = None` | 已存在 |
| `vector_db_dir` | 第 58 行 `vector_db_dir = project_root / ...` | 已存在 |
| `_load_agent_config()` | 第 136 行 | 已存在 |
| `project_root` | 第 57 行 | 已存在 |
| `.monitoring` | 未导入 (run-time import) | 首次导入, 按需 |

### 2.4 鉴权说明

`/api/knowledge/*` 和 `/api/system/status` 走现有 `APIAuthMiddleware`，需携带 `Authorization: Bearer <key>`。前端 `apiClient` 已配置 `no-key-needed`，不受影响。

---

## 三、前端: src/services/knowledgeService.ts (新建)

```typescript
// -*- coding: utf-8 -*-
/**
 * 知识库管理 API 封装
 */

import apiClient from './api';
import type { KnowledgeDocument } from '@/types/chat';

export interface KnowledgeListData {
  documents: KnowledgeDocument[];
  total: number;
}

export interface UploadResult {
  success: boolean;
  filename: string;
  size: number;
  size_mb: number;
}

/** 获取文档列表 */
export async function getDocuments(): Promise<KnowledgeListData> {
  const res = await apiClient.get<KnowledgeListData>(
      '/api/knowledge/documents');
  return res.data;
}

/** 上传 PDF */
export async function uploadDocument(
    file: File,
    onProgress?: (pct: number) => void,
): Promise<UploadResult> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await apiClient.post<UploadResult>(
      '/api/knowledge/upload', formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (e.total) {
            onProgress?.(Math.round((e.loaded * 100) / e.total));
          }
        },
      },
  );
  return res.data;
}

/** 删除文档 */
export async function deleteDocument(
    filename: string,
): Promise<{ success: boolean }> {
  const res = await apiClient.delete(
      `/api/knowledge/documents/${encodeURIComponent(filename)}`);
  return res.data;
}
```

---

## 四、前端: src/services/systemService.ts (新建)

```typescript
// -*- coding: utf-8 -*-
/**
 * 系统状态 API 封装
 */

import apiClient from './api';
import type { SystemStatusData } from '@/types/chat';

/** 获取系统状态 */
export async function getSystemStatus(): Promise<SystemStatusData> {
  const res = await apiClient.get<SystemStatusData>('/api/system/status');
  return res.data;
}
```

---

## 五、前端: 重写 src/pages/KnowledgePage.tsx

核心组件设计:

```
┌──────────────────────────────────────┐
│  知识库管理                            │
│  ┌──────────────────────────────────┐ │
│  │  [上传 PDF] 拖拽或点击上传         │ │
│  └──────────────────────────────────┘ │
│  ┌──────────────────────────────────┐ │
│  │ 文件名      大小   上传时间  索引  操作│ │
│  │ 中国移动_2024.pdf 2.3M 08-01 ●已索引 [删]│ │
│  │ 中国联通_2024.pdf 1.8M 08-05 ●已索引 [删]│ │
│  │ 测试.pdf    3.1M 08-09 ○未索引  [删]│ │
│  └──────────────────────────────────┘ │
└──────────────────────────────────────┘
```

组件结构:
- `antd Table` -- 文档列表（分页、排序）
- `antd Upload.Dragger` -- PDF 拖拽上传，仅允许 `.pdf`
- `antd Progress` -- 上传进度条
- `antd Modal.confirm` -- 删除二次确认
- 空状态 `antd Empty` / 错误降级 `antd Alert`

```tsx
// -*- coding: utf-8 -*-
/**
 * 知识库管理页面
 * Phase 3 实现: PDF 文档列表、上传、删除、索引状态
 */

import { useState, useEffect } from 'react';
import {
  Typography, Table, Button, Tag, Progress,
  Modal, message, Empty, Alert, Upload,
} from 'antd';
import { InboxOutlined, DeleteOutlined } from '@ant-design/icons';
import { getDocuments, uploadDocument, deleteDocument }
    from '@/services/knowledgeService';
import type { KnowledgeDocument } from '@/types/chat';

const { Title } = Typography;
const { Dragger } = Upload;

export default function KnowledgePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDocuments();
      setDocuments(data.documents);
    } catch {
      setError('知识库服务暂不可用，请检查后端是否启动');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      message.error('仅支持 PDF 文件');
      return false;
    }
    setUploading(true);
    setUploadProgress(0);
    try {
      await uploadDocument(file, setUploadProgress);
      message.success(`上传成功: ${file.name}`);
      fetchDocuments();
    } catch {
      message.error(`上传失败: ${file.name}`);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
    return false; // 阻止 Upload 组件自动上传
  };

  const handleDelete = (filename: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除 "${filename}" 吗？此操作不可恢复。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteDocument(filename);
          message.success('已删除');
          fetchDocuments();
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  const columns = [
    {
      title: '文件名', dataIndex: 'filename', key: 'filename',
      ellipsis: true, sorter: (a: KnowledgeDocument, b: KnowledgeDocument) =>
          a.filename.localeCompare(b.filename),
    },
    {
      title: '大小', dataIndex: 'size_mb', key: 'size_mb',
      width: 100,
      render: (v: number) => `${v} MB`,
      sorter: (a: KnowledgeDocument, b: KnowledgeDocument) =>
          a.size - b.size,
    },
    {
      title: '上传时间', dataIndex: 'upload_time', key: 'upload_time',
      width: 170,
      sorter: (a: KnowledgeDocument, b: KnowledgeDocument) =>
          a.upload_time.localeCompare(b.upload_time),
    },
    {
      title: '索引状态', dataIndex: 'indexed', key: 'indexed',
      width: 110,
      filters: [
        { text: '已索引', value: true },
        { text: '未索引', value: false },
      ],
      onFilter: (value: boolean, record: KnowledgeDocument) =>
          record.indexed === value,
      render: (v: boolean) => v
          ? <Tag color="green">已索引</Tag>
          : <Tag color="gold">未索引</Tag>,
    },
    {
      title: '操作', key: 'action', width: 80,
      render: (_: unknown, record: KnowledgeDocument) => (
        <Button
          danger icon={<DeleteOutlined />}
          size="small"
          onClick={() => handleDelete(record.filename)}
        />
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>知识库管理</Title>

      <div style={{ marginBottom: 24 }}>
        <Dragger
          accept=".pdf"
          maxCount={1}
          showUploadList={false}
          beforeUpload={(file) => {
            handleUpload(file as File);
            return false;
          }}
          disabled={uploading}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">
            点击或拖拽 PDF 文件到此区域上传
          </p>
          <p className="ant-upload-hint">
            仅支持 .pdf 格式，最大 50MB
          </p>
        </Dragger>
        {uploading && (
          <Progress
            percent={uploadProgress}
            style={{ marginTop: 12 }}
          />
        )}
      </div>

      {error ? (
        <Alert
          type="warning"
          message="服务不可用"
          description={error}
          showIcon
        />
      ) : (
        <Table
          columns={columns}
          dataSource={documents}
          rowKey="filename"
          loading={loading}
          pagination={{
            pageSize: 10,
            showTotal: (t) => `共 ${t} 篇`,
          }}
          locale={{
            emptyText: <Empty description="暂无文档" />,
          }}
        />
      )}
    </div>
  );
}
```

---

## 六、前端: 重写 src/pages/SettingsPage.tsx (v2: 只读监控面板)

**修正说明**:
- 去掉所有交互控件 (Slider, InputNumber, Select, Switch)
- 去掉 localStorage 持久化逻辑
- 改为 3 个只读卡片: Agent 当前配置 / 系统健康 / 工具列表

```
┌──────────────────────────────────────┐
│  系统设置（只读监控）                      │
│                                      │
│  Agent 当前配置                        │
│  ┌──────────────────────────────────┐ │
│  │ 模型: qwen-max   已加载            │ │
│  │ Temperature: 0.3                  │ │
│  │ Max Steps: 5                      │ │
│  └──────────────────────────────────┘ │
│                                      │
│  系统健康                              │
│  ┌──────────────────────────────────┐ │
│  │ 模型状态    ● 已加载               │ │
│  │ 向量数据库  ● 可用 (4 家公司)        │ │
│  │ 长期记忆    ● 已启用               │ │
│  │ LangSmith   ○ 未启用              │ │
│  └──────────────────────────────────┘ │
│                                      │
│  已注册工具                             │
│  ┌──────────────────────────────────┐ │
│  │ ● 检索 (retrieve)                 │ │
│  │ ● 计算 (calculator)               │ │
│  │ ● 对比 (compare)                  │ │
│  │ ● 图表 (chart)                    │ │
│  │ ● 验证 (verify)                   │ │
│  │ ● 委派 (delegate)                 │ │
│  └──────────────────────────────────┘ │
└──────────────────────────────────────┘
```

```tsx
// -*- coding: utf-8 -*-
/**
 * 系统设置页面（只读监控面板）
 * Phase 3 实现: 展示服务端运行状态，不做本地修改
 */

import { useState, useEffect } from 'react';
import {
  Typography, Card, Tag, Descriptions, Space, Spin,
} from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { getSystemStatus } from '@/services/systemService';
import type { SystemStatusData } from '@/types/chat';

const { Title, Text } = Typography;

const TOOL_LABELS: Record<string, string> = {
  retrieve: '检索',
  calculator: '计算',
  compare: '对比',
  chart: '图表',
  verify: '验证',
  delegate: '委派',
};

export default function SettingsPage() {
  const [status, setStatus] = useState<SystemStatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await getSystemStatus();
        setStatus(data);
      } catch {
        setError('无法连接后端服务');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div style={{
        display: 'flex', justifyContent: 'center',
        alignItems: 'center', minHeight: 300,
      }}>
        <Spin size="large" />
    </div>
  );
}

if (error) {
    return (
      <div style={{ padding: 24 }}>
        <Title level={3}>系统设置</Title>
        <Card>
          <Text type="danger">
            <ExclamationCircleOutlined style={{ marginRight: 8 }} />
            {error}
          </Text>
        </Card>
      </div>
    );
  }

  if (!status) return null;

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>系统设置</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        当前运行状态（只读监控，修改配置请编辑 config/agent_config.json）
      </Text>

      <Space direction="vertical"
             style={{ width: '100%' }} size="middle">

        {/* ===== Agent 当前配置 ===== */}
        <Card title="Agent 当前配置">
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="模型">
              <Tag color="blue">{status.model.name}</Tag>
              <Tag color={
                  status.model.status === 'loaded' ? 'green' : 'red'}
                   style={{ marginLeft: 8 }}>
                {status.model.status === 'loaded'
                    ? '已加载' : '未加载'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Temperature">
              {status.model.temperature}
            </Descriptions.Item>
            <Descriptions.Item label="Max Steps">
              {status.model.max_steps} 步
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* ===== 系统健康 ===== */}
        <Card title="系统健康">
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="模型状态">
              <Tag color={
                  status.model.status === 'loaded' ? 'green' : 'red'}>
                {status.model.status === 'loaded'
                    ? <CheckCircleOutlined />
                    : <CloseCircleOutlined />}
                {' '}{status.model.status === 'loaded'
                    ? '已加载' : '未加载'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="向量数据库">
              <Tag color={
                  status.vector_db.status === 'available'
                      ? 'green' : 'red'}>
                {status.vector_db.status === 'available'
                    ? <CheckCircleOutlined />
                    : <CloseCircleOutlined />}
                {' '}{status.vector_db.status === 'available'
                    ? `可用 (${status.vector_db.company_count} 家公司)`
                    : '不可用'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="长期记忆">
              <Tag color={
                  status.memory.long_term_enabled ? 'green' : 'default'}>
                {status.memory.long_term_enabled
                    ? '已启用' : '未启用'}
              </Tag>
              {status.memory.long_term_enabled && (
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  容量: {status.memory.working_memory_limit} 条
                </Text>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="LangSmith">
              <Tag color={
                  status.monitoring.langsmith_available
                      ? 'green' : 'default'}>
                {status.monitoring.langsmith_available
                    ? '已启用' : '未启用'}
              </Tag>
              {status.monitoring.langsmith_available && (
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  {status.monitoring.langsmith_project}
                </Text>
              )}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* ===== 已注册工具 ===== */}
        <Card title="已注册工具">
          <Descriptions column={1} bordered size="small">
            {Object.entries(TOOL_LABELS).map(([key, label]) => (
              <Descriptions.Item key={key} label={label}>
                <Tag color={status.tools[key] ? 'green' : 'red'}>
                  {status.tools[key] ? '已启用' : '已禁用'}
                </Tag>
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  ({key})
                </Text>
              </Descriptions.Item>
            ))}
          </Descriptions>
        </Card>
      </Space>
    </div>
  );
}
```

---

## 七、前端: 修改 src/App.tsx (React.lazy 代码分割)

将非首页路由改为 `React.lazy` + `<Suspense>`:

```tsx
import React, { Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Spin, Result, Button } from 'antd';
import AppLayout from '@/components/layout/AppLayout';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import ChatPage from '@/pages/ChatPage';

// 非首页路由懒加载
const DagBoardPage = React.lazy(() => import('@/pages/DagBoardPage'));
const ChartsPage = React.lazy(() => import('@/pages/ChartsPage'));
const KnowledgePage = React.lazy(() => import('@/pages/KnowledgePage'));
const SettingsPage = React.lazy(() => import('@/pages/SettingsPage'));

/** Suspense fallback 组件 */
function LazyFallback() {
  return (
    <div style={{
      display: 'flex', justifyContent: 'center',
      alignItems: 'center', minHeight: 300,
    }}>
      <Spin size="large" />
    </div>
  );
}

function NotFoundPage() {
  return (
    <Result
      status="404" title="404"
      subTitle="抱歉，您访问的页面不存在"
      extra={<Button type="primary" href="/">返回首页</Button>}
    />
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<ChatPage />} />
            <Route path="/dag" element={
              <Suspense fallback={<LazyFallback />}>
                <DagBoardPage />
              </Suspense>} />
            <Route path="/charts" element={
              <Suspense fallback={<LazyFallback />}>
                <ChartsPage />
              </Suspense>} />
            <Route path="/knowledge" element={
              <Suspense fallback={<LazyFallback />}>
                <KnowledgePage />
              </Suspense>} />
            <Route path="/settings" element={
              <Suspense fallback={<LazyFallback />}>
                <SettingsPage />
              </Suspense>} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
```

---

## 八、前端: src/styles/responsive.css (新建)

```css
/* -*- coding: utf-8 -*- */
/**
 * 响应式适配样式
 * 移动端断点: 768px
 */

@media (max-width: 768px) {
  .ant-layout-sider {
    position: fixed !important;
    z-index: 1000;
    height: 100vh;
  }

  .ant-table {
    overflow-x: auto;
  }

  .ant-card {
    margin-bottom: 12px !important;
  }

  .ant-upload-drag {
    min-height: 120px !important;
  }
}
```

在 `frontend/src/main.tsx` 中与 `global.css` 同行导入:

```tsx
// main.tsx 第 9-10 行
import './styles/global.css';
import './styles/responsive.css';   // Phase 3 新增
```

> 注意: 不可在 `global.css` 中用 `@import` 导入，因为 CSS 规范要求 `@import` 必须在文件最顶部（所有规则之前），而 `global.css` 第 7 行已开始写规则。

---

## 九、前端: src/types/chat.ts (新增类型定义)

在文件末尾追加:

```typescript
/** 知识库文档 */
export interface KnowledgeDocument {
  filename: string;
  size: number;
  size_mb: number;
  upload_time: string;
  indexed: boolean;
}

/** 系统状态 */
export interface SystemStatusData {
  model: {
    name: string;
    status: string;
    temperature: number;
    max_steps: number;
  };
  vector_db: {
    path: string;
    status: string;
    company_count: number;
  };
  memory: {
    long_term_enabled: boolean;
    working_memory_limit: number;
  };
  monitoring: {
    langsmith_available: boolean;
    langsmith_project: string;
    langsmith_endpoint: string;
  };
  tools: Record<string, boolean>;
}
```

---

## 十、TDD 标绿 (tasks 3.9)

Phase 3 共需验证并标绿 16 条用例（12 条功能 + 4 条 UAT）:

### TC-FE-011: 知识库管理 (6 条)
| 编号 | 用例 | 验证方式 |
|------|------|------|
| TC-FE-011-01 | 文档列表展示（列: 文件名/大小/上传时间/索引状态/操作） | 浏览器打开 /knowledge, 检查表格列 |
| TC-FE-011-02 | 拖拽/点击上传 PDF | 选择 PDF 文件, 检查列表刷新 |
| TC-FE-011-03 | 非 PDF 拦截 | 上传 .txt, 检查 toast "仅支持 PDF" |
| TC-FE-011-04 | 删除确认对话框 | 点击删除按钮, 检查 Modal 弹出, 取消后不执行 |
| TC-FE-011-05 | 上传进度条显示 | 上传大文件, 检查 Progress 组件 |
| TC-FE-011-06 | 空列表展示 Empty | 清空 PDF 后检查 Empty 组件 |

### TC-FE-012: 系统设置页 (3 条)
| 编号 | 用例 | 验证方式 |
|------|------|------|
| TC-FE-012-01 | Agent 配置只读展示（模型/Temperature/MaxSteps） | 打开 /settings, 检查 Descriptions |
| TC-FE-012-02 | 系统健康面板（模型/向量库/记忆/LangSmith 状态） | 检查 Descriptions 中的 Tag 颜色 |
| TC-FE-012-03 | 已注册工具列表 | 检查工具列表 Descriptions |

### TC-FE-013: 生产就绪 (3 条)
| 编号 | 用例 | 验证方式 |
|------|------|------|
| TC-FE-013-01 | 响应式布局: 移动端侧边栏 fixed | 浏览器调为 768px 宽度, 检查侧边栏 |
| TC-FE-013-02 | 代码分割: 非首页路由 lazyload | 打开 DevTools Network 标签, 访问 /knowledge 检查独立 chunk |
| TC-FE-013-03 | 前端构建零 fail | 执行 `npx vite build` |

### TC-FE-UAT: 用户验收 (4 条)
| 编号 | 用例 | 验证方式 |
|------|------|------|
| TC-FE-UAT-01 | 亮/暗主题切换 | 点击侧边栏底部月亮图标 |
| TC-FE-UAT-02 | 全 5 个页面可访问 | 逐一访问 /, /dag, /charts, /knowledge, /settings |
| TC-FE-UAT-03 | 知识库 CRUD 完整流程 | 上传 → 列表 → 删除 全流程 |
| TC-FE-UAT-04 | 并发操作不崩溃 | 打开 2 个 Tab 分别操作 /charts 和 /knowledge |

验证方法: 启动前后端后浏览器手动验证，通过后更新 `tdd-frontend-ui.md` 中对应行标绿。
