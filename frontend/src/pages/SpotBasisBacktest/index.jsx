import React, {
  useEffect,
  useMemo,
  useState,
} from 'react';
import { Space, message } from 'antd';
import { createSpotBasisDataBacktestSearchJob } from '../../services/endpoints/spotBasisDataApi';
import {
  getSpotBasisAutoConfig,
  setSpotBasisAutoStatus,
  updateSpotBasisAutoConfig,
} from '../../services/endpoints/spotBasisApi';
import { useSpotBasisDataJobQuery } from '../../services/queries/spotBasisBacktestQueries';
import { getApiErrorMessage } from '../../utils/error';
import AutoDiffModal from './AutoDiffModal';
import BacktestSection from './BacktestSection';
import {
  AUTO_CFG_FIELD_LABELS,
  defaultParams,
  defaultSearchParams,
} from './constants';
import { buildAutoConfigPatch, buildSearchPayload } from './logic';
import SearchSection from './SearchSection';
import {
  createAutoDiffCols,
  createEventCols,
  createLeaderboardCols,
  createWindowCols,
} from './tableColumns';
import useBacktestOps from './useBacktestOps';
import {
  fmtReasonCodes,
  fmtPreviewValue,
  isSameValue,
  num,
  parseNumberList,
  statusTag,
} from './utils';

export default function SpotBasisBacktest() {
  const [params, setParams] = useState(defaultParams);
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [readiness, setReadiness] = useState(null);
  const [readinessLoading, setReadinessLoading] = useState(false);
  const [importJobId, setImportJobId] = useState(null);
  const [importJob, setImportJob] = useState(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importPath, setImportPath] = useState('');
  const [fundingImportPath, setFundingImportPath] = useState('');
  const [availableRangeLoading, setAvailableRangeLoading] = useState(false);
  const [availableRange, setAvailableRange] = useState(null);

  const [searchParams, setSearchParams] = useState(defaultSearchParams);
  const [searchJobId, setSearchJobId] = useState(null);
  const [searchJob, setSearchJob] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [applyAutoLoading, setApplyAutoLoading] = useState(false);
  const [applyAutoAndStartLoading, setApplyAutoAndStartLoading] = useState(false);
  const [autoDiffVisible, setAutoDiffVisible] = useState(false);
  const [autoDiffLoading, setAutoDiffLoading] = useState(false);
  const [autoDiffStartAfterApply, setAutoDiffStartAfterApply] = useState(false);
  const [autoDiffCurrentCfg, setAutoDiffCurrentCfg] = useState(null);
  const [autoDiffPatch, setAutoDiffPatch] = useState(null);

  const result = useMemo(() => job?.result || {}, [job]);
  const summary = result?.summary || {};
  const curve = result?.equity_curve || [];
  const events = result?.events || [];

  const searchResult = useMemo(() => searchJob?.result || {}, [searchJob]);
  const searchSummary = searchResult?.summary || {};
  const recommended = searchResult?.recommended || null;
  const leaderboard = searchResult?.leaderboard || [];
  const windows = searchResult?.windows || [];

  const autoDiffRows = useMemo(() => {
    const patch = autoDiffPatch || {};
    const current = autoDiffCurrentCfg || {};
    return Object.keys(patch).map((key) => ({
      key,
      label: AUTO_CFG_FIELD_LABELS[key] || key,
      before: current[key],
      after: patch[key],
      changed: !isSameValue(current[key], patch[key]),
    }));
  }, [autoDiffCurrentCfg, autoDiffPatch]);

  const backtestJobQuery = useSpotBasisDataJobQuery(jobId, Boolean(jobId));
  const importJobQuery = useSpotBasisDataJobQuery(importJobId, Boolean(importJobId));
  const searchJobQuery = useSpotBasisDataJobQuery(searchJobId, Boolean(searchJobId));

  const {
    checkReadiness,
    startSnapshotImport,
    startFundingImport,
    fillAvailableDates,
    startBacktest,
  } = useBacktestOps({
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
  });

  useEffect(() => {
    if (backtestJobQuery.data) setJob(backtestJobQuery.data);
  }, [backtestJobQuery.data]);

  useEffect(() => {
    if (importJobQuery.data) setImportJob(importJobQuery.data);
  }, [importJobQuery.data]);

  useEffect(() => {
    if (searchJobQuery.data) setSearchJob(searchJobQuery.data);
  }, [searchJobQuery.data]);

  useEffect(() => {
    const status = String(importJob?.status || '').toLowerCase();
    if ((status === 'succeeded' || status === 'failed') && importJob?.id && importJob.id === importJobId) {
      void checkReadiness(true);
    }
  }, [checkReadiness, importJob?.id, importJob?.status, importJobId]);

  const startSearch = async () => {
    setSearchLoading(true);
    try {
      const payload = buildSearchPayload(searchParams, parseNumberList);
      const { data } = await createSpotBasisDataBacktestSearchJob(payload);
      const j = data?.job;
      if (!j?.id) throw new Error('参数搜索任务创建失败');
      setSearchJobId(j.id);
      setSearchJob(j);
      message.success(`参数搜索任务已启动 #${j.id}`);
    } catch (e) {
      message.error(getApiErrorMessage(e, '启动参数搜索失败'));
    } finally {
      setSearchLoading(false);
    }
  };

  const refreshBacktestJob = async () => {
    if (!jobId) return;
    const res = await backtestJobQuery.refetch();
    if (res.error) message.error(getApiErrorMessage(res.error, '读取任务失败'));
  };

  const refreshSearchJob = async () => {
    if (!searchJobId) return;
    const res = await searchJobQuery.refetch();
    if (res.error) message.error(getApiErrorMessage(res.error, '读取搜索任务失败'));
  };

  const applyRecommendedToBacktest = () => {
    const rec = recommended?.params;
    if (!rec) {
      message.warning('暂无可应用的推荐参数');
      return;
    }
    setParams((p) => ({ ...p, ...rec }));
    message.success('已将推荐参数写入回测参数');
  };

  const applyRecommendedToAuto = async (startAfterApply = false, patchOverride = null) => {
    const patch = patchOverride || buildAutoConfigPatch(recommended, searchParams, num);
    if (!patch) {
      message.warning('暂无可应用的推荐参数');
      return false;
    }
    if (startAfterApply) setApplyAutoAndStartLoading(true);
    else setApplyAutoLoading(true);

    try {
      await updateSpotBasisAutoConfig(patch);
      if (startAfterApply) {
        await setSpotBasisAutoStatus({ enabled: true, dry_run: true });
        message.success('已应用推荐参数并开启自动策略（模拟模式）');
      } else {
        message.success('已应用推荐参数到自动策略配置');
      }
      return true;
    } catch (e) {
      message.error(getApiErrorMessage(e, '应用自动策略参数失败'));
      return false;
    } finally {
      if (startAfterApply) setApplyAutoAndStartLoading(false);
      else setApplyAutoLoading(false);
    }
  };

  const openAutoDiffPreview = async (startAfterApply = false) => {
    const patch = buildAutoConfigPatch(recommended, searchParams, num);
    if (!patch) {
      message.warning('暂无可应用的推荐参数');
      return;
    }
    setAutoDiffLoading(true);
    try {
      const { data } = await getSpotBasisAutoConfig();
      setAutoDiffCurrentCfg(data || {});
      setAutoDiffPatch(patch);
      setAutoDiffStartAfterApply(!!startAfterApply);
      setAutoDiffVisible(true);
    } catch (e) {
      message.error(getApiErrorMessage(e, '读取当前自动策略配置失败'));
    } finally {
      setAutoDiffLoading(false);
    }
  };

  const confirmApplyFromDiff = async () => {
    if (!autoDiffPatch) return;
    const ok = await applyRecommendedToAuto(autoDiffStartAfterApply, autoDiffPatch);
    if (ok) setAutoDiffVisible(false);
  };

  const onNumber = (key, setter) => (value) => {
    setter((p) => ({ ...p, [key]: value == null ? p[key] : value }));
  };

  const eventCols = useMemo(() => createEventCols(), []);
  const leaderboardCols = useMemo(() => createLeaderboardCols(), []);
  const windowCols = useMemo(() => createWindowCols(), []);
  const autoDiffCols = useMemo(() => createAutoDiffCols(fmtPreviewValue), []);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <BacktestSection
        params={params}
        setParams={setParams}
        onNumber={onNumber}
        importPath={importPath}
        setImportPath={setImportPath}
        fundingImportPath={fundingImportPath}
        setFundingImportPath={setFundingImportPath}
        importLoading={importLoading}
        readinessLoading={readinessLoading}
        availableRangeLoading={availableRangeLoading}
        loading={loading}
        startSnapshotImport={startSnapshotImport}
        startFundingImport={startFundingImport}
        checkReadiness={checkReadiness}
        fillAvailableDates={fillAvailableDates}
        startBacktest={startBacktest}
        refreshBacktestJob={refreshBacktestJob}
        jobId={jobId}
        job={job}
        importJobId={importJobId}
        importJob={importJob}
        readiness={readiness}
        availableRange={availableRange}
        fmtReasonCodes={fmtReasonCodes}
        statusTag={statusTag}
        summary={summary}
        curve={curve}
        events={events}
        eventCols={eventCols}
      />

      <SearchSection
        searchParams={searchParams}
        setSearchParams={setSearchParams}
        onNumber={onNumber}
        searchJobId={searchJobId}
        searchJob={searchJob}
        searchLoading={searchLoading}
        refreshSearchJob={refreshSearchJob}
        startSearch={startSearch}
        searchSummary={searchSummary}
        recommended={recommended}
        leaderboard={leaderboard}
        windows={windows}
        leaderboardCols={leaderboardCols}
        windowCols={windowCols}
        applyRecommendedToBacktest={applyRecommendedToBacktest}
        openAutoDiffPreview={openAutoDiffPreview}
        applyAutoLoading={applyAutoLoading}
        applyAutoAndStartLoading={applyAutoAndStartLoading}
        autoDiffLoading={autoDiffLoading}
        statusTag={statusTag}
      />

      <AutoDiffModal
        autoDiffVisible={autoDiffVisible}
        autoDiffStartAfterApply={autoDiffStartAfterApply}
        confirmApplyFromDiff={confirmApplyFromDiff}
        setAutoDiffVisible={setAutoDiffVisible}
        applyAutoLoading={applyAutoLoading}
        applyAutoAndStartLoading={applyAutoAndStartLoading}
        autoDiffCols={autoDiffCols}
        autoDiffRows={autoDiffRows}
      />
    </Space>
  );
}
