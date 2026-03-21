import React, { useMemo } from 'react';
import DevOverlay from '../DevOverlay';
import { Badge, Input, Tooltip } from 'antd';
import {
  BarChartOutlined,
  BellOutlined,
  DashboardOutlined,
  FundOutlined,
  LineChartOutlined,
  PercentageOutlined,
  RadarChartOutlined,
  RobotOutlined,
  SearchOutlined,
  SettingOutlined,
  SwapOutlined,
  SyncOutlined,
  WalletOutlined,
} from '@ant-design/icons';

const MAIN_MENU = [
  { key: 'dashboard', icon: <DashboardOutlined />, label: '总览看板' },
  { key: 'funding-rates', icon: <PercentageOutlined />, label: '资金费率' },
  { key: 'spread-monitor', icon: <RadarChartOutlined />, label: '价差监控' },
  { key: 'opportunities', icon: <SwapOutlined />, label: '价差机会' },
  { key: 'spread-arb', icon: <SwapOutlined />, label: '价差套利' },
  { key: 'positions', icon: <FundOutlined />, label: '策略 / 持仓' },
  { key: 'analytics', icon: <BarChartOutlined />, label: '收益分析' },
];

const AUTO_MENU = [
  { key: 'spot-basis-auto', icon: <RobotOutlined />, label: '自动现货-合约套利' },
  { key: 'spot-basis-backtest', icon: <LineChartOutlined />, label: '现货-合约回测' },
  { key: 'settings', icon: <SettingOutlined />, label: '系统设置' },
];



function findPageLabel(currentPage) {
  const allItems = [...MAIN_MENU, ...AUTO_MENU];
  return allItems.find((item) => item.key === currentPage)?.label || '控制台';
}

function renderNavItems(items, currentPage, onNavigate, alertCount) {
  return items.map((item) => {
    const isActive = item.key === currentPage;
    const isPositions = item.key === 'positions' && alertCount > 0;
    return (
      <button
        key={item.key}
        type="button"
        className={`kinetic-nav-item ${isActive ? 'is-active' : ''}`}
        onClick={() => onNavigate(item.key)}
      >
        {item.icon}
        <span>{item.label}</span>
        {isPositions && <Badge count={alertCount} size="small" />}
      </button>
    );
  });
}

export default function AppLayout({
  currentPage,
  onNavigate,
  children,
  alertCount = 0,
  pageChrome,
}) {
  const fallbackTitle = useMemo(() => findPageLabel(currentPage), [currentPage]);
  const title = pageChrome?.title || fallbackTitle;
  const subtitle = pageChrome?.subtitle || '实时策略监控与执行控制';
  const badge = pageChrome?.badge || '控制台';
  const statusTone = pageChrome?.statusTone || 'idle';
  const statusText = pageChrome?.statusText || '等待数据';

  return (
    <div className="kinetic-shell">
      <aside className="kinetic-sidebar">
        <div className="kinetic-brand">
          <span className="kinetic-brand-mark">
            <RadarChartOutlined />
          </span>
          <div>
            <div className="kinetic-brand-title">ArbitrageStation</div>
            <div className="kinetic-brand-sub">v1.0.0</div>
          </div>
        </div>

        <div className="kinetic-nav-group">
          <div className="kinetic-nav-label">主控台</div>
          {renderNavItems(MAIN_MENU, currentPage, onNavigate, alertCount)}
        </div>

        <div className="kinetic-nav-group">
          <div className="kinetic-nav-label">自动化</div>
          {renderNavItems(AUTO_MENU, currentPage, onNavigate, alertCount)}
        </div>


      </aside>

      <section className="kinetic-main">
        <header className="kinetic-topbar">
          <div />
          <DevOverlay>
          <div className="kinetic-topbar-right">
            <Input
              className="kinetic-top-search"
              prefix={<SearchOutlined />}
              placeholder="搜索参数..."
            />
            <Tooltip title="钱包">
              <span className="kinetic-icon-btn"><WalletOutlined /></span>
            </Tooltip>
            <Tooltip title="同步">
              <span className="kinetic-icon-btn"><SyncOutlined /></span>
            </Tooltip>
            <Tooltip title="通知">
              <Badge dot offset={[-2, 2]}>
                <span className="kinetic-icon-btn"><BellOutlined /></span>
              </Badge>
            </Tooltip>
          </div>
          </DevOverlay>
        </header>

        <div className="kinetic-content">
          <section className="kinetic-page-header">
            <div className="kinetic-page-header-meta">
              <span className="kinetic-badge">{badge}</span>
              <span className={`kinetic-status-dot ${statusTone}`} />
              <span className="kinetic-status-text">{statusText}</span>
            </div>
            <h1 className="kinetic-page-title">{title}</h1>
            <div className="kinetic-page-subtitle">{subtitle}</div>
          </section>

          {pageChrome?.rightSlot ? (
            <div style={{ marginBottom: 16 }}>{pageChrome.rightSlot}</div>
          ) : null}

          {children}
        </div>
      </section>
    </div>
  );
}
