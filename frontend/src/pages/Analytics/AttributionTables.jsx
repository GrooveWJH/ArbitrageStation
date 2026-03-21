import React from 'react';
import {
  Card,
  Col,
  Row,
  Table,
} from 'antd';
import { TermLabel } from '../../components/TermHint';
import { PnlText } from './renderers';

function AttributionTable({ rows, prefix, emptyText }) {
  return (
    <Table
      size="small"
      pagination={false}
      rowKey={(r) => `${prefix}-${r.strategy_type}`}
      dataSource={rows}
      columns={[
        { title: '类型', dataIndex: 'strategy_type', width: 120 },
        { title: '策略数', dataIndex: 'strategy_count', width: 90 },
        {
          title: '盈亏',
          dataIndex: 'pnl_usdt',
          render: (v) => <PnlText value={v} />,
        },
        {
          title: '占比',
          dataIndex: 'pnl_ratio',
          render: (v) => (v == null ? '--' : `${(Number(v) * 100).toFixed(2)}%`),
        },
      ]}
      expandable={{
        rowExpandable: (r) => Array.isArray(r?.strategies) && r.strategies.length > 0,
        expandedRowRender: (r) => (
          <Table
            size="small"
            pagination={false}
            rowKey={(s) => `${prefix}-${r.strategy_type}-${s.strategy_id}`}
            dataSource={r.strategies || []}
            columns={[
              { title: '策略 ID', dataIndex: 'strategy_id', width: 110 },
              { title: '名称', dataIndex: 'name', ellipsis: true },
              { title: '盈亏', dataIndex: 'pnl_usdt', width: 150, render: (v) => <PnlText value={v} /> },
            ]}
          />
        ),
      }}
      locale={{ emptyText }}
    />
  );
}

export default function AttributionTables({
  profitRows,
  lossRows,
}) {
  return (
    <Row gutter={12} style={{ marginBottom: 16 }}>
      <Col span={12}>
        <Card size="small" title={<TermLabel label="收益归因" term="attribution" />}>
          <AttributionTable rows={profitRows} prefix="p" emptyText="暂无收益归因数据" />
        </Card>
      </Col>
      <Col span={12}>
        <Card size="small" title={<TermLabel label="亏损归因" term="attribution" />}>
          <AttributionTable rows={lossRows} prefix="l" emptyText="暂无亏损归因数据" />
        </Card>
      </Col>
    </Row>
  );
}
