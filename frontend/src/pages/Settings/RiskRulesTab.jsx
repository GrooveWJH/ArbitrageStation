import React, { useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
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
  PlusOutlined,
  SafetyOutlined,
} from '@ant-design/icons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  createRiskRule,
  deleteRiskRule,
  updateRiskRule,
} from '../../services/endpoints/settingsApi';
import { useRiskRulesQuery } from '../../services/queries/settingsQueries';
import { getApiErrorMessage } from '../../utils/error';
import { ACTION_OPTIONS, RULE_TYPE_OPTIONS } from './constants';

export default function RiskRulesTab() {
  const queryClient = useQueryClient();
  const riskRulesQuery = useRiskRulesQuery();
  const rules = riskRulesQuery.data || [];
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [form] = Form.useForm();
  const createRuleMutation = useMutation({
    mutationFn: createRiskRule,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['settings', 'risk-rules'] });
    },
  });
  const updateRuleMutation = useMutation({
    mutationFn: ({ id, payload }) => updateRiskRule(id, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['settings', 'risk-rules'] });
    },
  });
  const deleteRuleMutation = useMutation({
    mutationFn: deleteRiskRule,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['settings', 'risk-rules'] });
    },
  });

  const openCreate = () => {
    setEditingRule(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (rule) => {
    setEditingRule(rule);
    form.setFieldsValue(rule);
    setModalOpen(true);
  };

  const handleSave = async (values) => {
    try {
      if (editingRule) {
        await updateRuleMutation.mutateAsync({ id: editingRule.id, payload: values });
        message.success('规则已更新');
      } else {
        await createRuleMutation.mutateAsync(values);
        message.success('规则已创建');
      }
      setModalOpen(false);
    } catch (e) {
      message.error(`操作失败: ${getApiErrorMessage(e)}`);
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteRuleMutation.mutateAsync(id);
      message.success('规则已删除');
    } catch (e) {
      message.error(`删除失败: ${getApiErrorMessage(e)}`);
    }
  };

  const handleToggle = async (rule, enabled) => {
    try {
      await updateRuleMutation.mutateAsync({ id: rule.id, payload: { is_enabled: enabled } });
    } catch (e) {
      message.error(`更新失败: ${getApiErrorMessage(e)}`);
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: '规则名称',
      dataIndex: 'name',
      render: (v, r) => (
        <Space>
          <span style={{ fontWeight: 600 }}>{v}</span>
          {!r.is_enabled && <Tag color="default">已禁用</Tag>}
        </Space>
      ),
    },
    {
      title: '触发类型',
      dataIndex: 'rule_type',
      render: (v) => RULE_TYPE_OPTIONS.find((o) => o.value === v)?.label || v,
    },
    {
      title: '阈值',
      dataIndex: 'threshold',
      render: (v, r) => {
        const suffix = r.rule_type === 'loss_pct' ? '%' : r.rule_type === 'max_leverage' ? 'x' : ' USDT';
        return (
          <Tag color="orange">
            {v}
            {suffix}
          </Tag>
        );
      },
    },
    {
      title: '触发动作',
      dataIndex: 'action',
      render: (v) => (
        <Tag color={v === 'close_position' ? 'red' : 'blue'}>
          {ACTION_OPTIONS.find((o) => o.value === v)?.label || v}
        </Tag>
      ),
    },
    {
      title: '发邮件',
      dataIndex: 'send_email',
      render: (v) => <Tag color={v ? 'green' : 'default'}>{v ? '是' : '否'}</Tag>,
    },
    {
      title: '启用',
      dataIndex: 'is_enabled',
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
          <SafetyOutlined />
          风控规则管理
        </Space>
      )}
      extra={(
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增规则
        </Button>
      )}
    >
      <Alert
        message="风控规则说明"
        description="每条规则独立运行。「亏损百分比」规则中，设置80表示亏损≥80%时触发；「立即平仓」会同时平掉该策略的所有仓位（含对冲仓）。"
        type="info"
        showIcon
        closable
        style={{ marginBottom: 16 }}
      />
      <Table
        dataSource={rules}
        columns={columns}
        rowKey="id"
        size="small"
        pagination={false}
        loading={
          riskRulesQuery.isPending
          || riskRulesQuery.isFetching
          || createRuleMutation.isPending
          || updateRuleMutation.isPending
          || deleteRuleMutation.isPending
        }
      />

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
              <Form.Item name="send_email" label="发邮件通知" valuePropName="checked" initialValue>
                <Switch />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="is_enabled" label="启用" valuePropName="checked" initialValue>
                <Switch />
              </Form.Item>
            </Col>
          </Row>
          <Button type="primary" htmlType="submit" block>
            保存规则
          </Button>
        </Form>
      </Modal>
    </Card>
  );
}
