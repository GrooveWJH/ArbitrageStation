import React, { useEffect, useState } from 'react';
import {
  Tabs, Card, Table, Button, Space, Modal, Form, Input, InputNumber, Select,
  Switch, Popconfirm, message, Row, Col, Divider, Tag, Tooltip, Alert
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, EditOutlined, MailOutlined,
  SafetyOutlined, SettingOutlined, GlobalOutlined, SendOutlined,
} from '@ant-design/icons';
import {
  getRiskRules, createRiskRule, updateRiskRule, deleteRiskRule,
  getEmailConfig, updateEmailConfig, testEmail,
  getAppConfig, updateAppConfig,
  getExchanges, getSupportedExchanges, addExchange, updateExchange, deleteExchange,
} from '../../services/api';

const RULE_TYPE_OPTIONS = [
  { label: '亏损百分比触发 (%)', value: 'loss_pct' },
  { label: '单仓最大金额 (USDT)', value: 'max_position_usd' },
  { label: '总敞口上限 (USDT)', value: 'max_exposure_usd' },
  { label: '最小费率差要求 (%)', value: 'min_rate_diff' },
  { label: '最大杠杆倍数', value: 'max_leverage' },
];

const ACTION_OPTIONS = [
  { label: '立即平仓', value: 'close_position' },
  { label: '仅告警不平仓', value: 'alert_only' },
];

// ─── Risk Rules Tab ───────────────────────────────────────────────────────────
function RiskRulesTab() {
  const [rules, setRules] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [form] = Form.useForm();

  const load = async () => {
    const { data } = await getRiskRules();
    setRules(data);
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => { setEditingRule(null); form.resetFields(); setModalOpen(true); };
  const openEdit = (rule) => {
    setEditingRule(rule);
    form.setFieldsValue(rule);
    setModalOpen(true);
  };

  const handleSave = async (values) => {
    try {
      if (editingRule) {
        await updateRiskRule(editingRule.id, values);
        message.success('规则已更新');
      } else {
        await createRiskRule(values);
        message.success('规则已创建');
      }
      setModalOpen(false);
      load();
    } catch (e) {
      message.error('操作失败: ' + e.message);
    }
  };

  const handleDelete = async (id) => {
    await deleteRiskRule(id);
    message.success('规则已删除');
    load();
  };

  const handleToggle = async (rule, enabled) => {
    await updateRiskRule(rule.id, { is_enabled: enabled });
    load();
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '规则名称', dataIndex: 'name', render: (v, r) => (
      <Space>
        <span style={{ fontWeight: 600 }}>{v}</span>
        {!r.is_enabled && <Tag color="default">已禁用</Tag>}
      </Space>
    )},
    { title: '触发类型', dataIndex: 'rule_type',
      render: v => RULE_TYPE_OPTIONS.find(o => o.value === v)?.label || v },
    { title: '阈值', dataIndex: 'threshold',
      render: (v, r) => {
        const suffix = r.rule_type === 'loss_pct' ? '%'
          : r.rule_type === 'max_leverage' ? 'x' : ' USDT';
        return <Tag color="orange">{v}{suffix}</Tag>;
      }
    },
    { title: '触发动作', dataIndex: 'action',
      render: v => <Tag color={v === 'close_position' ? 'red' : 'blue'}>
        {ACTION_OPTIONS.find(o => o.value === v)?.label || v}
      </Tag>
    },
    { title: '发邮件', dataIndex: 'send_email', render: v => <Tag color={v ? 'green' : 'default'}>{v ? '是' : '否'}</Tag> },
    { title: '启用', dataIndex: 'is_enabled',
      render: (v, r) => <Switch checked={v} onChange={en => handleToggle(r, en)} size="small" /> },
    { title: '操作', key: 'action', width: 120,
      render: (_, r) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    },
  ];

  return (
    <Card
      title={<Space><SafetyOutlined />风控规则管理</Space>}
      extra={<Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增规则</Button>}
    >
      <Alert
        message="风控规则说明"
        description='每条规则独立运行。「亏损百分比」规则中，设置80表示亏损≥80%时触发；「立即平仓」会同时平掉该策略的所有仓位（含对冲仓）。'
        type="info" showIcon closable style={{ marginBottom: 16 }}
      />
      <Table dataSource={rules} columns={columns} rowKey="id" size="small" pagination={false} />

      <Modal
        title={editingRule ? '编辑风控规则' : '新增风控规则'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={520}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="name" label="规则名称" rules={[{ required: true }]}>
            <Input placeholder="如：强制止损 80%" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="可选，描述此规则的用途" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="rule_type" label="触发类型" rules={[{ required: true }]}>
                <Select options={RULE_TYPE_OPTIONS} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="threshold" label="阈值" rules={[{ required: true }]}>
                <InputNumber style={{ width: '100%' }} min={0} step={0.1} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="action" label="触发动作" rules={[{ required: true }]} initialValue="close_position">
                <Select options={ACTION_OPTIONS} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="send_email" label="发邮件通知" valuePropName="checked" initialValue={true}>
                <Switch />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="is_enabled" label="启用" valuePropName="checked" initialValue={true}>
                <Switch />
              </Form.Item>
            </Col>
          </Row>
          <Button type="primary" htmlType="submit" block>保存规则</Button>
        </Form>
      </Modal>
    </Card>
  );
}

// ─── Email Config Tab ─────────────────────────────────────────────────────────
function EmailTab() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    getEmailConfig().then(({ data }) => form.setFieldsValue(data));
  }, []);

  const handleSave = async (values) => {
    setLoading(true);
    try {
      await updateEmailConfig(values);
      message.success('邮件配置已保存');
    } finally { setLoading(false); }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const { data } = await testEmail();
      message.success(data.message);
    } catch (e) {
      message.error('测试失败: ' + e.message);
    } finally { setTesting(false); }
  };

  return (
    <Card title={<Space><MailOutlined />邮件通知配置</Space>}>
      <Form form={form} layout="vertical" onFinish={handleSave} style={{ maxWidth: 600 }}>
        <Row gutter={16}>
          <Col span={16}>
            <Form.Item name="smtp_host" label="SMTP 服务器" rules={[{ required: true }]}>
              <Input placeholder="smtp.gmail.com / smtp.qq.com" />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="smtp_port" label="端口" rules={[{ required: true }]}>
              <InputNumber style={{ width: '100%' }} placeholder="587" />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="smtp_user" label="SMTP 用户名" rules={[{ required: true }]}>
              <Input placeholder="your@email.com" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="smtp_password" label="SMTP 密码 / 授权码" rules={[{ required: true }]}>
              <Input.Password placeholder="授权码（非登录密码）" />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item name="from_email" label="发件人地址">
          <Input placeholder="your@email.com" />
        </Form.Item>
        <Form.Item name="to_emails" label="收件人地址（多个用逗号分隔）" rules={[{ required: true }]}>
          <Input placeholder="user1@email.com, user2@email.com" />
        </Form.Item>
        <Form.Item name="is_enabled" label="启用邮件通知" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Space>
          <Button type="primary" htmlType="submit" loading={loading}>保存配置</Button>
          <Button icon={<SendOutlined />} onClick={handleTest} loading={testing}>发送测试邮件</Button>
        </Space>
      </Form>
    </Card>
  );
}

// ─── Exchange Config Tab ──────────────────────────────────────────────────────
function ExchangeTab() {
  const [exchanges, setExchanges] = useState([]);
  const [supported, setSupported] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingEx, setEditingEx] = useState(null);
  const [form] = Form.useForm();

  const load = async () => {
    const [e, s] = await Promise.all([getExchanges(), getSupportedExchanges()]);
    setExchanges(e.data);
    setSupported(s.data);
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => { setEditingEx(null); form.resetFields(); setModalOpen(true); };
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
          if (payload[k] === '' || payload[k] === null || payload[k] === undefined) {
            delete payload[k];
          }
        });
        await updateExchange(editingEx.id, payload);
        message.success('交易所已更新');
      } else {
        await addExchange(values);
        message.success('交易所已添加');
      }
      setModalOpen(false);
      load();
    } catch (e) {
      message.error(e.response?.data?.detail || e.message);
    }
  };

  const handleDelete = async (id) => {
    await deleteExchange(id);
    message.success('已删除');
    load();
  };

  const handleToggle = async (ex, active) => {
    await updateExchange(ex.id, { is_active: active });
    load();
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '交易所', dataIndex: 'display_name', render: (v, r) => <Space>{v}<Tag>{r.name}</Tag></Space> },
    { title: 'API Key', dataIndex: 'has_api_key', render: v => <Tag color={v ? 'green' : 'default'}>{v ? '已配置' : '未配置'}</Tag> },
    { title: '账户模式', dataIndex: 'is_unified_account', render: v => v ? <Tag color="blue">统一账户</Tag> : <Tag>分账户</Tag> },
    { title: '测试网', dataIndex: 'is_testnet', render: v => v ? <Tag color="orange">测试网</Tag> : '-' },
    { title: '启用', dataIndex: 'is_active',
      render: (v, r) => <Switch checked={v} onChange={en => handleToggle(r, en)} size="small" /> },
    { title: '操作', key: 'action', width: 120,
      render: (_, r) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    },
  ];

  return (
    <Card
      title={<Space><GlobalOutlined />交易所管理</Space>}
      extra={<Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>添加交易所</Button>}
    >
      <Table dataSource={exchanges} columns={columns} rowKey="id" size="small" pagination={false} />

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
                options={supported.map(s => ({ label: `${s.name} (${s.id})`, value: s.id }))}
                filterOption={(input, option) =>
                  option.label.toLowerCase().includes(input.toLowerCase())
                }
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
          <Button type="primary" htmlType="submit" block>保存</Button>
        </Form>
      </Modal>
    </Card>
  );
}

// ─── App Config Tab ───────────────────────────────────────────────────────────
function AppConfigTab() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getAppConfig().then(({ data }) => form.setFieldsValue(data));
  }, []);

  const handleSave = async (values) => {
    setLoading(true);
    try {
      await updateAppConfig(values);
      message.success('应用配置已保存，立即生效');
    } finally { setLoading(false); }
  };

  return (
    <Card title={<Space><SettingOutlined />应用配置</Space>} style={{ maxWidth: 500 }}>
      <Form form={form} layout="vertical" onFinish={handleSave}>
        <Form.Item name="auto_trade_enabled" label="自动交易（开启后将自动开仓最优套利机会）" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name="data_refresh_interval" label="数据刷新间隔（秒）">
          <InputNumber style={{ width: '100%' }} min={5} max={300} step={5} />
        </Form.Item>
        <Form.Item name="risk_check_interval" label="风控检查间隔（秒）">
          <InputNumber style={{ width: '100%' }} min={1} max={60} step={1} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={loading}>保存配置</Button>
      </Form>
    </Card>
  );
}

// ─── Main Settings Page ───────────────────────────────────────────────────────
export default function Settings() {
  const tabItems = [
    { key: 'risk',     label: <Space><SafetyOutlined />风控规则</Space>,   children: <RiskRulesTab /> },
    { key: 'exchange', label: <Space><GlobalOutlined />交易所管理</Space>,  children: <ExchangeTab /> },
    { key: 'email',    label: <Space><MailOutlined />邮件通知</Space>,      children: <EmailTab /> },
    { key: 'app',      label: <Space><SettingOutlined />应用配置</Space>,   children: <AppConfigTab /> },
  ];

  return <Tabs items={tabItems} defaultActiveKey="risk" />;
}
