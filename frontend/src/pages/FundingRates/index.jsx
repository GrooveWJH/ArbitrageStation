import React, { useEffect, useState } from 'react';
import {
  Card, Table, Input, InputNumber, Select, Space, Button, Row, Col, Badge
} from 'antd';
import { SearchOutlined, ReloadOutlined, FilterOutlined } from '@ant-design/icons';
import {
  useFundingRateExchangesQuery,
  useFundingRatesQuery,
} from '../../services/queries/fundingRateQueries';
import { buildFundingColumns } from './columns';

const EMPTY_FILTERS = {
  symbol: '',
  min_rate: null,
  min_volume: null,
  exchange_ids: [],
};

function applyFundingRateFilters(rows, filters) {
  let result = Array.isArray(rows) ? rows : [];
  if (filters.symbol) {
    const symbol = filters.symbol.toUpperCase();
    result = result.filter((r) => r.symbol.toUpperCase().includes(symbol));
  }
  if (filters.min_rate != null) {
    result = result.filter((r) => Math.abs(r.rate_pct) >= filters.min_rate);
  }
  if (filters.exchange_ids.length) {
    result = result.filter((r) => filters.exchange_ids.includes(r.exchange_id));
  }
  if (filters.min_volume != null && filters.min_volume > 0) {
    result = result.filter((r) => (r.volume_24h || 0) >= filters.min_volume);
  }
  return result;
}

export default function FundingRates({ wsData }) {
  const [rates, setRates] = useState([]);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const exchangesQuery = useFundingRateExchangesQuery();
  const ratesQuery = useFundingRatesQuery(appliedFilters);
  const exchanges = exchangesQuery.data || [];
  const loading = ratesQuery.isPending || ratesQuery.isFetching;

  useEffect(() => {
    if (ratesQuery.data) {
      setRates(ratesQuery.data);
    }
  }, [ratesQuery.data]);

  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(rates.length / pageSize));
    if (page > maxPage) setPage(maxPage);
  }, [rates.length, page, pageSize]);

  // Real-time update from WS
  useEffect(() => {
    if (wsData?.type === 'funding_rates') {
      setRates(applyFundingRateFilters(wsData.data.rates, appliedFilters));
    }
  }, [wsData, appliedFilters]);

  const applyFilters = () => {
    setAppliedFilters(filters);
    setPage(1);
  };

  const resetFilters = () => {
    setFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setPage(1);
  };

  const columns = buildFundingColumns(exchanges);

  return (
    <div className="kinetic-page kinetic-funding">
      <Card
        className="kinetic-panel-card"
      title={
        <Space>
          <FilterOutlined />
          <span>资金费率监控</span>
          <span className="kinetic-counter-badge">
            <Badge count={rates.length} overflowCount={9999} />
          </span>
        </Space>
      }
      extra={
        <Button
          icon={<ReloadOutlined />}
          onClick={() => { void ratesQuery.refetch(); }}
          loading={loading}
        >
          刷新
        </Button>
      }
    >
      {/* Filter Row */}
      <Row gutter={[16, 16]} className="kinetic-funding-filter-row">
        <Col span={6}>
          <Input
            placeholder="搜索交易对，如 BTC"
            prefix={<SearchOutlined />}
            value={filters.symbol}
            onChange={e => setFilters(f => ({ ...f, symbol: e.target.value }))}
            onPressEnter={applyFilters}
            allowClear
          />
        </Col>
        <Col span={4}>
          <InputNumber
            placeholder="最小费率绝对值 %"
            style={{ width: '100%' }}
            min={0} max={10} step={0.01}
            value={filters.min_rate}
            onChange={v => setFilters(f => ({ ...f, min_rate: v }))}
          />
        </Col>
        <Col span={4}>
          <InputNumber
            placeholder="最小24h量 (U)"
            style={{ width: '100%' }}
            min={0} step={1000000}
            formatter={v => v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : ''}
            value={filters.min_volume}
            onChange={v => setFilters(f => ({ ...f, min_volume: v }))}
          />
        </Col>
        <Col span={6}>
          <Select
            mode="multiple"
            placeholder="筛选交易所"
            style={{ width: '100%' }}
            value={filters.exchange_ids}
            onChange={v => setFilters(f => ({ ...f, exchange_ids: v }))}
            options={exchanges.map(e => ({ label: e.display_name, value: e.id }))}
            allowClear
          />
        </Col>
        <Col span={3}>
          <Button className="kinetic-filter-apply-btn" onClick={applyFilters} icon={<FilterOutlined />}>
            筛选
          </Button>
        </Col>
        <Col span={3}>
          <Button onClick={resetFilters}>重置</Button>
        </Col>
      </Row>

      <Table
        className="kinetic-funding-table"
        dataSource={rates}
        columns={columns}
        rowKey={(r) => `${r.exchange_id}-${r.symbol}`}
        loading={loading}
        size="small"
        pagination={{
          current: page,
          pageSize,
          showSizeChanger: true,
          pageSizeOptions: [20, 50, 100, 200],
          showTotal: (t, range) => `${range[0]}-${range[1]} / ${t}`,
          onChange: (nextPage, nextPageSize) => {
            if (nextPageSize !== pageSize) {
              setPageSize(nextPageSize);
              setPage(1);
              return;
            }
            setPage(nextPage);
          },
        }}
        scroll={{ x: 900 }}
      />
      </Card>
    </div>
  );
}
