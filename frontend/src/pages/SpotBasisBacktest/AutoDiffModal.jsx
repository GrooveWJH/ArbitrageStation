import React from 'react';
import {
  Alert,
  Modal,
  Table,
} from 'antd';

export default function AutoDiffModal({
  autoDiffVisible,
  autoDiffStartAfterApply,
  confirmApplyFromDiff,
  setAutoDiffVisible,
  applyAutoLoading,
  applyAutoAndStartLoading,
  autoDiffCols,
  autoDiffRows,
}) {
  return (
    <Modal
      title={autoDiffStartAfterApply ? '确认应用参数并开启自动策略(模拟)' : '确认应用参数到自动策略'}
      open={autoDiffVisible}
      onCancel={() => setAutoDiffVisible(false)}
      onOk={confirmApplyFromDiff}
      okText={autoDiffStartAfterApply ? '确认并开启(模拟)' : '确认应用'}
      cancelText="取消"
      confirmLoading={applyAutoLoading || applyAutoAndStartLoading}
      width={980}
    >
      {autoDiffStartAfterApply ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="将同时开启自动策略，且默认以模拟模式运行（dry_run=true）。"
        />
      ) : null}
      <Table
        size="small"
        rowKey={(r) => String(r.key || '')}
        columns={autoDiffCols}
        dataSource={autoDiffRows}
        pagination={false}
        scroll={{ x: 760, y: 420 }}
      />
    </Modal>
  );
}
