import React from 'react';
import { Card, Table, Tag } from 'antd';

export default function RecentTradesCard({ logs, columns }) {
  return (
    <Card title="最近成交记录" extra={<Tag>{logs.length} 条</Tag>}>
      <Table
        dataSource={logs}
        columns={columns}
        rowKey="id"
        size="small"
        pagination={{ pageSize: 10 }}
        scroll={{ x: 900 }}
        rowClassName={(r) => (r.action === 'emergency_close' ? 'risk-row' : '')}
      />
    </Card>
  );
}
