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
import ExchangeLogoName from '../../components/ExchangeLogoName';

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
    <Modal title="新建策略" open={open} onCancel={onCancel} footer={null} width={700}>
      {strategyType === 'cross_exchange' && opportunities.length > 0 && (
        <Card size="small" title={<><ThunderboltOutlined /> 跨所机会（Top）</>} style={{ marginBottom: 16 }}>
          <Table
            dataSource={opportunities.slice(0, 5)}
            size="small"
            pagination={false}
            rowKey="symbol"
            columns={[
              { title: '交易对', dataIndex: 'symbol' },
              {
                title: '做多交易所',
                dataIndex: 'long_exchange',
                render: (v, r) => <ExchangeLogoName name={v} exchangeId={r.long_exchange_id} />,
              },
              {
                title: '做空交易所',
                dataIndex: 'short_exchange',
                render: (v, r) => <ExchangeLogoName name={v} exchangeId={r.short_exchange_id} />,
              },
              { title: '年化', dataIndex: 'annualized_pct', render: (v) => `${v.toFixed(1)}%` },
              {
                title: '',
                key: 'fill',
                render: (_, r) => (
                  <Button size="small" onClick={() => fillFromOpportunity(r)}>
                    填充
                  </Button>
                ),
              },
            ]}
          />
        </Card>
      )}

      {strategyType === 'spot_hedge' && spotOpportunities.length > 0 && (
        <Card size="small" title={<><ThunderboltOutlined /> 现货-合约机会（Top）</>} style={{ marginBottom: 16 }}>
          <Table
            dataSource={spotOpportunities.slice(0, 5)}
            size="small"
            pagination={false}
            rowKey={(r) =>
              `${r.symbol}-${r.long_exchange_id ?? r.spot_exchange_id ?? r.exchange_id}-${r.short_exchange_id ?? r.perp_exchange_id ?? r.exchange_id}`
            }
            columns={[
              { title: '交易对', dataIndex: 'symbol' },
              {
                title: '现货交易所',
                dataIndex: 'long_exchange',
                render: (v, r) => <ExchangeLogoName name={v} exchangeId={r.long_exchange_id ?? r.spot_exchange_id} />,
              },
              {
                title: '合约交易所',
                dataIndex: 'short_exchange',
                render: (v, r) => <ExchangeLogoName name={v} exchangeId={r.short_exchange_id ?? r.perp_exchange_id} />,
              },
              { title: '费率', dataIndex: 'rate_pct', render: (v) => `${v > 0 ? '+' : ''}${v.toFixed(4)}%` },
              { title: '年化', dataIndex: 'annualized_pct', render: (v) => `${v.toFixed(1)}%` },
              {
                title: '',
                key: 'fill',
                render: (_, r) => (
                  <Button size="small" onClick={() => fillFromSpotOpportunity(r)}>
                    填充
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
            <Form.Item name="strategy_type" label="策略类型" rules={[{ required: true }]}>
              <Select
                options={[
                  { label: '跨所套利 - 多低费率 / 空高费率', value: 'cross_exchange' },
                  { label: '现货对冲 - 买现货 + 空合约', value: 'spot_hedge' },
                ]}
              />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              name="symbol"
              label={strategyType === 'spot_hedge' ? '合约交易对' : '交易对'}
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
              label={strategyType === 'spot_hedge' ? '现货交易所（买现货）' : '做多交易所'}
              rules={[{ required: true }]}
            >
              <Select options={exchanges.map((e) => ({ label: e.display_name, value: e.id }))} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              name="short_exchange_id"
              label={strategyType === 'spot_hedge' ? '合约交易所（空合约）' : '做空交易所'}
              rules={[{ required: true }]}
            >
              <Select options={exchanges.map((e) => ({ label: e.display_name, value: e.id }))} />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="size_usd" label="保证金 (USDT)" rules={[{ required: true }]}>
              <InputNumber style={{ width: '100%' }} min={0} step={100} prefix="$" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="leverage" label="杠杆">
              <InputNumber style={{ width: '100%' }} min={1} max={20} step={1} suffix="x" />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item>
          <Button type="primary" htmlType="submit" block>
            确认开仓
          </Button>
        </Form.Item>
      </Form>
    </Modal>
  );
}
