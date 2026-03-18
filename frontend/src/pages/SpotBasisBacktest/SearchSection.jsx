import React from 'react';
import {
  Button,
  Card,
  Col,
  Empty,
  Input,
  InputNumber,
  Progress,
  Row,
  Space,
  Statistic,
  Tag,
  Table,
  Typography,
} from 'antd';
import {
  PlayCircleOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { num } from './utils';

const { Title, Text } = Typography;

export default function SearchSection({
  searchParams,
  setSearchParams,
  onNumber,
  searchJobId,
  searchJob,
  searchLoading,
  refreshSearchJob,
  startSearch,
  searchSummary,
  recommended,
  leaderboard,
  windows,
  leaderboardCols,
  windowCols,
  applyRecommendedToBacktest,
  openAutoDiffPreview,
  applyAutoLoading,
  applyAutoAndStartLoading,
  autoDiffLoading,
  statusTag,
}) {
  return (
    <>
      <Card>
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <SearchOutlined style={{ color: '#1677ff' }} />
            <Title level={5} style={{ margin: 0 }}>Walk-forward 参数搜索</Title>
          </Space>
          <Space>
            <Button icon={<ReloadOutlined />} disabled={!searchJobId} onClick={() => { void refreshSearchJob(); }}>
              刷新搜索
            </Button>
            <Button type="primary" loading={searchLoading} icon={<PlayCircleOutlined />} onClick={() => { void startSearch(); }}>
              启动参数搜索
            </Button>
          </Space>
        </Space>

        <Text type="secondary">列表类参数使用逗号分隔，例如: 0,5,10,15</Text>

        <Row gutter={[12, 12]} style={{ marginTop: 14 }}>
          <Col span={6}><Text>开始日期(YYYY-MM-DD)</Text><Input value={searchParams.start_date} onChange={(e) => setSearchParams((p) => ({ ...p, start_date: e.target.value }))} placeholder="留空按 days" /></Col>
          <Col span={6}><Text>结束日期(YYYY-MM-DD)</Text><Input value={searchParams.end_date} onChange={(e) => setSearchParams((p) => ({ ...p, end_date: e.target.value }))} placeholder="留空为今天" /></Col>
          <Col span={4}><Text>搜索天数</Text><InputNumber min={10} max={365} value={searchParams.days} onChange={onNumber('days', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>机会池TopN</Text><InputNumber min={1} max={2000} value={searchParams.top_n} onChange={onNumber('top_n', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>初始资金</Text><InputNumber min={100} value={searchParams.initial_nav_usd} onChange={onNumber('initial_nav_usd', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>训练天数</Text><InputNumber min={1} max={90} value={searchParams.train_days} onChange={onNumber('train_days', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>测试天数</Text><InputNumber min={1} max={30} value={searchParams.test_days} onChange={onNumber('test_days', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>步长天数</Text><InputNumber min={1} max={30} value={searchParams.step_days} onChange={onNumber('step_days', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>每窗入围K</Text><InputNumber min={1} max={20} value={searchParams.train_top_k} onChange={onNumber('train_top_k', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>最大试验组</Text><InputNumber min={1} max={300} value={searchParams.max_trials} onChange={onNumber('max_trials', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>随机种子</Text><InputNumber min={1} value={searchParams.random_seed} onChange={onNumber('random_seed', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={8}><Text>入场评分候选</Text><Input value={searchParams.enter_score_threshold_values} onChange={(e) => setSearchParams((p) => ({ ...p, enter_score_threshold_values: e.target.value }))} /></Col>
          <Col span={8}><Text>入场置信度候选</Text><Input value={searchParams.entry_conf_min_values} onChange={(e) => setSearchParams((p) => ({ ...p, entry_conf_min_values: e.target.value }))} /></Col>
          <Col span={8}><Text>最大持仓对数候选</Text><Input value={searchParams.max_open_pairs_values} onChange={(e) => setSearchParams((p) => ({ ...p, max_open_pairs_values: e.target.value }))} /></Col>
          <Col span={8}><Text>利用率候选(%)</Text><Input value={searchParams.target_utilization_pct_values} onChange={(e) => setSearchParams((p) => ({ ...p, target_utilization_pct_values: e.target.value }))} /></Col>
          <Col span={8}><Text>最小单对本金候选</Text><Input value={searchParams.min_pair_notional_usd_values} onChange={(e) => setSearchParams((p) => ({ ...p, min_pair_notional_usd_values: e.target.value }))} /></Col>
          <Col span={8}><Text>冲击成本上限候选(%)</Text><Input value={searchParams.max_impact_pct_values} onChange={(e) => setSearchParams((p) => ({ ...p, max_impact_pct_values: e.target.value }))} /></Col>
          <Col span={8}><Text>换仓确认轮数候选</Text><Input value={searchParams.switch_confirm_rounds_values} onChange={(e) => setSearchParams((p) => ({ ...p, switch_confirm_rounds_values: e.target.value }))} /></Col>
          <Col span={8}><Text>相对增益门槛候选(%)</Text><Input value={searchParams.rebalance_min_relative_adv_pct_values} onChange={(e) => setSearchParams((p) => ({ ...p, rebalance_min_relative_adv_pct_values: e.target.value }))} /></Col>
          <Col span={8}><Text>绝对增益门槛候选(USD/天)</Text><Input value={searchParams.rebalance_min_absolute_adv_usd_day_values} onChange={(e) => setSearchParams((p) => ({ ...p, rebalance_min_absolute_adv_usd_day_values: e.target.value }))} /></Col>
        </Row>
      </Card>

      <Card>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Text strong>搜索任务ID: {searchJobId || '--'}</Text>
            {statusTag(searchJob?.status)}
            <Text type="secondary">{searchJob?.message || ''}</Text>
          </Space>
          <Text type="secondary">更新时间: {searchJob?.updated_at ? new Date(searchJob.updated_at).toLocaleString('zh-CN') : '--'}</Text>
        </Space>
        <Progress percent={Math.round(num(searchJob?.progress, 0) * 100)} style={{ marginTop: 10 }} />
      </Card>

      <Card title="参数搜索结果">
        <Row gutter={[12, 12]}>
          <Col span={6}><Statistic title="时间范围" value={`${searchSummary.start_date || '--'} ~ ${searchSummary.end_date || '--'}`} /></Col>
          <Col span={6}><Statistic title="窗口数量" value={num(searchSummary.windows, 0)} /></Col>
          <Col span={6}><Statistic title="参数组数量" value={num(searchSummary.combos_evaluated, 0)} /></Col>
          <Col span={6}><Statistic title="每窗入围K" value={num(searchSummary.train_top_k, 0)} /></Col>
        </Row>

        <Card size="small" style={{ marginTop: 12 }} title="推荐参数组">
          {!recommended ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无推荐参数" />
          ) : (
            <Space direction="vertical" style={{ width: '100%' }}>
              <Space>
                <Tag color="blue">参数组 {recommended.combo_id}</Tag>
                <Tag color="green">稳定评分 {num(recommended.stability_score).toFixed(4)}</Tag>
                <Tag color="purple">均值收益 {num(recommended.avg_test_return_pct).toFixed(4)}%</Tag>
                <Tag color="gold">收益波动 {num(recommended.std_test_return_pct).toFixed(4)}%</Tag>
                <Tag color="red">平均回撤 {num(recommended.avg_test_drawdown_pct).toFixed(4)}%</Tag>
              </Space>
              <Space size={[4, 4]} wrap>
                {Object.entries(recommended.params || {}).map(([k, v]) => (
                  <Tag key={k}>{`${k}: ${v}`}</Tag>
                ))}
              </Space>
              <Space wrap>
                <Button onClick={applyRecommendedToBacktest}>应用到上方回测参数</Button>
                <Button loading={applyAutoLoading || autoDiffLoading} onClick={() => openAutoDiffPreview(false)}>
                  应用到自动策略配置
                </Button>
                <Button type="primary" loading={applyAutoAndStartLoading || autoDiffLoading} onClick={() => openAutoDiffPreview(true)}>
                  应用并开启自动策略(模拟)
                </Button>
              </Space>
            </Space>
          )}
        </Card>

        <Card size="small" style={{ marginTop: 12 }} title={`稳定性榜单 (${leaderboard.length})`}>
          <Table
            size="small"
            rowKey={(r) => String(r.combo_id || '')}
            columns={leaderboardCols}
            dataSource={leaderboard}
            pagination={{ pageSize: 8, showSizeChanger: false }}
            scroll={{ x: 1200 }}
          />
        </Card>

        <Card size="small" style={{ marginTop: 12 }} title={`窗口结果 (${windows.length})`}>
          <Table
            size="small"
            rowKey={(r) => `w-${r.window_index || ''}`}
            columns={windowCols}
            dataSource={windows}
            pagination={{ pageSize: 8, showSizeChanger: false }}
            scroll={{ x: 1100 }}
          />
        </Card>
      </Card>
    </>
  );
}
