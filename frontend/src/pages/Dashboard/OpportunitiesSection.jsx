import React from 'react';
import { ThunderboltOutlined } from '@ant-design/icons';
import { Card, InputNumber, Space, Table, Tag } from 'antd';

export default function OpportunitiesSection({
  opportunities,
  spotOpportunities,
  minVolume,
  minSpotVolume,
  onMinVolumeChange,
  onMinSpotVolumeChange,
  oppColumns,
  spotOppColumns,
  compact = false,
}) {
  if (compact) {
    return (
      <Card
        className="kinetic-panel-card kinetic-opportunities-card"
        title={<Space><ThunderboltOutlined style={{ color: '#7bd0ff' }} /><span>实时套利机会</span></Space>}
        style={{ marginBottom: 0 }}
        extra={(
          <Space>
            <span className="kinetic-mini-note">最小24h量</span>
            <InputNumber
              size="small"
              min={0}
              step={1000000}
              style={{ width: 130 }}
              value={minVolume || null}
              placeholder="不限"
              formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : '')}
              onChange={onMinVolumeChange}
            />
            <Tag color="green">{opportunities.length} 条</Tag>
          </Space>
        )}
      >
        <Table
          dataSource={opportunities}
          columns={oppColumns}
          rowKey="symbol"
          size="small"
          pagination={{ pageSize: 8, showSizeChanger: false }}
          scroll={{ x: 900 }}
        />
      </Card>
    );
  }

  return (
    <>
      <Card
        className="kinetic-panel-card"
        title={<Space><ThunderboltOutlined style={{ color: '#1677ff' }} /><span>跨所费率套利机会 (实时)</span></Space>}
        style={{ marginBottom: 24 }}
        extra={(
          <Space>
            <span style={{ color: '#888', fontSize: 13 }}>最小24h量 (U):</span>
            <InputNumber
              size="small"
              min={0}
              step={1000000}
              style={{ width: 130 }}
              value={minVolume || null}
              placeholder="不限"
              formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : '')}
              onChange={onMinVolumeChange}
            />
            <Tag color="blue">{opportunities.length} 个</Tag>
          </Space>
        )}
      >
        <Table
          dataSource={opportunities}
          columns={oppColumns}
          rowKey="symbol"
          size="small"
          pagination={{ pageSize: 10 }}
          scroll={{ x: 900 }}
        />
      </Card>

      <Card
        className="kinetic-panel-card"
        title={<Space><ThunderboltOutlined style={{ color: '#13c2c2' }} /><span>现货对冲机会 (实时)</span></Space>}
        style={{ marginBottom: 24 }}
        extra={(
          <Space>
            <span style={{ color: '#888', fontSize: 13 }}>合约24h量 (U):</span>
            <InputNumber
              size="small"
              min={0}
              step={1000000}
              style={{ width: 120 }}
              value={minVolume || null}
              placeholder="不限"
              formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : '')}
              onChange={onMinVolumeChange}
            />
            <span style={{ color: '#888', fontSize: 13 }}>现货24h量 (U):</span>
            <InputNumber
              size="small"
              min={0}
              step={1000000}
              style={{ width: 120 }}
              value={minSpotVolume || null}
              placeholder="不限"
              formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : '')}
              onChange={onMinSpotVolumeChange}
            />
            <Tag color="cyan">{spotOpportunities.length} 个</Tag>
          </Space>
        )}
      >
        <Table
          dataSource={spotOpportunities}
          columns={spotOppColumns}
          rowKey={(r) => `${r.long_exchange_id ?? r.exchange_id}-${r.short_exchange_id ?? r.exchange_id}-${r.symbol}`}
          size="small"
          pagination={{ pageSize: 10 }}
          scroll={{ x: 900 }}
          rowClassName={(r) => (r.has_spot_market === false ? 'row-no-spot' : '')}
        />
      </Card>
    </>
  );
}
