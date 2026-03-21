import React, { useMemo, useState } from 'react';
import DevOverlay from '../../components/DevOverlay';
import { Button, Card, Space, Switch, Tag, message } from 'antd';
import {
  ApiOutlined,
  GlobalOutlined,
  MailOutlined,
  ReloadOutlined,
  SafetyOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useQueryClient } from '@tanstack/react-query';
import AppConfigTab from './AppConfigTab';
import EmailTab from './EmailTab';
import ExchangeTab from './ExchangeTab';
import RiskRulesTab from './RiskRulesTab';
import {
  useAppConfigQuery,
  useEmailConfigQuery,
  useRiskRulesQuery,
  useSettingsExchangesQuery,
} from '../../services/queries/settingsQueries';

const PANEL_ITEMS = [
  { key: 'risk', title: '风控规则', icon: <SafetyOutlined />, render: () => <RiskRulesTab /> },
  { key: 'exchange', title: '交易所 API', icon: <GlobalOutlined />, render: () => <ExchangeTab /> },
  { key: 'email', title: '通知配置', icon: <MailOutlined />, render: () => <EmailTab /> },
  { key: 'app', title: '应用配置', icon: <SettingOutlined />, render: () => <AppConfigTab /> },
];

export default function Settings() {
  const queryClient = useQueryClient();
  const [activeKey, setActiveKey] = useState('risk');

  const riskRulesQuery = useRiskRulesQuery();
  const exchangesQuery = useSettingsExchangesQuery();
  const emailQuery = useEmailConfigQuery();
  const appConfigQuery = useAppConfigQuery();

  const activeItem = useMemo(
    () => PANEL_ITEMS.find((item) => item.key === activeKey) || PANEL_ITEMS[0],
    [activeKey],
  );

  const riskRules = Array.isArray(riskRulesQuery.data) ? riskRulesQuery.data : [];
  const exchangeRows = Array.isArray(exchangesQuery.data) ? exchangesQuery.data : [];
  const enabledRiskRules = riskRules.filter((r) => r.is_enabled).length;
  const activeExchanges = exchangeRows.filter((ex) => ex.is_active).length;
  const emailEnabled = Boolean(emailQuery.data?.is_enabled);
  const autoTradeEnabled = Boolean(appConfigQuery.data?.auto_trade_enabled);

  const handleRefreshAll = async () => {
    await queryClient.invalidateQueries({ queryKey: ['settings'] });
    message.success('设置数据已刷新');
  };

  const remindSectionSave = () => {
    message.info('请在左侧当前模块内点击保存按钮提交变更。');
  };

  return (
    <div className="kinetic-page kinetic-settings">
      <div className="kinetic-settings-nav">
        {PANEL_ITEMS.map((item) => (
          <button
            key={item.key}
            type="button"
            className={activeKey === item.key ? 'active' : ''}
            onClick={() => setActiveKey(item.key)}
          >
            <Space size={6}>
              {item.icon}
              <span>{item.title}</span>
            </Space>
          </button>
        ))}
      </div>

      <div className="kinetic-settings-grid">
        <section className="kinetic-settings-main">
          {activeItem.render()}

          <DevOverlay>
          <div className="kinetic-settings-actionbar">
            <Button type="primary" onClick={remindSectionSave}>
              保存更改
            </Button>
            <Button onClick={handleRefreshAll} icon={<ReloadOutlined />}>
              重置并刷新
            </Button>
          </div>
          </DevOverlay>
        </section>

        <aside className="kinetic-settings-side">
          <Card className="kinetic-settings-card" title="告警与日志">
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>邮件报告</div>
              <div className="kinetic-mini-note">每日摘要与风险事件邮件推送</div>
            </div>
            <Switch checked={emailEnabled} disabled />
            <div style={{ height: 1, background: 'rgba(43,70,128,0.5)', margin: '14px 0' }} />
            <DevOverlay>
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>Telegram 机器人</div>
              <div className="kinetic-mini-note">实时交易告警链路（由通知配置接管）</div>
            </div>
            <Tag color={emailEnabled ? 'green' : 'default'}>
              {emailEnabled ? '通知已启用' : '通知未启用'}
            </Tag>
            </DevOverlay>
          </Card>

          <Card className="kinetic-settings-card" title="运行环境">
            <DevOverlay>
            <div style={{ marginBottom: 10 }}>
              <span className="kinetic-pill">
                <ApiOutlined />
                实例: KNTC-PRD-042
              </span>
            </div>
            </DevOverlay>
            <div className="kinetic-mini-note" style={{ marginBottom: 8 }}>
              当前执行环境与关键连接状态摘要。
            </div>
            <Space direction="vertical" size={8}>
              <Tag color={autoTradeEnabled ? 'green' : 'default'}>
                自动交易: {autoTradeEnabled ? '已启用' : '已禁用'}
              </Tag>
              <Tag color={activeExchanges > 0 ? 'blue' : 'default'}>
                交易所连接: {activeExchanges}/{exchangeRows.length}
              </Tag>
              <Tag color={enabledRiskRules > 0 ? 'orange' : 'default'}>
                风控规则: {enabledRiskRules}/{riskRules.length}
              </Tag>
            </Space>
          </Card>
        </aside>
      </div>
    </div>
  );
}
