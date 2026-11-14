import { useCallback, useEffect, useState } from 'react';
import { incidentTarget } from './utils/incidentNavigation';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { LoginPage, SignupPage } from './auth/AuthPages';
import { checkBackendHealth, fetchAlerts, fetchObservationDetail, fetchObservations, submitImageAssessment } from './api/client';
import { AlertsPage } from './components/AlertsPage';
import { AppShell, type AppSection } from './components/AppShell';
import { AssessmentResults } from './components/AssessmentResults';
import { ImageUploader } from './components/ImageUploader';
import { ObservationHistory } from './components/ObservationHistory';
import { OverviewPage } from './components/OverviewPage';
import { ObservationRow } from './components/ObservationRow';
import { RecurrenceAnalyticsPage } from './components/RecurrenceAnalyticsPage';
import { ReportsPage } from './components/ReportsPage';
import { ZoneAnalyticsPage } from './components/ZoneAnalyticsPage';
import type { AlertDetailResponse, AssessmentsResponse, ImageAssessmentParams, ObservationDetailResponse } from './types';

type AuthRoute = 'login' | 'signup';
const readRoute = (): AppSection | AuthRoute => {
  const hash = typeof window === 'undefined' ? '' : window.location.hash.slice(1).split('?')[0];
  if (hash === 'login' || hash === 'signup') return hash;
  if (hash === 'incidents' || hash === 'history' || hash === 'alerts' || hash === 'zones' || hash === 'recurrence' || hash === 'reports' || hash === 'analysis' || hash === 'experimental') return hash === 'history' ? 'incidents' : hash === 'experimental' ? 'analysis' : hash;
  if (typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('tab') === 'experimental') return 'analysis';
  return 'overview';
};

function SafetyWorkspace({ view, onNavigate }: { view: 'analysis' | 'incidents'; onNavigate: (section: AppSection) => void }) {
  const [isBackendHealthy, setIsBackendHealthy] = useState(false);
  const [isDatabaseConfigured, setIsDatabaseConfigured] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [assessmentError, setAssessmentError] = useState<string | null>(null);
  const [latestAssessment, setLatestAssessment] = useState<AssessmentsResponse | null>(null);
  const [latestObservation, setLatestObservation] = useState<ObservationDetailResponse | null>(null);
  const [latestAlerts, setLatestAlerts] = useState<AlertDetailResponse[]>([]);
  const [observations, setObservations] = useState<ObservationDetailResponse[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const recoveryKey = 'safesite.pending-analysis';
  useEffect(() => {
    const id = sessionStorage.getItem(recoveryKey);
    if (view !== 'analysis' || !id) return;
    let active = true;
    void fetchObservationDetail(id).then(obs => { if (active) setLatestObservation(obs); })
      .catch(reason => { if (active) setHistoryError(reason instanceof Error ? reason.message : 'Unable to restore saved observation'); });
    return () => { active = false; };
  }, [view]);

  const loadHistory = useCallback(async () => {
    setIsHistoryLoading(true);
    try {
      const result = await fetchObservations(20, 0);
      const target = incidentTarget();
      if (view === 'incidents' && target.observationId) {
        const observation = await fetchObservationDetail(target.observationId);
        if (target.assessmentId && !observation.detected_hazards.some((hazard) => hazard.assessments.some((assessment) => String(assessment.assessment_id) === target.assessmentId))) {
          throw new Error('The requested assessment does not belong to this observation');
        }
        result.data = [observation];
      }
      setObservations(result.data);
      setIsDatabaseConfigured(result.isDatabaseConfigured);
      setHistoryError(result.error);
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : 'Unable to load observation');
    } finally {
      setIsHistoryLoading(false);
    }
  }, [view]);

  useEffect(() => { window.addEventListener('hashchange', loadHistory); return () => window.removeEventListener('hashchange', loadHistory); }, [loadHistory]);

  useEffect(() => {
    const check = async () => setIsBackendHealthy(await checkBackendHealth());
    void check();
    void loadHistory();
    const interval = setInterval(check, 15000);
    return () => clearInterval(interval);
  }, [loadHistory]);

  const analyze = async (file: File, params: ImageAssessmentParams) => {
    setIsAnalyzing(true);
    setAssessmentError(null);
    setLatestAssessment(null);
    setLatestObservation(null);
    setLatestAlerts([]);
    sessionStorage.removeItem(recoveryKey);
    try {
      const result = await submitImageAssessment(file, params);
      setLatestAssessment(result);
      sessionStorage.setItem(recoveryKey, result.observation_id);
      await loadHistory();
      try {
        setLatestObservation(await fetchObservationDetail(result.observation_id));
        if (result.safety_decision.outcome === 'alert') {
          setLatestAlerts(await fetchAlerts(result.observation_id));
        }
      } catch (reason) {
        setHistoryError(reason instanceof Error ? reason.message : 'Unable to load the saved observation');
      }
    } catch (reason) {
      setAssessmentError(reason instanceof Error ? reason.message : 'Visual hazard assessment failed');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const onCompleted = (observationId: string) => {
    setLatestAssessment(null);
    void loadHistory();
    void fetchObservationDetail(observationId).then(setLatestObservation).catch((reason) => {
      setHistoryError(reason instanceof Error ? reason.message : 'Unable to refresh the saved observation');
    });
  };

  if (view === 'incidents') {
    return (
      <ObservationHistory
        observations={observations}
        onNavigate={onNavigate}
        onRefresh={loadHistory}
        onAssessmentCompleted={(observationId) => {
          if (latestAssessment?.observation_id === observationId) setLatestAssessment(null);
          void loadHistory();
        }}
        onWorkAreaUpdated={(updated) => {
          setObservations((current) =>
            current.map((item) => (item.observation_id === updated.observation_id ? updated : item))
          );
        }}
      />
    );
  }

  return <div className="space-y-7">
    <div><p className="text-sm text-teal-700 font-bold">Persisted image assessment</p><h2 className="text-3xl font-bold mt-1">AI Safety Analysis</h2><p className="text-slate-500 mt-2">Upload a construction-site image to identify supported PPE violations, assess risk, and record findings for review.</p></div>
    {(!isDatabaseConfigured || !isBackendHealthy) && !isHistoryLoading && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Persisted analysis is unavailable until the database connection is restored.</p>}
    {historyError && !assessmentError && <p role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{historyError}</p>}
    {isDatabaseConfigured && <ImageUploader onAnalyze={analyze} isLoading={isAnalyzing} error={assessmentError} onClear={() => { sessionStorage.removeItem(recoveryKey); setLatestAssessment(null); setLatestObservation(null); setLatestAlerts([]); }} />}
    {latestAssessment && !latestObservation && latestAssessment.safety_decision.outcome !== 'pending' && <>
      <AssessmentResults assessment={latestAssessment} />
      <section className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">
        <p>Saved as Observation <strong>{latestAssessment.observation_id}</strong>.</p>
        <div className="mt-2 flex flex-wrap gap-4">
          <button onClick={() => onNavigate('incidents')} className="font-semibold underline">View in Observation History</button>
          {latestAlerts.length > 0 && <button onClick={() => onNavigate('alerts')} className="font-semibold underline">View alert{latestAlerts.length > 1 ? 's' : ''} #{latestAlerts.map((alert) => alert.alert_id).join(', #')} in Alert Register</button>}
        </div>
      </section>
    </>}
    {latestObservation && <ObservationRow key={latestObservation.observation_id} observation={latestObservation}
      isExpanded onToggleExpand={() => {}} onAssessmentUpdated={onCompleted}
      onWorkAreaUpdated={setLatestObservation} />}
  </div>;
}

function AuthenticatedApp() {
  const { user, isLoading, logout } = useAuth();
  const [route, setRoute] = useState<AppSection | AuthRoute>(readRoute);
  useEffect(() => { const onHash = () => setRoute(readRoute()); window.addEventListener('hashchange', onHash); return () => window.removeEventListener('hashchange', onHash); }, []);
  const navigate = (next: AppSection | AuthRoute) => { window.location.hash = next; setRoute(next); };
  useEffect(() => { if (!isLoading && !user && route !== 'login' && route !== 'signup') navigate('login'); if (user && (route === 'login' || route === 'signup')) navigate('overview'); }, [isLoading, user, route]);
  if (isLoading) return <div className="min-h-screen bg-[#f4f7f7] flex items-center justify-center text-sm text-slate-500">Restoring your SafeSite session…</div>;
  if (!user) return route === 'signup' ? <SignupPage onNavigate={(next) => navigate(next)} /> : <LoginPage onNavigate={(next) => navigate(next)} />;
  const section = route === 'login' || route === 'signup' ? 'overview' : route;
  return <AppShell activeSection={section} onNavigate={navigate} user={user} onLogout={() => { logout(); navigate('login'); }}>{section === 'overview' && <OverviewPage onNavigate={navigate} />}{(section === 'incidents' || section === 'analysis') && <SafetyWorkspace key={section} view={section} onNavigate={navigate} />}{section === 'alerts' && <AlertsPage onNavigate={navigate} />}{section === 'zones' && <ZoneAnalyticsPage />}{section === 'recurrence' && <RecurrenceAnalyticsPage onNavigate={navigate} />}{section === 'reports' && <ReportsPage />}</AppShell>;
}

export function App() { return <AuthProvider><AuthenticatedApp /></AuthProvider>; }
export default App;
