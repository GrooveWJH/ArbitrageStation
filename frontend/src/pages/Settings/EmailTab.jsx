import React, { useEffect, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Space,
  Switch,
  message,
} from 'antd';
import { MailOutlined, SendOutlined } from '@ant-design/icons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  testEmail,
  updateEmailConfig,
} from '../../services/endpoints/settingsApi';
import { useEmailConfigQuery } from '../../services/queries/settingsQueries';
import { getApiErrorMessage } from '../../utils/error';

export default function EmailTab() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const emailConfigQuery = useEmailConfigQuery();
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const updateEmailMutation = useMutation({
    mutationFn: updateEmailConfig,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['settings', 'email-config'] });
    },
  });
  const testEmailMutation = useMutation({
    mutationFn: testEmail,
  });

  useEffect(() => {
    if (emailConfigQuery.data) {
      form.setFieldsValue(emailConfigQuery.data);
    }
  }, [emailConfigQuery.data, form]);

  const handleSave = async (values) => {
    setLoading(true);
    try {
      await updateEmailMutation.mutateAsync(values);
      message.success('邮件配置已保存');
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const { data } = await testEmailMutation.mutateAsync();
      message.success(data.message);
    } catch (e) {
      message.error(`测试失败: ${getApiErrorMessage(e)}`);
    } finally {
      setTesting(false);
    }
  };

  return (
    <Card
      className="kinetic-settings-card"
      title={(
        <Space>
          <MailOutlined />
          邮件通知配置
        </Space>
      )}
      loading={emailConfigQuery.isPending}
    >
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
          <Button type="primary" htmlType="submit" loading={loading}>
            保存配置
          </Button>
          <Button icon={<SendOutlined />} onClick={handleTest} loading={testing}>
            发送测试邮件
          </Button>
        </Space>
      </Form>
    </Card>
  );
}
