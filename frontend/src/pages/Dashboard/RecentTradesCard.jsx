import React from 'react';
import { Card, Table, Tag } from 'antd';
import { fmtTime } from '../../utils/time';

export default function RecentTradesCard({ logs, columns, compact = false }) {
  if (compact) {
    return (
      <Card className="kinetic-panel-card kinetic-exec-logs-card" title="执行日志" extra={<Tag>{logs.length}</Tag>}>
        <div className="kinetic-log-list">
          {logs.slice(0, 6).map((log) => (
            <div className="kinetic-log-item" key={log.id}>
              <div className={`kinetic-log-dot ${log.action === 'emergency_close' ? 'danger' : 'ok'}`} />
              <div className="kinetic-log-content">
                <div className="kinetic-log-title">{log.action || '交易事件'}</div>
                <div className="kinetic-log-sub">
                  {fmtTime(log.created_at || log.ts) || '-'}
                  {' | '}
                  {log.symbol || log.message || '系统事件'}
                </div>
              </div>
            </div>
          ))}
          {logs.length === 0 ? (
            <div className="kinetic-mini-note">暂无执行日志</div>
          ) : null}
        </div>
      </Card>
    );
  }

  return (
    <Card className="kinetic-panel-card" title="最近成交记录" extra={<Tag>{logs.length} 条</Tag>}>
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
