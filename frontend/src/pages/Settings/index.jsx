import React from 'react';
import { Tabs, Space } from 'antd';
import {
  GlobalOutlined,
  MailOutlined,
  SafetyOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import AppConfigTab from './AppConfigTab';
import EmailTab from './EmailTab';
import ExchangeTab from './ExchangeTab';
import RiskRulesTab from './RiskRulesTab';

export default function Settings() {
  const tabItems = [
    {
      key: 'risk',
      label: (
        <Space>
          <SafetyOutlined />
          风控规则
        </Space>
      ),
      children: <RiskRulesTab />,
    },
    {
      key: 'exchange',
      label: (
        <Space>
          <GlobalOutlined />
          交易所管理
        </Space>
      ),
      children: <ExchangeTab />,
    },
    {
      key: 'email',
      label: (
        <Space>
          <MailOutlined />
          邮件通知
        </Space>
      ),
      children: <EmailTab />,
    },
    {
      key: 'app',
      label: (
        <Space>
          <SettingOutlined />
          应用配置
        </Space>
      ),
      children: <AppConfigTab />,
    },
  ];

  return <Tabs items={tabItems} defaultActiveKey="risk" />;
}
