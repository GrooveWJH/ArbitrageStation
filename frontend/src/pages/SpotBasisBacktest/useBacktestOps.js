import { useCallback } from 'react';
import { message } from 'antd';
import {
  createSpotBasisDataBacktestJob,
  getSpotBasisBacktestReadiness,
  getSpotBasisDataAvailableRange,
  importSpotBasisFunding,
  importSpotBasisSnapshots,
} from '../../services/endpoints/spotBasisDataApi';
import { getApiErrorMessage } from '../../utils/error';
import { fmtReasonCodes, num } from './utils';

export default function useBacktestOps({
  params,
  setParams,
  importPath,
  fundingImportPath,
  setReadiness,
  setReadinessLoading,
  setImportLoading,
  setImportJobId,
  setImportJob,
  setAvailableRangeLoading,
  setAvailableRange,
  setLoading,
  setJobId,
  setJob,
}) {
  const buildReadinessParams = useCallback(
    () => ({
      start_date: params.start_date || undefined,
      end_date: params.end_date || undefined,
      days: Math.max(1, Math.trunc(num(params.days, 15))),
      top_n: Math.max(1, Math.trunc(num(params.top_n, 120))),
    }),
    [params],
  );

  const checkReadiness = useCallback(async (silent = false) => {
    setReadinessLoading(true);
    try {
      const { data } = await getSpotBasisBacktestReadiness(buildReadinessParams());
      const next = data?.result || null;
      setReadiness(next);
      return next;
    } catch (e) {
      if (!silent) message.error(getApiErrorMessage(e, '读取回测覆盖检查失败'));
      return null;
    } finally {
      setReadinessLoading(false);
    }
  }, [buildReadinessParams, setReadiness, setReadinessLoading]);

  const startPathImport = useCallback(async (kind = 'snapshots') => {
    const isFunding = String(kind || '').toLowerCase() === 'funding';
    const p = String(isFunding ? fundingImportPath : importPath || '').trim();
    if (!p) {
      message.warning('请先输入本地文件路径');
      return;
    }
    setImportLoading(true);
    try {
      const name = p.split('\\').pop().split('/').pop();
      const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
      const fmt = ext === 'parquet' ? 'parquet' : 'csv';
      const importer = isFunding ? importSpotBasisFunding : importSpotBasisSnapshots;
      const { data } = await importer({ file_path: p, file_format: fmt });
      const j = data?.job;
      if (!j?.id) throw new Error('导入任务创建失败');
      setImportJobId(j.id);
      setImportJob(j);
      message.success(`${isFunding ? 'Funding历史' : '快照'}导入任务已启动 #${j.id}`);
    } catch (e) {
      message.error(getApiErrorMessage(e, `启动${isFunding ? 'Funding历史' : '快照'}导入失败`));
    } finally {
      setImportLoading(false);
    }
  }, [fundingImportPath, importPath, setImportLoading, setImportJob, setImportJobId]);

  const startSnapshotImport = useCallback(() => {
    void startPathImport('snapshots');
  }, [startPathImport]);

  const startFundingImport = useCallback(() => {
    void startPathImport('funding');
  }, [startPathImport]);

  const fillAvailableDates = useCallback(async () => {
    setAvailableRangeLoading(true);
    try {
      const preferredDays = Math.max(1, Math.trunc(num(params.days, 15)));
      const { data } = await getSpotBasisDataAvailableRange({ preferred_days: preferredDays });
      const next = data?.result || null;
      setAvailableRange(next);
      const start = next?.recommended_start_date;
      const end = next?.recommended_end_date;
      if (!start || !end) {
        message.warning('当前暂无可用的连续日期区间，请先导入 funding 与 15m 快照');
        return;
      }
      setParams((p) => ({ ...p, start_date: start, end_date: end }));
      message.success(`已自动填充回测日期: ${start} ~ ${end}`);
      setReadiness(null);
    } catch (e) {
      message.error(getApiErrorMessage(e, '读取可用日期范围失败'));
    } finally {
      setAvailableRangeLoading(false);
    }
  }, [params.days, setAvailableRange, setAvailableRangeLoading, setParams, setReadiness]);

  const startBacktest = useCallback(async () => {
    setLoading(true);
    try {
      const rd = await checkReadiness(true);
      if (rd && rd.ready === false) {
        message.error(`回测前检查未通过：${fmtReasonCodes(rd.reason_codes)}`);
        return;
      }
      if (rd && Array.isArray(rd.reason_codes) && rd.reason_codes.includes('snapshot_coverage_low')) {
        message.warning('回测数据覆盖偏低，结果可能不稳定');
      }
      const { data } = await createSpotBasisDataBacktestJob(params);
      const j = data?.job;
      if (!j?.id) throw new Error('任务创建失败');
      setJobId(j.id);
      setJob(j);
      message.success(`回测任务已启动 #${j.id}`);
    } catch (e) {
      message.error(getApiErrorMessage(e, '启动回测失败'));
    } finally {
      setLoading(false);
    }
  }, [checkReadiness, params, setJob, setJobId, setLoading]);

  return {
    checkReadiness,
    startSnapshotImport,
    startFundingImport,
    fillAvailableDates,
    startBacktest,
  };
}
