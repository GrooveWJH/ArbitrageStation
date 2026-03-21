import React, { useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  message,
} from 'antd';
import {
  DisconnectOutlined,
  DeleteOutlined,
  EditOutlined,
  GlobalOutlined,
  LinkOutlined,
  PlusOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import {
  addExchange,
  deleteExchange,
  updateExchange,
} from '../../services/endpoints/exchangesApi';
import {
  useSettingsExchangesQuery,
  useSupportedExchangesQuery,
} from '../../services/queries/settingsQueries';
import { getApiErrorMessage } from '../../utils/error';

export default function ExchangeTab() {
  const exchangesQuery = useSettingsExchangesQuery();
  const supportedExchangesQuery = useSupportedExchangesQuery();
  const exchanges = exchangesQuery.data || [];
  const supported = supportedExchangesQuery.data || [];
  const [modalOpen, setModalOpen] = useState(false);
  const [editingEx, setEditingEx] = useState(null);
  const [form] = Form.useForm();

  const refetchAll = async () => {
    await Promise.all([exchangesQuery.refetch(), supportedExchangesQuery.refetch()]);
  };

  const openCreate = () => {
    setEditingEx(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (ex) => {
    setEditingEx(ex);
    form.setFieldsValue({ ...ex, api_key: '', api_secret: '' });
    setModalOpen(true);
  };

  const handleSave = async (values) => {
    try {
      if (editingEx) {
        const payload = { ...values };
        ['api_key', 'api_secret', 'passphrase'].forEach((k) => {
          if (payload[k] === '' || payload[k] == null) delete payload[k];
        });
        await updateExchange(editingEx.id, payload);
        message.success('交易所已更新');
      } else {
        await addExchange(values);
        message.success('交易所已添加');
      }
      setModalOpen(false);
      await refetchAll();
    } catch (e) {
      message.error(getApiErrorMessage(e));
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteExchange(id);
      message.success('已删除');
      await refetchAll();
    } catch (e) {
      message.error(getApiErrorMessage(e));
    }
  };

  const handleToggle = async (ex, active) => {
    try {
      await updateExchange(ex.id, { is_active: active });
      await refetchAll();
    } catch (e) {
      message.error(getApiErrorMessage(e));
    }
  };

  const formatExchangeId = (ex) => {
    const raw = String(ex.id ?? ex.name ?? '').toUpperCase();
    if (!raw) return 'UNKNOWN';
    if (raw.length <= 10) return raw;
    return `${raw.slice(0, 4)}...${raw.slice(-3)}`;
  };

  const getLatencyLabel = (ex) => {
    const latency = ex.latency_ms ?? ex.last_latency_ms ?? ex.ws_latency_ms ?? ex.ping_ms;
    if (latency == null || Number.isNaN(Number(latency))) return '---';
    return `${Number(latency).toFixed(0)}ms`;
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: '交易所',
      dataIndex: 'display_name',
      render: (v, r) => (
        <Space>
          {v}
          <Tag>{r.name}</Tag>
        </Space>
      ),
    },
    {
      title: 'API Key',
      dataIndex: 'has_api_key',
      render: (v) => <Tag color={v ? 'green' : 'default'}>{v ? '已配置' : '未配置'}</Tag>,
    },
    {
      title: '账户模式',
      dataIndex: 'is_unified_account',
      render: (v) => (v ? <Tag color="blue">统一账户</Tag> : <Tag>分账户</Tag>),
    },
    {
      title: '测试网',
      dataIndex: 'is_testnet',
      render: (v) => (v ? <Tag color="orange">测试网</Tag> : '-'),
    },
    {
      title: '启用',
      dataIndex: 'is_active',
      render: (v, r) => <Switch checked={v} onChange={(en) => handleToggle(r, en)} size="small" />,
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, r) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>
            编辑
          </Button>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      className="kinetic-settings-card"
      title={(
        <Space>
          <GlobalOutlined />
          交易所管理
        </Space>
      )}
      extra={(
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          添加交易所
        </Button>
      )}
    >
      <section className="kinetic-exchange-connectivity">
        <div className="connectivity-head">
          <h4>
            <GlobalOutlined />
            交易所 API 连通性
          </h4>
        </div>

        <div className="connectivity-list">
          {exchanges.map((ex) => {
            const connected = Boolean(ex.is_active && ex.has_api_key);
            const shortName = (ex.display_name || ex.name || 'EX').slice(0, 3).toUpperCase();
            return (
              <div className={`connectivity-row ${connected ? 'is-connected' : 'is-disconnected'}`} key={`connectivity-${ex.id}`}>
                <div className="connectivity-main">
                  <div className="exchange-mark">{shortName}</div>
                  <div>
                    <div className="exchange-title">{(ex.display_name || ex.name || 'Unnamed').toUpperCase()}</div>
                    <div className="exchange-meta">
                      <span>ID: {formatExchangeId(ex)}</span>
                      <span className="dot" />
                      <span className={`status ${connected ? 'ok' : 'error'}`}>
                        <span className="pulse" />
                        {connected ? '已连接' : '未连接'}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="connectivity-actions">
                  <div className="latency">
                    <div>延迟</div>
                    <strong>{getLatencyLabel(ex)}</strong>
                  </div>
                  <Button size="small" icon={<SettingOutlined />} onClick={() => openEdit(ex)} />
                  <Button
                    size="small"
                    type={connected ? 'default' : 'primary'}
                    danger={connected}
                    icon={connected ? <DisconnectOutlined /> : <LinkOutlined />}
                    onClick={() => { void handleToggle(ex, !connected); }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <Table
        dataSource={exchanges}
        columns={columns}
        rowKey="id"
        size="small"
        pagination={false}
        loading={exchangesQuery.isPending || exchangesQuery.isFetching}
      />

      <Modal
        className="kinetic-settings-modal"
        title={editingEx ? '编辑交易所' : '添加交易所'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={520}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          {!editingEx && (
            <Form.Item name="name" label="交易所" rules={[{ required: true }]}>
              <Select
                showSearch
                placeholder="搜索交易所..."
                options={supported.map((s) => ({ label: `${s.name} (${s.id})`, value: s.id }))}
                filterOption={(input, option) => String(option?.label || '').toLowerCase().includes(input.toLowerCase())}
              />
            </Form.Item>
          )}
          <Form.Item name="display_name" label="显示名称">
            <Input placeholder="可自定义显示名称" />
          </Form.Item>
          <Form.Item name="api_key" label="API Key">
            <Input placeholder={editingEx ? '留空则不更新' : ''} />
          </Form.Item>
          <Form.Item name="api_secret" label="API Secret">
            <Input.Password placeholder={editingEx ? '留空则不更新' : ''} />
          </Form.Item>
          <Form.Item name="passphrase" label="Passphrase (OKX等需要)">
            <Input.Password />
          </Form.Item>
          <Form.Item name="is_unified_account" label="统一账户模式" valuePropName="checked">
            <Switch checkedChildren="统一" unCheckedChildren="分账户" />
          </Form.Item>
          <Form.Item name="is_testnet" label="使用测试网" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            保存
          </Button>
        </Form>
      </Modal>
    </Card>
  );
}
