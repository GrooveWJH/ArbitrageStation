import React, { useState } from 'react';
import { Layout, Menu, Badge, Typography } from 'antd';
import {
  DashboardOutlined,
  PercentageOutlined,
  FundOutlined,
  SettingOutlined,
  RobotOutlined,
  BarChartOutlined,
  SwapOutlined,
  RiseOutlined,
  LineChartOutlined,
} from '@ant-design/icons';

const { Header, Sider, Content } = Layout;
const { Title } = Typography;

const menuItems = [
  { key: 'dashboard', icon: <DashboardOutlined />, label: '总览看板' },
  { key: 'funding-rates', icon: <PercentageOutlined />, label: '资金费率' },
  { key: 'spread-monitor', icon: <SwapOutlined />, label: '价差监控' },
  { key: 'opportunities', icon: <RiseOutlined />, label: '价差机会' },
  { key: 'spread-arb', icon: <SwapOutlined />, label: '价差套利' },
  { key: 'positions', icon: <FundOutlined />, label: '策略/持仓' },
  { key: 'spot-basis-auto', icon: <RobotOutlined />, label: '自动现货-合约费率套利' },
  { key: 'spot-basis-backtest', icon: <LineChartOutlined />, label: '现货-合约回测' },
  { key: 'analytics', icon: <BarChartOutlined />, label: '收益分析' },
  { key: 'settings', icon: <SettingOutlined />, label: '系统设置' },
];

export default function AppLayout({ currentPage, onNavigate, children, alertCount = 0 }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        width={220}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '0 16px',
          }}
        >
          {!collapsed && (
            <Title level={5} style={{ color: '#fff', margin: 0, whiteSpace: 'nowrap' }}>
              费率套利工具
            </Title>
          )}
        </div>

        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[currentPage]}
          onClick={({ key }) => onNavigate(key)}
          items={menuItems.map((item) => ({
            ...item,
            label:
              item.key === 'positions' && alertCount > 0 ? (
                <Badge count={alertCount} offset={[8, 0]}>
                  {item.label}
                </Badge>
              ) : (
                item.label
              ),
          }))}
        />
      </Sider>

      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,21,41,.08)',
          }}
        >
          <Title level={4} style={{ margin: 0, color: '#1677ff' }}>
            {menuItems.find((m) => m.key === currentPage)?.label}
          </Title>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Badge status="processing" text="实时监控中" />
          </div>
        </Header>

        <Content style={{ margin: 24, background: '#f5f5f5', minHeight: 'calc(100vh - 112px)' }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
