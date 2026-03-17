import React, { useEffect, useState } from 'react';
import {
  Button,
  Card,
  Form,
  InputNumber,
  Space,
  Switch,
  message,
} from 'antd';
import { SettingOutlined } from '@ant-design/icons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateAppConfig } from '../../services/endpoints/settingsApi';
import { useAppConfigQuery } from '../../services/queries/settingsQueries';

export default function AppConfigTab() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const appConfigQuery = useAppConfigQuery();
  const [loading, setLoading] = useState(false);
  const updateAppMutation = useMutation({
    mutationFn: updateAppConfig,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['settings', 'app-config'] });
    },
  });

  useEffect(() => {
    if (appConfigQuery.data) {
      form.setFieldsValue(appConfigQuery.data);
    }
  }, [appConfigQuery.data, form]);

  const handleSave = async (values) => {
    setLoading(true);
    try {
      await updateAppMutation.mutateAsync(values);
      message.success('应用配置已保存，立即生效');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      title={(
        <Space>
          <SettingOutlined />
          应用配置
        </Space>
      )}
      style={{ maxWidth: 500 }}
      loading={appConfigQuery.isPending}
    >
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
        <Button type="primary" htmlType="submit" loading={loading}>
          保存配置
        </Button>
      </Form>
    </Card>
  );
}
