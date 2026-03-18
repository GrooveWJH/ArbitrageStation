import React from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  InputNumber,
  Progress,
  Row,
  Space,
  Statistic,
  Table,
  Text,
} from 'antd';
import {
  LineChartOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { Typography } from 'antd';
import EquityCurveChart from './EquityCurveChart';
import { DELTA_REASON_LABELS, IMPORT_JOB_TYPE_LABELS } from './constants';
import { num } from './utils';

const { Title } = Typography;

export default function BacktestSection({
  params,
  setParams,
  onNumber,
  importPath,
  setImportPath,
  fundingImportPath,
  setFundingImportPath,
  importLoading,
  readinessLoading,
  availableRangeLoading,
  loading,
  startSnapshotImport,
  startFundingImport,
  checkReadiness,
  fillAvailableDates,
  startBacktest,
  refreshBacktestJob,
  jobId,
  job,
  importJobId,
  importJob,
  readiness,
  availableRange,
  fmtReasonCodes,
  statusTag,
  summary,
  curve,
  events,
  eventCols,
}) {
  return (
    <>
      <Card>
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <LineChartOutlined style={{ color: '#1677ff' }} />
            <Title level={5} style={{ margin: 0 }}>现货-合约费率套利回测</Title>
          </Space>
          <Space>
            <Button icon={<ReloadOutlined />} disabled={!jobId} onClick={() => { void refreshBacktestJob(); }}>
              刷新任务
            </Button>
            <Button icon={<UploadOutlined />} loading={importLoading} onClick={startSnapshotImport}>
              导入本地快照
            </Button>
            <Button icon={<UploadOutlined />} loading={importLoading} onClick={startFundingImport}>
              导入Funding历史
            </Button>
            <Button loading={readinessLoading} onClick={() => { void checkReadiness(false); }}>
              覆盖检查
            </Button>
            <Button loading={availableRangeLoading} onClick={() => { void fillAvailableDates(); }}>
              自动填充日期
            </Button>
            <Button type="primary" loading={loading} icon={<PlayCircleOutlined />} onClick={() => { void startBacktest(); }}>
              启动回测
            </Button>
          </Space>
        </Space>

        <Row gutter={[12, 12]} style={{ marginTop: 14 }}>
          <Col span={8}>
            <Typography.Text>离线快照文件路径(CSV/Parquet)</Typography.Text>
            <Input
              value={importPath}
              onChange={(e) => setImportPath(e.target.value)}
              placeholder="例如 C:\\data\\snapshots_15m_2026-02-27_2026-03-13.csv"
            />
          </Col>
          <Col span={8}>
            <Typography.Text>Funding历史文件路径(CSV/Parquet)</Typography.Text>
            <Input
              value={fundingImportPath}
              onChange={(e) => setFundingImportPath(e.target.value)}
              placeholder="例如 C:\\data\\funding_2026-02-27_2026-03-13.csv"
            />
          </Col>
          <Col span={4}>
            <Typography.Text>开始日期(YYYY-MM-DD)</Typography.Text>
            <Input value={params.start_date} onChange={(e) => setParams((p) => ({ ...p, start_date: e.target.value }))} placeholder="留空按 days" />
          </Col>
          <Col span={4}>
            <Typography.Text>结束日期(YYYY-MM-DD)</Typography.Text>
            <Input value={params.end_date} onChange={(e) => setParams((p) => ({ ...p, end_date: e.target.value }))} placeholder="留空为今天" />
          </Col>
          <Col span={4}><Typography.Text>回放天数</Typography.Text><InputNumber min={1} max={180} value={params.days} onChange={onNumber('days', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Typography.Text>每日机会池TopN</Typography.Text><InputNumber min={1} max={2000} value={params.top_n} onChange={onNumber('top_n', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Typography.Text>初始资金(USDT)</Typography.Text><InputNumber min={100} value={params.initial_nav_usd} onChange={onNumber('initial_nav_usd', setParams)} style={{ width: '100%' }} /></Col>

          <Col span={4}><Typography.Text>最小费率(%)</Typography.Text><InputNumber min={0} step={0.001} value={params.min_rate_pct} onChange={onNumber('min_rate_pct', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Typography.Text>最小合约量</Typography.Text><InputNumber min={0} value={params.min_perp_volume} onChange={onNumber('min_perp_volume', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Typography.Text>最小现货量</Typography.Text><InputNumber min={0} value={params.min_spot_volume} onChange={onNumber('min_spot_volume', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Typography.Text>最小基差(%)</Typography.Text><InputNumber step={0.001} value={params.min_basis_pct} onChange={onNumber('min_basis_pct', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Typography.Text>最大持仓对数</Typography.Text><InputNumber min={1} max={50} value={params.max_open_pairs} onChange={onNumber('max_open_pairs', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Typography.Text>目标利用率(%)</Typography.Text><InputNumber min={1} max={95} value={params.target_utilization_pct} onChange={onNumber('target_utilization_pct', setParams)} style={{ width: '100%' }} /></Col>

          <Col span={4}><Typography.Text>入场置信度下限</Typography.Text><InputNumber min={0} max={1} step={0.01} value={params.entry_conf_min} onChange={onNumber('entry_conf_min', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Typography.Text>换仓确认轮数</Typography.Text><InputNumber min={1} max={20} value={params.switch_confirm_rounds} onChange={onNumber('switch_confirm_rounds', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Typography.Text>最小单对本金</Typography.Text><InputNumber min={1} value={params.min_pair_notional_usd} onChange={onNumber('min_pair_notional_usd', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Typography.Text>硬回撤阈值(%)</Typography.Text><InputNumber max={0} step={0.1} value={params.portfolio_dd_hard_pct} onChange={onNumber('portfolio_dd_hard_pct', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Typography.Text>数据陈旧桶数</Typography.Text><InputNumber min={0} max={50} value={params.data_stale_max_buckets} onChange={onNumber('data_stale_max_buckets', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Typography.Text>最大冲击(%)</Typography.Text><InputNumber min={0.01} max={10} step={0.01} value={params.max_impact_pct} onChange={onNumber('max_impact_pct', setParams)} style={{ width: '100%' }} /></Col>
        </Row>
      </Card>

      <Card>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Typography.Text strong>回测前数据覆盖检查</Typography.Text>
          <Typography.Text type="secondary">范围: {readiness?.start_date || '--'} ~ {readiness?.end_date || '--'}</Typography.Text>
        </Space>
        {availableRange?.recommended_start_date && availableRange?.recommended_end_date ? (
          <Typography.Text type="secondary">
            建议区间: {availableRange.recommended_start_date} ~ {availableRange.recommended_end_date}（连续{num(availableRange.trailing_contiguous_days, 0)}天）
          </Typography.Text>
        ) : null}
        {!readiness ? (
          <Alert type="info" showIcon style={{ marginTop: 10 }} message="尚未检查覆盖" description="点击“覆盖检查”获取候选池与15m快照覆盖情况。" />
        ) : (
          <>
            <Alert
              type={readiness.ready ? 'success' : 'error'}
              showIcon
              style={{ marginTop: 10 }}
              message={readiness.ready ? '覆盖检查通过' : '覆盖检查未通过'}
              description={`原因: ${fmtReasonCodes(readiness.reason_codes)}`}
            />
            {Array.isArray(readiness.reason_codes) && readiness.reason_codes.includes('previous_run_deadband_blocked') ? (
              <Alert
                type="warning"
                showIcon
                style={{ marginTop: 10 }}
                message="上次回测被 deadband 阻断"
                description={`阻断桶数: ${num(readiness?.latest_backtest_hint?.delta_blocked_bucket_count, 0)}；请检查绝对/相对增益门槛与成本参数。`}
              />
            ) : null}
            <Row gutter={[12, 12]} style={{ marginTop: 10 }}>
              <Col span={6}><Statistic title="期望交易日" value={num(readiness.expected_trade_days, 0)} /></Col>
              <Col span={6}><Statistic title="有机会池的天数" value={num(readiness.universe_days_with_rows, 0)} /></Col>
              <Col span={6}><Statistic title="缺失机会池天数" value={num(readiness.missing_universe_date_count, 0)} /></Col>
              <Col span={6}><Statistic title="快照覆盖率" value={num(readiness.snapshot_bucket_coverage_pct)} precision={2} suffix="%" /></Col>
            </Row>
          </>
        )}
      </Card>

      <Card>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Typography.Text strong>
              离线导入任务ID: {importJobId || '--'}
              {importJob?.job_type ? ` (${IMPORT_JOB_TYPE_LABELS[importJob.job_type] || importJob.job_type})` : ''}
            </Typography.Text>
            {statusTag(importJob?.status)}
            <Typography.Text type="secondary">{importJob?.message || ''}</Typography.Text>
          </Space>
          <Typography.Text type="secondary">更新时间: {importJob?.updated_at ? new Date(importJob.updated_at).toLocaleString('zh-CN') : '--'}</Typography.Text>
        </Space>
        <Progress percent={Math.round(num(importJob?.progress, 0) * 100)} style={{ marginTop: 10 }} />
      </Card>

      <Card>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Typography.Text strong>回测任务ID: {jobId || '--'}</Typography.Text>
            {statusTag(job?.status)}
            <Typography.Text type="secondary">{job?.message || ''}</Typography.Text>
          </Space>
          <Typography.Text type="secondary">更新时间: {job?.updated_at ? new Date(job.updated_at).toLocaleString('zh-CN') : '--'}</Typography.Text>
        </Space>
        <Progress percent={Math.round(num(job?.progress, 0) * 100)} style={{ marginTop: 10 }} />
      </Card>

      <Card>
        <Title level={5}>回测摘要</Title>
        {!summary?.reason && num(summary?.trades_opened, 0) === 0 && num(summary?.delta_blocked_bucket_count, 0) > 0 ? (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="本次回测被 deadband 阻断，未触发执行"
            description={`阻断桶数: ${num(summary?.delta_blocked_bucket_count, 0)}；原因: ${(summary?.delta_block_reason_top || []).map((x) => `${DELTA_REASON_LABELS[x.code] || x.code}(${x.count})`).join('、') || '--'}`}
          />
        ) : null}
        <Row gutter={[12, 12]}>
          <Col span={6}><Statistic title="起始资金" value={num(summary.initial_nav_usd)} precision={2} prefix="$" /></Col>
          <Col span={6}><Statistic title="结束资金" value={num(summary.end_nav_usd)} precision={2} prefix="$" /></Col>
          <Col span={6}><Statistic title="总收益率" value={num(summary.total_return_pct)} precision={3} suffix="%" /></Col>
          <Col span={6}><Statistic title="最大回撤" value={num(summary.max_drawdown_pct)} precision={3} suffix="%" /></Col>
          <Col span={6}><Statistic title="Funding收益" value={num(summary.funding_pnl_usd)} precision={4} prefix="$" /></Col>
          <Col span={6}><Statistic title="Basis收益" value={num(summary.basis_pnl_usd)} precision={4} prefix="$" /></Col>
          <Col span={6}><Statistic title="手续费" value={num(summary.fee_paid_usd)} precision={4} prefix="$" /></Col>
          <Col span={6}><Statistic title="执行换仓次数" value={num(summary.rebalance_executed, 0)} /></Col>
        </Row>
      </Card>

      <Card title="权益曲线">
        <EquityCurveChart rows={curve} />
      </Card>

      <Card title={`事件明细 (${events.length})`}>
        <Table
          size="small"
          rowKey={(r, idx) => `${r.ts || ''}-${r.action || ''}-${idx}`}
          columns={eventCols}
          dataSource={events}
          pagination={{ pageSize: 15, showSizeChanger: false }}
          scroll={{ x: 900 }}
        />
      </Card>
    </>
  );
}
