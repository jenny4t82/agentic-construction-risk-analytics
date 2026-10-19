import { useState, useEffect, useCallback } from 'react';
import { Navbar } from './components/Navbar';
import { OverviewCards } from './components/OverviewCards';
import { ImageUploader } from './components/ImageUploader';
import { AssessmentResults } from './components/AssessmentResults';
import { ObservationHistory } from './components/ObservationHistory';
import {
  checkBackendHealth,
  submitImageAssessment,
  fetchObservations,
} from './api/client';
import type {
  AssessmentsResponse,
  ImageAssessmentParams,
  ObservationDetailResponse,
} from './types';

export function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'history'>('dashboard');
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(false);
  const [isDatabaseConfigured, setIsDatabaseConfigured] = useState<boolean>(false);

  // Assessment upload state
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [assessmentError, setAssessmentError] = useState<string | null>(null);
  const [latestAssessment, setLatestAssessment] = useState<AssessmentsResponse | null>(null);

  // History state
  const [observations, setObservations] = useState<ObservationDetailResponse[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState<boolean>(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  // Check health and load history
  const loadHistory = useCallback(async () => {
    setIsHistoryLoading(true);
    setHistoryError(null);
    const result = await fetchObservations(20, 0);
    setObservations(result.data);
    setIsDatabaseConfigured(result.isDatabaseConfigured);
    setHistoryError(result.error);
    setIsHistoryLoading(false);
  }, []);

  useEffect(() => {
    // Health check polling
    const checkHealth = async () => {
      const healthy = await checkBackendHealth();
      setIsBackendHealthy(healthy);
    };

    const init = async () => {
      await checkHealth();
      await loadHistory();
    };
    init();

    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, [loadHistory]);

  const handleAnalyzeImage = async (file: File, params: ImageAssessmentParams) => {
    setIsAnalyzing(true);
    setAssessmentError(null);
    try {
      const response = await submitImageAssessment(file, params);
      setLatestAssessment(response);
      // Refresh history in case persistence is enabled
      await loadHistory();
    } catch (err) {
      setAssessmentError(
        err instanceof Error ? err.message : 'Visual hazard assessment failed'
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <Navbar
        isBackendHealthy={isBackendHealthy}
        isDatabaseConfigured={isDatabaseConfigured}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* KPI Summary Cards */}
        <OverviewCards
          observations={observations}
          latestAssessment={latestAssessment}
          isDatabaseConfigured={isDatabaseConfigured}
        />

        {/* Tab 1: Dashboard / Assessment View */}
        {activeTab === 'dashboard' && (
          <div>
            <ImageUploader
              onAnalyze={handleAnalyzeImage}
              isLoading={isAnalyzing}
              error={assessmentError}
            />

            {latestAssessment && <AssessmentResults assessment={latestAssessment} />}

            {/* Quick preview of history on dashboard */}
            <div className="mt-8">
              <ObservationHistory
                observations={observations}
                isLoading={isHistoryLoading}
                isDatabaseConfigured={isDatabaseConfigured}
                error={historyError}
                onRefresh={loadHistory}
              />
            </div>
          </div>
        )}

        {/* Tab 2: Full History View */}
        {activeTab === 'history' && (
          <ObservationHistory
            observations={observations}
            isLoading={isHistoryLoading}
            isDatabaseConfigured={isDatabaseConfigured}
            error={historyError}
            onRefresh={loadHistory}
          />
        )}
      </main>

      {/* Educational Disclaimer Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 text-center text-xs text-slate-400">
        <p className="max-w-2xl mx-auto px-4">
          SafeSite Risk Intelligence Platform • Educational rule-based scoring (Severity × Likelihood ×
          Exposure). This system is a prototype and not an official regulatory OSHA standard or
          statistical accident probability calculator.
        </p>
      </footer>
    </div>
  );
}

export default App;
