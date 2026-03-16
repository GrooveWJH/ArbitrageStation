import React, { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Select,
  Space,
  Table,
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

  const handleOpenStrategy = async (values) => {
    try {
      await openStrategy(values);
      message.success('Strategy opened');
      setOpenModal(false);
      form.resetFields();
      await positionsOverviewQuery.refetch();
    } catch (e) {
      message.error(`Open failed: ${getApiErrorMessage(e)}`);
    }
  };

  const handleClose = async (id) => {
    try {
      await closeStrategy(id, { reason: 'manual_close' });
      message.success('Close request sent');
      await positionsOverviewQuery.refetch();
    } catch (e) {
      message.error(`Close failed: ${getApiErrorMessage(e)}`);
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
      message.warning(`Load detail failed: ${getApiErrorMessage(e)}`);
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

  return (
    <>
      <Card
        title="Strategy Management"
        extra={(
          <Space>
            <Select
              value={statusFilter}
              onChange={setStatusFilter}
              style={{ width: 140 }}
              options={[
                { label: 'Active', value: 'active' },
                { label: 'Closed', value: 'closed' },
                { label: 'All', value: undefined },
              ]}
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                void positionsOverviewQuery.refetch();
              }}
              loading={loading}
            >
              Refresh
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpenModal(true)}>
              Open Strategy
            </Button>
          </Space>
        )}
      >
        <Table
          dataSource={strategies}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="small"
          scroll={{ x: 1400 }}
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
            if (r.quality === 'missing') return 'missing-row';
            if (r.total_pnl_usd == null) return 'partial-row';
            return '';
          }}
        />
      </Card>

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
      `}</style>
    </>
  );
}
