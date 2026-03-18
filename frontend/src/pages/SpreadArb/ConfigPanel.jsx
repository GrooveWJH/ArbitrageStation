import React, {
  useEffect,
  useRef,
  useState,
} from 'react';
import {
  Button,
  Card,
  Col,
  InputNumber,
  Row,
  Select,
  Switch,
  Tooltip,
} from 'antd';
import { SettingOutlined } from '@ant-design/icons';

export default function ConfigPanel({
  cfg,
  onSave,
  saving,
}) {
  const [local, setLocal] = useState(null);
  const didInit = useRef(false);

  useEffect(() => {
    if (cfg && !didInit.current) {
      setLocal(cfg);
      didInit.current = true;
    }
  }, [cfg]);

  const set = (k, v) => setLocal((p) => ({ ...p, [k]: v }));
  if (!local) return null;

  return (
    <Card size="small" title={<><SettingOutlined /> 价差套利配置</>} style={{ marginBottom: 16 }}>
      <Row gutter={[16, 12]}>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="当前价差 z分数 ≥ 此值时入场">入场 z 阈值 ℹ</Tooltip>
          </div>
          <InputNumber
            value={local.spread_entry_z}
            onChange={(v) => set('spread_entry_z', v)}
            min={0.5}
            max={5}
            step={0.1}
            precision={1}
            style={{ width: '100%' }}
          />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="z分数回落至此值时平仓（价差回归均值）">出场 z 阈值 ℹ</Tooltip>
          </div>
          <InputNumber
            value={local.spread_exit_z}
            onChange={(v) => set('spread_exit_z', v)}
            min={-1}
            max={2}
            step={0.1}
            precision={1}
            style={{ width: '100%' }}
          />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="止损 z = 入场时z + δ。入场z越高止损线自动上移，避免高z入场时倒挂。示例：入场z=3.4，δ=1.5 → 止损z=4.9">
              止损偏移 δ ℹ
            </Tooltip>
          </div>
          <InputNumber
            value={local.spread_stop_z_delta}
            onChange={(v) => set('spread_stop_z_delta', v)}
            min={0.1}
            max={5}
            step={0.1}
            precision={1}
            style={{ width: '100%' }}
            addonAfter="σ"
          />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="浮动止盈 z = 入场时z - δ。价差收敛到此z即止盈，早于完全均值回归。默认3.0，即入场z=7时在z=4止盈。">
              止盈偏移 δ ℹ
            </Tooltip>
          </div>
          <InputNumber
            value={local.spread_tp_z_delta}
            onChange={(v) => set('spread_tp_z_delta', v)}
            min={0.5}
            max={10}
            step={0.5}
            precision={1}
            style={{ width: '100%' }}
            addonAfter="σ"
          />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="结算前N分钟平仓，避免价格波动风险">结算前平仓(分钟) ℹ</Tooltip>
          </div>
          <InputNumber
            value={local.spread_pre_settle_mins}
            onChange={(v) => set('spread_pre_settle_mins', v)}
            min={1}
            max={60}
            step={1}
            style={{ width: '100%' }}
          />
        </Col>

        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="每笔仓位使用「可用余额」的百分比（可用=总余额-费率套利占用）">仓位占比(%) ℹ</Tooltip>
          </div>
          <InputNumber
            value={local.spread_position_pct}
            onChange={(v) => set('spread_position_pct', v)}
            min={1}
            max={100}
            step={1}
            precision={1}
            suffix="%"
            style={{ width: '100%' }}
          />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="价差套利专属上限（两种策略共用「总上限」）">价差仓位上限 ℹ</Tooltip>
          </div>
          <InputNumber
            value={local.spread_max_positions}
            onChange={(v) => set('spread_max_positions', v)}
            min={1}
            max={20}
            step={1}
            style={{ width: '100%' }}
          />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="两腿中较小成交量须达到此值才入场（0=不限制）">最小24h成交量 ℹ</Tooltip>
          </div>
          <InputNumber
            value={local.spread_min_volume_usd}
            onChange={(v) => set('spread_min_volume_usd', v || 0)}
            min={0}
            step={100000}
            formatter={(v) => (v ? `$${Number(v).toLocaleString()}` : '$0')}
            parser={(v) => Number((v || '0').replace(/[^0-9]/g, ''))}
            style={{ width: '100%' }}
          />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="止损平仓后，该对子在N分钟内不再入场（冷静期）">止损冷静期(分钟) ℹ</Tooltip>
          </div>
          <InputNumber
            value={local.spread_cooldown_mins}
            onChange={(v) => set('spread_cooldown_mins', v)}
            min={0}
            max={1440}
            step={5}
            style={{ width: '100%' }}
          />
        </Col>

        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="费率套利 + 价差套利 合计最多同时持有的「策略个数」上限（不是 USD，与费率套利自动交易页面互通）">
              总策略数上限（共用）ℹ
            </Tooltip>
          </div>
          <InputNumber
            value={local.max_open_strategies}
            onChange={(v) => set('max_open_strategies', v)}
            min={1}
            max={50}
            step={1}
            style={{ width: '100%' }}
            addonAfter="个"
          />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>下单类型</div>
          <Select value={local.spread_order_type} onChange={(v) => set('spread_order_type', v)} style={{ width: '100%' }}>
            <Select.Option value="market">市价单 (立即成交)</Select.Option>
            <Select.Option value="limit">限价单 (当前价)</Select.Option>
          </Select>
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="关闭后，若价差套利方向与同交易所同币种的费率套利方向相反，则跳过该机会（无需交易所开启双向持仓模式）">
              双向持仓模式 ℹ
            </Tooltip>
          </div>
          <Switch
            checked={local.spread_use_hedge_mode ?? true}
            onChange={(v) => set('spread_use_hedge_mode', v)}
            checkedChildren="开启"
            unCheckedChildren="关闭"
          />
          <div style={{ fontSize: 11, color: '#aaa', marginTop: 4 }}>
            {local.spread_use_hedge_mode ?? true ? '独立建仓，与费率套利方向无关' : '跳过与费率套利方向冲突的机会'}
          </div>
        </Col>
        <Col span={6} style={{ display: 'flex', alignItems: 'flex-end' }}>
          <Button type="primary" loading={saving} onClick={() => onSave(local)} block>
            保存配置
          </Button>
        </Col>
      </Row>
    </Card>
  );
}
