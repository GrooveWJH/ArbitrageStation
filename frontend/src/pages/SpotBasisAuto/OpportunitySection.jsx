import React from 'react';
import {
  Button,
  Card,
  Col,
  Empty,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
} from 'antd';
import {
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import HistoryPanel from './HistoryPanel';
import { keyOf, num, STRICT_HINT } from './helpers';

export default function OpportunitySection({
  filters,
  setFilters,
  exchangeOptions,
  rows,
  rowsLoading,
  refreshRows,
  stats,
  expanded,
  setExpanded,
  columns,
}) {
  return (
    <div className="opportunity-section">
      <Card style={{ marginBottom: 12 }}>
        <Space wrap>
          <Input
            style={{ width: 240 }}
            placeholder="搜索交易对"
            prefix={<SearchOutlined />}
            value={filters.symbol}
            onChange={(e) => setFilters((f) => ({ ...f, symbol: e.target.value }))}
          />
          <InputNumber addonBefore="费率%" value={filters.min_rate} min={0} step={0.001} onChange={(v) => setFilters((f) => ({ ...f, min_rate: num(v, 0) }))} />
          <InputNumber addonBefore="合约量" value={filters.min_perp_volume} min={0} step={100000} onChange={(v) => setFilters((f) => ({ ...f, min_perp_volume: num(v, 0) }))} />
          <InputNumber addonBefore="现货量" value={filters.min_spot_volume} min={0} step={100000} onChange={(v) => setFilters((f) => ({ ...f, min_spot_volume: num(v, 0) }))} />
          <InputNumber addonBefore="基差%" value={filters.min_basis_pct} min={-10} step={0.01} onChange={(v) => setFilters((f) => ({ ...f, min_basis_pct: num(v, 0) }))} />
          <Select mode="multiple" allowClear style={{ width: 220 }} placeholder="合约交易所" value={filters.perp_exchange_ids} options={exchangeOptions} onChange={(v) => setFilters((f) => ({ ...f, perp_exchange_ids: v || [] }))} />
          <Select mode="multiple" allowClear style={{ width: 220 }} placeholder="现货交易所" value={filters.spot_exchange_ids} options={exchangeOptions} onChange={(v) => setFilters((f) => ({ ...f, spot_exchange_ids: v || [] }))} />
          <Select
            style={{ width: 180 }}
            value={filters.sort_by}
            options={[
              { label: '严格综合评分', value: 'score_strict' },
              { label: '资金费率', value: 'funding_rate_pct' },
              { label: '基差', value: 'basis_abs' },
              { label: 'E24净期望', value: 'e24_net_pct' },
            ]}
            onChange={(v) => setFilters((f) => ({ ...f, sort_by: v || 'score_strict' }))}
          />
          <Button icon={<ReloadOutlined />} type="primary" onClick={() => { void refreshRows(false); }} loading={rowsLoading}>
            刷新
          </Button>
        </Space>
      </Card>

      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col span={8}><Card><Statistic title="监控标的" value={stats.c} /></Card></Col>
        <Col span={8}><Card><Statistic title="平均E24净期望" value={Number(num(stats.e, 0).toFixed(4))} suffix="%" /></Card></Col>
        <Col span={8}><Card><Statistic title="最高综合评分" value={Number(num(stats.s, 0).toFixed(4))} /></Card></Col>
      </Row>

      <Card title={<Space>机会列表 <Tag color="blue">{rows.length}</Tag> <Tag>{STRICT_HINT}</Tag></Space>}>
        <Table
          size="small"
          rowKey={keyOf}
          loading={rowsLoading}
          dataSource={rows}
          columns={columns}
          pagination={{ pageSize: 20, showSizeChanger: false }}
          expandable={{
            expandedRowKeys: expanded,
            onExpandedRowsChange: (keys) => setExpanded((keys || []).map((k) => String(k))),
            expandedRowRender: (record) => <HistoryPanel key={keyOf(record)} row={record} />,
          }}
          scroll={{ x: 1500 }}
          locale={{
            emptyText: rowsLoading ? <Spin /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无机会" />,
          }}
        />
      </Card>
    </div>
  );
}
