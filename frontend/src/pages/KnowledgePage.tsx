// -*- coding: utf-8 -*-
/**
 * 知识库管理页面
 * Phase 3 实现: PDF 文档列表、上传、删除、索引状态
 */

import { useState, useEffect } from 'react';
import {
  Alert,
  Button,
  Card,
  Empty,
  Modal,
  Progress,
  Table,
  Tag,
  Upload,
  message,
} from 'antd';
import { InboxOutlined, DeleteOutlined } from '@ant-design/icons';
import { getDocuments, uploadDocument, deleteDocument }
    from '@/services/knowledgeService';
import type { KnowledgeDocument } from '@/types/chat';
import type { ColumnsType } from 'antd/es/table';
import { PageHeader, PageShell } from '@/components/common/PageShell';
import KnowledgeOverview from '@/components/knowledge/KnowledgeOverview';
import { DatabaseOutlined } from '@ant-design/icons';

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
    } catch (err) {
      console.error('[KnowledgePage] 获取文档列表失败:', err);
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
    } catch (err) {
      console.error('[KnowledgePage] 上传失败:', file.name, err);
      message.error(`上传失败: ${file.name}`);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
    return false;
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
        } catch (err) {
          console.error('[KnowledgePage] 删除失败:', filename, err);
          message.error('删除失败');
        }
      },
    });
  };

  const columns: ColumnsType<KnowledgeDocument> = [
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
      onFilter: (value, record: KnowledgeDocument) =>
          record.indexed === Boolean(value),
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
    <PageShell>
      <PageHeader
        eyebrow="研究资料"
        title="资料库"
        icon={<DatabaseOutlined />}
        description="上传财务年报，并查看当前资料的索引可用状态"
      />

      <section className="knowledge-archive" aria-label="证据资产工作区">
      <div className="knowledge-archive__heading">
        <span>证据资产</span>
        <p>已接入资料会在完成索引后用于回答核验与来源定位</p>
      </div>

      <KnowledgeOverview documents={documents} />

      <Card
        className="page-card page-toolbar"
        title="上传资料"
        extra="仅支持 PDF，最大 50MB"
        style={{ marginBottom: 24 }}
      >
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
      </Card>

      {error ? (
        <Alert
          type="warning"
          message="服务不可用"
          description={error}
          showIcon
        />
      ) : (
        <Card className="page-card knowledge-archive__list" title={`资料清单（${documents.length}）`}>
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
        </Card>
      )}
      </section>
    </PageShell>
  );
}
