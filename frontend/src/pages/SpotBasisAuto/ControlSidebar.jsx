import React from 'react';
import {
  Button,
  Card,
  Col,
  Empty,
  InputNumber,
  Popconfirm,
  Row,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd';
import {
  ReloadOutlined,
  RobotOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import {
  AUTO_TERM_HELP,
  CFG_FIELD_META,
  CFG_SECTIONS,
  DEFAULT_CFG,
} from './configMeta';
import {
  cycleModeTag,
  cycleStatusColor,
  cycleStatusLabel,
  fmtIsoTime,
  fmtUsd,
  num,
  termLabel,
} from './helpers';

export default function ControlSidebar({
  cfg,
  savingStatus,
  setStatus,
  setCfg,
  drawdownWatermarkLoading,
  drawdownWatermark,
  drawdownWatermarkResetting,
  resetDrawdownWatermark,
  setCfgField,
  saveCfg,
  saving,
  runCycleOnce,
  cycleRunning,
  exchangeFundsLoading,
  refreshExchangeFunds,
  fundsSummary,
  exchangeFunds,
  exchangeFundsColumns,
  cycleLast,
  refreshCycleLogs,
  setCycleLogs,
  cycleLogs,
  cycleLogColumns,
  decisionLoading,
  decisionPreview,
}) {
  return (
    <Col span={8}>
      <Card title={<Space><RobotOutlined />{termLabel('自动策略控制', AUTO_TERM_HELP.auto_control)}</Space>} style={{ marginBottom: 12 }}>
        {!cfg ? (
          <Spin />
        ) : (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Row justify="space-between">
              {termLabel('启用自动策略', AUTO_TERM_HELP.is_enabled)}
              <Switch
                checked={!!cfg.is_enabled}
                loading={savingStatus}
                onChange={(v) => {
                  void setStatus(v, !!cfg.dry_run);
                }}
              />
            </Row>
            <Row justify="space-between">
              {termLabel('模拟模式', AUTO_TERM_HELP.dry_run)}
              <Switch
                checked={!!cfg.dry_run}
                loading={savingStatus}
                onChange={(v) => {
                  void setStatus(!!cfg.is_enabled, v);
                }}
              />
            </Row>
            <Row justify="space-between">
              {termLabel('敞口修复失败熔断', AUTO_TERM_HELP.circuit_breaker_on_repair_fail)}
              <Switch
                checked={!!cfg.circuit_breaker_on_repair_fail}
                onChange={(v) => setCfg((p) => ({ ...(p || DEFAULT_CFG), circuit_breaker_on_repair_fail: !!v }))}
              />
            </Row>
            <Typography.Text type="secondary">
              {termLabel('合约开仓执行', AUTO_TERM_HELP.contract_entry_execution)}: {termLabel('全仓模式', AUTO_TERM_HELP.cross_margin_mode)} / {termLabel('固定杠杆 2x', AUTO_TERM_HELP.fixed_leverage_2x)}
            </Typography.Text>
            <Typography.Text type="secondary">
              {termLabel('资金安全垫', AUTO_TERM_HELP.safety_cushion)} = max(下限, 手续费缓冲 + 滑点缓冲 + 保证金缓冲)
            </Typography.Text>
            <Typography.Text type="secondary">
              {termLabel('无敞口容忍', AUTO_TERM_HELP.unhedged_tolerance)} = max(绝对USDT阈值, NAV百分比阈值)
            </Typography.Text>

            <Card size="small" title={termLabel('组合回撤高水位', AUTO_TERM_HELP.drawdown_watermark)}>
              <Space direction="vertical" style={{ width: '100%' }} size={4}>
                {drawdownWatermarkLoading ? (
                  <Spin size="small" />
                ) : (
                  <>
                    <Typography.Text type="secondary">当前高水位: {fmtUsd(drawdownWatermark?.peak_nav_usdt, 2)}</Typography.Text>
                    <Typography.Text type="secondary">当前 NAV: {fmtUsd(drawdownWatermark?.current_nav_usdt, 2)}</Typography.Text>
                    <Typography.Text type="secondary">最近重置: {fmtIsoTime(drawdownWatermark?.drawdown_peak_reset_at)}</Typography.Text>
                  </>
                )}
                <Popconfirm
                  title="重置高水位"
                  description={`${AUTO_TERM_HELP.drawdown_reset_button} 确认继续？`}
                  okText="确认"
                  cancelText="取消"
                  onConfirm={() => {
                    void resetDrawdownWatermark();
                  }}
                  disabled={drawdownWatermarkResetting}
                >
                  <Button danger loading={drawdownWatermarkResetting} disabled={drawdownWatermarkLoading} block>
                    重置高水位
                  </Button>
                </Popconfirm>
              </Space>
            </Card>

            {CFG_SECTIONS.map((section) => (
              <Card key={section.title} size="small" title={termLabel(section.title, AUTO_TERM_HELP[section.title])}>
                <Space direction="vertical" style={{ width: '100%' }}>
                  {section.keys.map((k) => {
                    const meta = CFG_FIELD_META[k] || {};
                    return (
                      <InputNumber
                        key={k}
                        style={{ width: '100%' }}
                        addonBefore={termLabel(meta.label || k, meta.help || AUTO_TERM_HELP[k])}
                        addonAfter={meta.addonAfter}
                        value={cfg[k]}
                        min={meta.min}
                        max={meta.max}
                        step={meta.step ?? 1}
                        precision={meta.int ? 0 : undefined}
                        onChange={(v) => setCfgField(k, v)}
                      />
                    );
                  })}
                </Space>
              </Card>
            ))}

            <Button type="primary" icon={<SaveOutlined />} onClick={() => { void saveCfg(); }} loading={saving} block>
              保存参数
            </Button>
            <Button onClick={() => { void runCycleOnce(); }} loading={cycleRunning} block>
              立即执行一次
            </Button>
          </Space>
        )}
      </Card>

      <Card
        title="交易所资金监控"
        size="small"
        style={{ marginBottom: 12 }}
        extra={(
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => {
              void refreshExchangeFunds();
            }}
            loading={exchangeFundsLoading}
          >
            刷新
          </Button>
        )}
      >
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Typography.Text type="secondary">
            总资金 {fmtUsd(fundsSummary.totalUsdt, 2)}，组合名义占用 {fmtUsd(fundsSummary.currentNotional, 0)} / {fmtUsd(fundsSummary.maxNotional, 0)}（{num(fundsSummary.usedPct, 0).toFixed(1)}%）
          </Typography.Text>
          <Table
            size="small"
            rowKey={(r) => String(r.exchange_id)}
            loading={exchangeFundsLoading}
            dataSource={exchangeFunds}
            columns={exchangeFundsColumns}
            pagination={false}
            scroll={{ x: 620, y: 260 }}
            locale={{
              emptyText: exchangeFundsLoading ? <Spin /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无资金数据" />,
            }}
          />
        </Space>
      </Card>

      <Card title="最近周期" size="small" style={{ marginBottom: 12 }}>
        {!cycleLast ? (
          <Typography.Text type="secondary">暂无周期记录</Typography.Text>
        ) : (
          <Space direction="vertical" size={4} style={{ width: '100%' }}>
            <Space wrap size={6}>
              <Tag color={cycleStatusColor(cycleLast.status)}>状态: {cycleStatusLabel(cycleLast.status)}</Tag>
              {cycleModeTag(cycleLast.mode)}
              <Tag>模拟模式: {cycleLast.dry_run ? '是' : '否'}</Tag>
            </Space>
            <Typography.Text type="secondary">计划开仓 {num(cycleLast.open_plan_pairs, 0)} / 平仓 {num(cycleLast.close_plan_pairs, 0)}</Typography.Text>
            <Typography.Text type="secondary">已完成开仓 {num(cycleLast.opened_pairs, 0)} / 平仓 {num(cycleLast.closed_pairs, 0)}</Typography.Text>
            <Typography.Text type="secondary">失败开仓 {num(cycleLast.open_failed_pairs, 0)} / 平仓 {num(cycleLast.close_failed_pairs, 0)}</Typography.Text>
            <Typography.Text type="secondary">重试队列待处理 {num(cycleLast.retry_queue?.pending, 0)}</Typography.Text>
            {!!cycleLast.execution_writeback && (
              <Typography.Text type="secondary">
                新增重试 平仓/开仓 {num(cycleLast.execution_writeback?.retry_enqueued_close, 0)}/{num(cycleLast.execution_writeback?.retry_enqueued_open, 0)}
              </Typography.Text>
            )}
            {!!cycleLast.retry_result && (
              <Typography.Text type="secondary">
                重试 到期/执行/成功/失败/丢弃: {num(cycleLast.retry_result?.due_count, 0)}/{num(cycleLast.retry_result?.retried, 0)}/{num(cycleLast.retry_result?.succeeded, 0)}/{num(cycleLast.retry_result?.failed, 0)}/{num(cycleLast.retry_result?.dropped, 0)}
              </Typography.Text>
            )}
          </Space>
        )}
      </Card>

      <Card
        title="运行日志"
        size="small"
        style={{ marginBottom: 12 }}
        extra={(
          <Space>
            <Button size="small" onClick={() => { void refreshCycleLogs(); }}>刷新</Button>
            <Button size="small" danger onClick={() => setCycleLogs([])}>清空</Button>
          </Space>
        )}
      >
        <Table
          size="small"
          rowKey={(r) => r.__key || `${num(r.ts, 0)}-${r.status || 's'}-${r.mode || 'm'}`}
          dataSource={cycleLogs}
          columns={cycleLogColumns}
          pagination={false}
          scroll={{ y: 260 }}
          locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无运行日志" /> }}
        />
      </Card>

      <Card title="决策预览" size="small">
        {decisionLoading && !decisionPreview ? (
          <Spin />
        ) : !decisionPreview ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无预览" />
        ) : (
          <Space direction="vertical" size={6} style={{ width: '100%' }}>
            <Typography.Text type="secondary">{decisionPreview?.policy?.note || '--'}</Typography.Text>
            <Tag color={decisionPreview?.open_evaluation?.eligible ? 'success' : 'default'}>
              {decisionPreview?.open_evaluation?.eligible ? '允许入场' : '禁止入场'}
            </Tag>
            <Typography.Text type="secondary">候选数: {num(decisionPreview?.open_evaluation?.candidate_count, 0)}</Typography.Text>
          </Space>
        )}
      </Card>
    </Col>
  );
}
