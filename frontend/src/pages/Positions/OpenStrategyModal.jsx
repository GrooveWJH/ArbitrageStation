import React from 'react';
import {
  Button,
  Card,
  Col,
  Form,
  InputNumber,
  Modal,
  Row,
  Select,
  Table,
} from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';

export default function OpenStrategyModal({
  open,
  onCancel,
  strategyType,
  setStrategyType,
  opportunities,
  spotOpportunities,
  fillFromOpportunity,
  fillFromSpotOpportunity,
  form,
  exchanges,
  onSubmit,
}) {
  return (
    <Modal title="Open Strategy" open={open} onCancel={onCancel} footer={null} width={700}>
      {strategyType === 'cross_exchange' && opportunities.length > 0 && (
        <Card size="small" title={<><ThunderboltOutlined /> Top Cross Opportunities</>} style={{ marginBottom: 16 }}>
          <Table
            dataSource={opportunities.slice(0, 5)}
            size="small"
            pagination={false}
            rowKey="symbol"
            columns={[
              { title: 'Symbol', dataIndex: 'symbol' },
              { title: 'Long Ex', dataIndex: 'long_exchange' },
              { title: 'Short Ex', dataIndex: 'short_exchange' },
              { title: 'Annualized', dataIndex: 'annualized_pct', render: (v) => `${v.toFixed(1)}%` },
              {
                title: '',
                key: 'fill',
                render: (_, r) => (
                  <Button size="small" onClick={() => fillFromOpportunity(r)}>
                    Fill
                  </Button>
                ),
              },
            ]}
          />
        </Card>
      )}

      {strategyType === 'spot_hedge' && spotOpportunities.length > 0 && (
        <Card size="small" title={<><ThunderboltOutlined /> Top Spot-Perp Opportunities</>} style={{ marginBottom: 16 }}>
          <Table
            dataSource={spotOpportunities.slice(0, 5)}
            size="small"
            pagination={false}
            rowKey={(r) =>
              `${r.symbol}-${r.long_exchange_id ?? r.spot_exchange_id ?? r.exchange_id}-${r.short_exchange_id ?? r.perp_exchange_id ?? r.exchange_id}`
            }
            columns={[
              { title: 'Symbol', dataIndex: 'symbol' },
              { title: 'Spot Ex', dataIndex: 'long_exchange' },
              { title: 'Perp Ex', dataIndex: 'short_exchange' },
              { title: 'Rate', dataIndex: 'rate_pct', render: (v) => `${v > 0 ? '+' : ''}${v.toFixed(4)}%` },
              { title: 'Annualized', dataIndex: 'annualized_pct', render: (v) => `${v.toFixed(1)}%` },
              {
                title: '',
                key: 'fill',
                render: (_, r) => (
                  <Button size="small" onClick={() => fillFromSpotOpportunity(r)}>
                    Fill
                  </Button>
                ),
              },
            ]}
          />
        </Card>
      )}

      <Form
        form={form}
        layout="vertical"
        onFinish={onSubmit}
        onValuesChange={(changed) => {
          if (changed.strategy_type) setStrategyType(changed.strategy_type);
        }}
        initialValues={{ strategy_type: 'cross_exchange', leverage: 1 }}
      >
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="strategy_type" label="Strategy Type" rules={[{ required: true }]}>
              <Select
                options={[
                  { label: 'Cross Exchange - long low funding / short high funding', value: 'cross_exchange' },
                  { label: 'Spot Hedge - buy spot + short perp', value: 'spot_hedge' },
                ]}
              />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              name="symbol"
              label={strategyType === 'spot_hedge' ? 'Perp Symbol' : 'Symbol'}
              rules={[{ required: true }]}
            >
              <Select
                showSearch
                placeholder="e.g. BTC/USDT:USDT"
                options={[
                  'BTC/USDT:USDT',
                  'ETH/USDT:USDT',
                  'SOL/USDT:USDT',
                  'BNB/USDT:USDT',
                  'XRP/USDT:USDT',
                  'DOGE/USDT:USDT',
                  'AVAX/USDT:USDT',
                  'LINK/USDT:USDT',
                  'DOT/USDT:USDT',
                  'ADA/USDT:USDT',
                  'MATIC/USDT:USDT',
                  'LTC/USDT:USDT',
                ].map((s) => ({ label: s, value: s }))}
                allowClear
              />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              name="long_exchange_id"
              label={strategyType === 'spot_hedge' ? 'Spot Exchange (buy spot)' : 'Long Exchange'}
              rules={[{ required: true }]}
            >
              <Select options={exchanges.map((e) => ({ label: e.display_name, value: e.id }))} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              name="short_exchange_id"
              label={strategyType === 'spot_hedge' ? 'Perp Exchange (short perp)' : 'Short Exchange'}
              rules={[{ required: true }]}
            >
              <Select options={exchanges.map((e) => ({ label: e.display_name, value: e.id }))} />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="size_usd" label="Margin (USDT)" rules={[{ required: true }]}>
              <InputNumber style={{ width: '100%' }} min={0} step={100} prefix="$" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="leverage" label="Leverage">
              <InputNumber style={{ width: '100%' }} min={1} max={20} step={1} suffix="x" />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item>
          <Button type="primary" htmlType="submit" block>
            Confirm Open
          </Button>
        </Form.Item>
      </Form>
    </Modal>
  );
}
