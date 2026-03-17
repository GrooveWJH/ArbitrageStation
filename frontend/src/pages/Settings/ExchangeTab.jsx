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
  DeleteOutlined,
  EditOutlined,
  GlobalOutlined,
  PlusOutlined,
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
      <Table
        dataSource={exchanges}
        columns={columns}
        rowKey="id"
        size="small"
        pagination={false}
        loading={exchangesQuery.isPending || exchangesQuery.isFetching}
      />

      <Modal
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
