import React from 'react';
import {
  Alert,
  Button,
  List,
  Modal,
  Space,
} from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleFilled,
  ThunderboltOutlined,
} from '@ant-design/icons';

export default function HedgeSetupModal({
  hedgeModal,
  onClose,
}) {
  return (
    <Modal
      title={(
        <Space>
          <ThunderboltOutlined style={{ color: '#faad14' }} />
          对冲模式初始化结果
        </Space>
      )}
      open={hedgeModal !== null}
      onCancel={onClose}
      footer={[
        <Button key="ok" type="primary" onClick={onClose}>确定</Button>,
      ]}
    >
      {hedgeModal?.loading ? (
        <div style={{ textAlign: 'center', padding: '24px 0', color: '#888' }}>
          正在初始化各交易所对冲模式，请稍候…
        </div>
      ) : hedgeModal?.error ? (
        <Alert type="error" message={hedgeModal.error} showIcon />
      ) : hedgeModal?.results && Object.keys(hedgeModal.results).length === 0 ? (
        <Alert type="warning" message="未找到已连接的活跃交易所，请先在「交易所」页面添加并启用交易所。" showIcon />
      ) : (
        <List
          dataSource={Object.entries(hedgeModal?.results || {})}
          renderItem={([name, ok]) => (
            <List.Item>
              <List.Item.Meta
                avatar={ok
                  ? <CheckCircleOutlined style={{ fontSize: 20, color: '#3f8600' }} />
                  : <CloseCircleFilled style={{ fontSize: 20, color: '#cf1322' }} />}
                title={<span style={{ fontWeight: 600 }}>{name}</span>}
                description={ok
                  ? <span style={{ color: '#3f8600' }}>双向持仓模式已开启</span>
                  : <span style={{ color: '#cf1322' }}>初始化失败，请检查 API 权限或手动设置</span>}
              />
            </List.Item>
          )}
        />
      )}
    </Modal>
  );
}
