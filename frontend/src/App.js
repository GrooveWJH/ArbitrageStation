import React, { useState, useEffect } from 'react';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppLayout from './components/Layout';
import Dashboard from './pages/Dashboard';
import FundingRates from './pages/FundingRates';
import Positions from './pages/Positions';
import Settings from './pages/Settings';
import Analytics from './pages/Analytics';
import SpreadMonitor from './pages/SpreadMonitor';
import SpreadOpportunities from './pages/SpreadOpportunities';
import SpreadArb from './pages/SpreadArb';
import SpotBasisAuto from './pages/SpotBasisAuto';
import SpotBasisBacktest from './pages/SpotBasisBacktest';
import { connectWS, disconnectWS } from './services/websocket';

export default function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [wsData, setWsData] = useState(null);

  useEffect(() => {
    connectWS((msg) => setWsData(msg));
    return () => {
      disconnectWS();
    };
  }, []);

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':    return <Dashboard wsData={wsData} />;
      case 'funding-rates': return <FundingRates wsData={wsData} />;
      case 'positions':    return <Positions />;
      case 'spot-basis-auto': return <SpotBasisAuto />;
      case 'spot-basis-backtest': return <SpotBasisBacktest />;
      case 'spread-monitor': return <SpreadMonitor wsData={wsData} />;
      case 'opportunities':  return <SpreadOpportunities wsData={wsData} />;
      case 'spread-arb':     return <SpreadArb />;
      case 'analytics':      return <Analytics />;
      case 'settings':     return <Settings />;
      default:             return <Dashboard wsData={wsData} />;
    }
  };

  return (
    <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: '#1677ff' } }}>
      <AppLayout currentPage={currentPage} onNavigate={setCurrentPage}>
        {renderPage()}
      </AppLayout>
    </ConfigProvider>
  );
}
