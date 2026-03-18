import React, { useEffect, useState } from 'react';
import {
  Card, Table, Tag, Input, InputNumber, Select, Space, Button, Row, Col, Tooltip, Badge
} from 'antd';
import { SearchOutlined, ReloadOutlined, FilterOutlined } from '@ant-design/icons';
import { getFundingRates, getExchanges } from '../../services/api';
import { fmtTime } from '../../utils/time';

export default function FundingRates({ wsData }) {
  const [rates, setRates] = useState([]);
  const [exchanges, setExchanges] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    symbol: '',
    min_rate: null,
    min_volume: null,
    exchange_ids: [],
  });

  const loadExchanges = async () => {
    const { data } = await getExchanges();
    setExchanges(data);
  };

  const loadRates = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.symbol) params.symbol = filters.symbol;
      if (filters.min_rate != null) params.min_rate = filters.min_rate;
      if (filters.min_volume != null) params.min_volume = filters.min_volume;
      if (filters.exchange_ids.length) params.exchange_ids = filters.exchange_ids.join(',');
      const { data } = await getFundingRates(params);
      setRates(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadExchanges();
    loadRates();
  }, []);

  // Real-time update from WS
  useEffect(() => {
    if (wsData?.type === 'funding_rates') {
      let newRates = wsData.data.rates;
      if (filters.symbol) {
        newRates = newRates.filter(r => r.symbol.toUpperCase().includes(filters.symbol.toUpperCase()));
      }
      if (filters.min_rate != null) {
        newRates = newRates.filter(r => Math.abs(r.rate_pct) >= filters.min_rate);
      }
      if (filters.exchange_ids.length) {
        newRates = newRates.filter(r => filters.exchange_ids.includes(r.exchange_id));
      }
      if (filters.min_volume != null && filters.min_volume > 0) {
        newRates = newRates.filter(r => (r.volume_24h || 0) >= filters.min_volume);
      }
      setRates(newRates);
    }
  }, [wsData]);

  const columns = [
    {
      title: '交易对', dataIndex: 'symbol', key: 'symbol', fixed: 'left', width: 160,
      render: v => <Tag color="blue" style={{ fontWeight: 600 }}>{v}</Tag>,
      sorter: (a, b) => a.symbol.localeCompare(b.symbol),
    },
    {
      title: '交易所', dataIndex: 'exchange_name', key: 'exchange_name', width: 120,
      render: v => <Tag>{v}</Tag>,
      filters: exchanges.map(e => ({ text: e.display_name, value: e.display_name })),
      onFilter: (value, record) => record.exchange_name === value,
    },
    {
      title: '资金费率', dataIndex: 'rate_pct', key: 'rate_pct', width: 130,
      render: v => {
        const color = v > 0 ? '#cf1322' : v < 0 ? '#3f8600' : '#666';
        const label = v > 0 ? '多头付费' : v < 0 ? '空头付费' : '中性';
        return (
          <Tooltip title={label}>
            <span style={{ color, fontWeight: 600 }}>
              {v > 0 ? '+' : ''}{v.toFixed(4)}%
            </span>
          </Tooltip>
        );
      },
      sorter: (a, b) => b.rate_pct - a.rate_pct,
      defaultSortOrder: 'descend',
    },
    {
      title: '费率绝对值', dataIndex: 'rate_pct', key: 'abs_rate',
      render: v => <Tag color={Math.abs(v) > 0.1 ? 'red' : Math.abs(v) > 0.05 ? 'orange' : 'default'}>
        {Math.abs(v).toFixed(4)}%
      </Tag>,
      sorter: (a, b) => Math.abs(b.rate_pct) - Math.abs(a.rate_pct),
      width: 130,
    },
    {
      title: '年化 (3次/天)', key: 'annualized',
      render: (_, r) => {
        const ann = r.rate_pct * 3 * 365;
        return <span style={{ color: ann > 10 ? '#1677ff' : '#666', fontWeight: ann > 10 ? 600 : 400 }}>
          {ann.toFixed(1)}%
        </span>;
      },
      sorter: (a, b) => Math.abs(b.rate_pct) - Math.abs(a.rate_pct),
      width: 140,
    },
    {
      title: '24h交易量(U)', dataIndex: 'volume_24h', key: 'volume_24h', width: 140,
      render: v => v > 0
        ? <span style={{ color: '#666' }}>{v >= 1e9 ? `${(v/1e9).toFixed(1)}B` : v >= 1e6 ? `${(v/1e6).toFixed(1)}M` : `${(v/1e3).toFixed(0)}K`}</span>
        : <span style={{ color: '#ccc' }}>-</span>,
      sorter: (a, b) => (b.volume_24h || 0) - (a.volume_24h || 0),
    },
    {
      title: '下次结算', dataIndex: 'next_funding_time', key: 'next_funding_time', width: 160,
      render: v => fmtTime(v),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <FilterOutlined />
          <span>资金费率监控</span>
          <Badge count={rates.length} overflowCount={9999} style={{ backgroundColor: '#1677ff' }} />
        </Space>
      }
      extra={
        <Button icon={<ReloadOutlined />} onClick={loadRates} loading={loading}>
          刷新
        </Button>
      }
    >
      {/* Filter Row */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Input
            placeholder="搜索交易对，如 BTC"
            prefix={<SearchOutlined />}
            value={filters.symbol}
            onChange={e => setFilters(f => ({ ...f, symbol: e.target.value }))}
            onPressEnter={loadRates}
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
          <Button type="primary" onClick={loadRates} icon={<FilterOutlined />}>
            筛选
          </Button>
        </Col>
        <Col span={3}>
          <Button onClick={() => {
            setFilters({ symbol: '', min_rate: null, min_volume: null, exchange_ids: [] });
            setTimeout(loadRates, 0);
          }}>重置</Button>
        </Col>
      </Row>

      <Table
        dataSource={rates}
        columns={columns}
        rowKey={(r) => `${r.exchange_id}-${r.symbol}`}
        loading={loading}
        size="small"
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: t => `共 ${t} 条` }}
        scroll={{ x: 900 }}
        rowClassName={r => Math.abs(r.rate_pct) > 0.1 ? 'high-rate-row' : ''}
      />
      <style>{`.high-rate-row { background: #fff7e6 !important; }`}</style>
    </Card>
  );
}
