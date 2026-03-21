import React, { useEffect, useMemo, useState } from 'react';
import DevOverlay from '../../components/DevOverlay';
import {
  Button,
  Card,
  Col,
  Form,
  Progress,
  Row,
  Select,
  Space,
  Table,
  Tag,
  message,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { getPnlV2StrategyDetail } from '../../services/endpoints/analyticsApi';
import { closeStrategy, openStrategy } from '../../services/endpoints/tradingApi';
import { usePositionsOverviewQuery } from '../../services/queries/positionsQueries';
import { getApiErrorMessage } from '../../utils/error';
import OpenStrategyModal from './OpenStrategyModal';
import PositionIntelCard from './PositionIntelCard';
import StrategyDetailDrawer from './StrategyDetailDrawer';
import { buildStrategyColumns } from './strategyColumns';
import { pnlPctRender, pnlRender, qualityTag, statusTag } from './renderers';

export default function Positions() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [openModal, setOpenModal] = useState(false);
  const [detailDrawer, setDetailDrawer] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailEventFilter, setDetailEventFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('active');
  const [strategyType, setStrategyType] = useState('cross_exchange');
  const [selectedStrategyId, setSelectedStrategyId] = useState(null);
  const [form] = Form.useForm();

  const positionsOverviewQuery = usePositionsOverviewQuery({
    status: statusFilter,
    page,
    pageSize,
  });
  const overview = positionsOverviewQuery.data || {};
  const strategies = overview.strategies || [];
  const exchanges = overview.exchanges || [];
  const opportunities = overview.opportunities || [];
  const spotOpportunities = overview.spotOpportunities || [];
  const totalCount = overview.totalCount || 0;
  const loading = positionsOverviewQuery.isPending || positionsOverviewQuery.isFetching;

  useEffect(() => {
    setPage(1);
  }, [statusFilter]);

  useEffect(() => {
    if (strategies.length === 0) {
      setSelectedStrategyId(null);
      return;
    }
    setSelectedStrategyId((prev) => {
      if (prev && strategies.some((item) => item.id === prev)) return prev;
      return strategies[0].id;
    });
  }, [strategies]);

  const handleOpenStrategy = async (values) => {
    try {
      await openStrategy(values);
      message.success('策略已创建');
      setOpenModal(false);
      form.resetFields();
      await positionsOverviewQuery.refetch();
    } catch (e) {
      message.error(`开仓失败: ${getApiErrorMessage(e)}`);
    }
  };

  const handleClose = async (id) => {
    try {
      await closeStrategy(id, { reason: 'manual_close' });
      message.success('平仓请求已发送');
      await positionsOverviewQuery.refetch();
    } catch (e) {
      message.error(`平仓失败: ${getApiErrorMessage(e)}`);
    }
  };

  const openDetail = async (record) => {
    setDetailEventFilter('all');
    setDetailDrawer({ ...record, v2: null });
    setDetailLoading(true);
    try {
      const res = await getPnlV2StrategyDetail(record.id, { window_mode: 'lifecycle', event_limit: 200 });
      const payload = res?.data || null;
      setDetailDrawer((prev) => (prev && prev.id === record.id ? { ...prev, v2: payload } : prev));
    } catch (e) {
      message.warning(`加载详情失败: ${getApiErrorMessage(e)}`);
    } finally {
      setDetailLoading(false);
    }
  };

  const fillFromOpportunity = (opp) => {
    form.setFieldsValue({
      symbol: opp.symbol,
      long_exchange_id: opp.long_exchange_id,
      short_exchange_id: opp.short_exchange_id,
    });
  };

  const fillFromSpotOpportunity = (opp) => {
    form.setFieldsValue({
      symbol: opp.symbol,
      long_exchange_id: opp.long_exchange_id ?? opp.spot_exchange_id ?? opp.exchange_id,
      short_exchange_id: opp.short_exchange_id ?? opp.perp_exchange_id ?? opp.exchange_id,
    });
  };

  const columns = useMemo(
    () => buildStrategyColumns({ openDetail, handleClose, statusTag, qualityTag, pnlRender }),
    [openDetail, handleClose],
  );

  const selectedStrategy = useMemo(
    () => strategies.find((item) => item.id === selectedStrategyId) || null,
    [strategies, selectedStrategyId],
  );

  const metrics = useMemo(() => {
    const totalMargin = strategies.reduce((sum, item) => sum + Number(item.initial_margin_usd || 0), 0);
    const unrealized = strategies.reduce((sum, item) => sum + Number(item.unrealized_pnl || 0), 0);
    const activeCount = strategies.filter((item) => item.status === 'active').length;
    const openInterest = strategies.reduce((sum, item) => sum + Math.abs(Number(item.initial_margin_usd || 0) * 2.5), 0);
    const stressedCount = strategies.filter(
      (item) => Number(item.total_pnl_usd || 0) < 0 || ['missing', 'stale', 'partial'].includes(item.quality),
    ).length;
    const maintenanceMargin = activeCount === 0 ? 0 : Math.min(95, Math.max(6, (stressedCount / activeCount) * 42));
    return {
      totalMargin,
      unrealized,
      openInterest,
      maintenanceMargin,
      activeCount,
      stressedCount,
    };
  }, [strategies]);

  const selectedRisk = useMemo(() => {
    if (!selectedStrategy) return { label: '暂无', pct: 0, tone: 'neutral' };
    const quality = selectedStrategy.quality || 'unknown';
    if (quality === 'ok') return { label: '低波动', pct: 28, tone: 'ok' };
    if (quality === 'na') return { label: '中等', pct: 45, tone: 'mid' };
    if (quality === 'partial') return { label: '偏高', pct: 62, tone: 'warn' };
    if (quality === 'stale') return { label: '高风险', pct: 76, tone: 'warn' };
    return { label: '严重', pct: 88, tone: 'danger' };
  }, [selectedStrategy]);

  return (
    <div className="kinetic-page kinetic-positions">
      <Row gutter={[16, 16]} className="kinetic-positions-metric-row">
        <Col xs={24} md={12} xl={6}>
          <Card className="kinetic-position-metric">
            <div className="label">保证金总额</div>
            <div className="value">${metrics.totalMargin.toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
            <div className="meta">{metrics.activeCount} 个运行中策略</div>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card className="kinetic-position-metric">
            <div className="label">未实现盈亏</div>
            <div className={`value ${metrics.unrealized >= 0 ? 'positive' : 'negative'}`}>
              {metrics.unrealized >= 0 ? '+' : ''}{metrics.unrealized.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </div>
            <div className="meta">质量异常 {metrics.stressedCount}</div>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card className="kinetic-position-metric">
            <div className="label">名义敞口</div>
            <div className="value">${metrics.openInterest.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
            <div className="meta">跨交易所合成头寸</div>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <DevOverlay>
          <Card className="kinetic-position-metric">
            <div className="label">维持保证金</div>
            <div className="value">{metrics.maintenanceMargin.toFixed(1)}%</div>
            <Progress percent={Number(metrics.maintenanceMargin.toFixed(1))} showInfo={false} strokeColor="#7bd0ff" trailColor="rgba(43,70,128,0.35)" />
          </Card>
          </DevOverlay>
        </Col>
      </Row>

      <Row gutter={[16, 16]} className="kinetic-positions-main-grid">
        <Col xs={24} xl={16}>
          <Card
            className="kinetic-panel-card"
            title="运行中策略"
            extra={(
              <Space>
                <Select
                  value={statusFilter}
                  onChange={setStatusFilter}
                  style={{ width: 140 }}
                  options={[
                    { label: '运行中', value: 'active' },
                    { label: '已结束', value: 'closed' },
                    { label: '全部', value: undefined },
                  ]}
                />
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => {
                    void positionsOverviewQuery.refetch();
                  }}
                  loading={loading}
                >
                  刷新
                </Button>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpenModal(true)}>
                  新建仓位
                </Button>
              </Space>
            )}
          >
            <Table
              className="kinetic-positions-table"
              dataSource={strategies}
              columns={columns}
              rowKey="id"
              loading={loading}
              size="small"
              tableLayout="auto"
              scroll={{ x: 1960 }}
              pagination={{
                current: page,
                pageSize,
                total: totalCount,
                showSizeChanger: true,
                pageSizeOptions: [15, 30, 50, 100],
                showTotal: (t, range) => `${range[0]}-${range[1]} / ${t}`,
                onChange: (nextPage, nextPageSize) => {
                  setPage(nextPage);
                  if (nextPageSize !== pageSize) setPageSize(nextPageSize);
                },
              }}
              rowClassName={(r) => {
                if (r.id === selectedStrategyId) return 'kinetic-selected-strategy-row';
                if (r.quality === 'missing') return 'missing-row';
                if (r.total_pnl_usd == null) return 'partial-row';
                return '';
              }}
              onRow={(record) => ({
                onClick: () => setSelectedStrategyId(record.id),
              })}
            />
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <PositionIntelCard
            selectedStrategy={selectedStrategy}
            selectedRisk={selectedRisk}
            statusTag={statusTag}
            qualityTag={qualityTag}
            onOpenDetail={() => {
              if (selectedStrategy) void openDetail(selectedStrategy);
            }}
            onClosePosition={() => {
              if (selectedStrategy?.id) void handleClose(selectedStrategy.id);
            }}
            onOpenPosition={() => setOpenModal(true)}
          />
        </Col>
      </Row>

      <OpenStrategyModal
        open={openModal}
        onCancel={() => setOpenModal(false)}
        strategyType={strategyType}
        setStrategyType={setStrategyType}
        opportunities={opportunities}
        spotOpportunities={spotOpportunities}
        fillFromOpportunity={fillFromOpportunity}
        fillFromSpotOpportunity={fillFromSpotOpportunity}
        form={form}
        exchanges={exchanges}
        onSubmit={handleOpenStrategy}
      />

      <StrategyDetailDrawer
        detailDrawer={detailDrawer}
        detailLoading={detailLoading}
        detailEventFilter={detailEventFilter}
        setDetailEventFilter={setDetailEventFilter}
        setDetailDrawer={setDetailDrawer}
        statusTag={statusTag}
        qualityTag={qualityTag}
        pnlRender={pnlRender}
        pnlPctRender={pnlPctRender}
      />

      <style>{`
        .missing-row { background: #fff1f0 !important; }
        .partial-row { background: #fff7e6 !important; }
        .kinetic-selected-strategy-row td {
          background: rgba(123, 208, 255, 0.14) !important;
        }
      `}</style>
    </div>
  );
}
