import { useCallback, useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { LoginPage, SignupPage } from './auth/AuthPages';
import { checkBackendHealth, fetchAlerts, fetchObservationDetail, fetchObservations, submitImageAssessment } from './api/client';
import { AlertsPage } from './components/AlertsPage';
import { AppShell, type AppSection } from './components/AppShell';
import { AssessmentResults } from './components/AssessmentResults';
import { ImageUploader } from './components/ImageUploader';
import { ObservationHistory } from './components/ObservationHistory';
import { OverviewPage } from './components/OverviewPage';
import { PendingAssessmentCompletion } from './components/PendingAssessmentCompletion';
import { RecurrenceAnalyticsPage } from './components/RecurrenceAnalyticsPage';
import { ReportsPage } from './components/ReportsPage';
import { SafetyDecisionPanel } from './components/SafetyDecisionPanel';
import { ZoneAnalyticsPage } from './components/ZoneAnalyticsPage';
import type { AlertDetailResponse, AssessmentCompletionResponse, AssessmentsResponse, ImageAssessmentParams, ObservationDetailResponse } from './types';

type AuthRoute = 'login' | 'signup';
const readRoute = (): AppSection | AuthRoute => {
  const hash = typeof window === 'undefined' ? '' : window.location.hash.slice(1);
  if (hash === 'login' || hash === 'signup') return hash;
  if (hash === 'incidents' || hash === 'history' || hash === 'alerts' || hash === 'zones' || hash === 'recurrence' || hash === 'reports' || hash === 'analysis' || hash === 'experimental') return hash === 'history' ? 'incidents' : hash === 'experimental' ? 'analysis' : hash;
  if (typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('tab') === 'experimental') return 'analysis';
  return 'overview';
};

function SafetyWorkspace({ view, onNavigate }: { view: 'analysis' | 'incidents'; onNavigate: (section: AppSection) => void }) {
  const { user } = useAuth();
  const [isBackendHealthy, setIsBackendHealthy] = useState(false);
  const [isDatabaseConfigured, setIsDatabaseConfigured] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [assessmentError, setAssessmentError] = useState<string | null>(null);
  const [latestAssessment, setLatestAssessment] = useState<AssessmentsResponse | null>(null);
  const [latestObservation, setLatestObservation] = useState<ObservationDetailResponse | null>(null);
  const [latestAlerts, setLatestAlerts] = useState<AlertDetailResponse[]>([]);
  const [completion, setCompletion] = useState<AssessmentCompletionResponse | null>(null);
  const [observations, setObservations] = useState<ObservationDetailResponse[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const canComplete = user?.role === 'safety_officer' || user?.role === 'admin';

  const loadHistory = useCallback(async () => {
    setIsHistoryLoading(true);
    try {
      const result = await fetchObservations(20, 0);
      setObservations(result.data);
      setIsDatabaseConfigured(result.isDatabaseConfigured);
      setHistoryError(result.error);
    } finally {
      setIsHistoryLoading(false);
    }
  }, []);

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
    setCompletion(null);
    try {
      const result = await submitImageAssessment(file, params);
      setLatestAssessment(result);
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

  const onCompleted = (result: AssessmentCompletionResponse) => {
    setCompletion(result);
    setLatestAssessment(null);
    void loadHistory();
    void fetchObservationDetail(result.observation_id).then(setLatestObservation).catch((reason) => {
      setHistoryError(reason instanceof Error ? reason.message : 'Unable to refresh the saved observation');
    });
    if (result.safety_decision.outcome === 'alert') {
      void fetchAlerts(result.observation_id).then(setLatestAlerts).catch(() => setLatestAlerts([]));
    }
  };

  if (view === 'incidents') {
    return <div className="space-y-7">
      <div><p className="text-sm text-teal-700 font-bold">Persisted records</p><h2 className="text-3xl font-bold mt-1">Safety incidents</h2><p className="text-slate-500 mt-2">Review recorded observations, findings, assessments and evidence.</p></div>
      <button onClick={() => onNavigate('analysis')} className="px-4 py-2.5 rounded-lg bg-teal-700 text-white text-sm font-semibold">Analyze another image</button>
      <ObservationHistory observations={observations} isLoading={isHistoryLoading} isDatabaseConfigured={isDatabaseConfigured && isBackendHealthy} error={historyError} onRefresh={loadHistory} onAssessmentCompleted={(observationId) => { if (latestAssessment?.observation_id === observationId) setLatestAssessment(null); void loadHistory(); }} onWorkAreaUpdated={(updated) => { setObservations((current) => current.map((item) => item.observation_id === updated.observation_id ? updated : item)); }} />
    </div>;
  }

  return <div className="space-y-7">
    <div><p className="text-sm text-teal-700 font-bold">Persisted image assessment</p><h2 className="text-3xl font-bold mt-1">AI Safety Analysis</h2><p className="text-slate-500 mt-2">Upload a construction-site image to identify supported PPE violations, assess risk, and record findings for review.</p></div>
    {!isDatabaseConfigured && !isHistoryLoading && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Persisted analysis is unavailable until the database connection is restored.</p>}
    {isDatabaseConfigured && <ImageUploader onAnalyze={analyze} isLoading={isAnalyzing} error={assessmentError} onClear={() => { setLatestAssessment(null); setCompletion(null); setLatestObservation(null); setLatestAlerts([]); }} />}
    {latestAssessment && <>
      <AssessmentResults assessment={latestAssessment} />
      <section className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">
        <p>Saved as Observation <strong>{latestAssessment.observation_id}</strong>.</p>
        <div className="mt-2 flex flex-wrap gap-4">
          <button onClick={() => onNavigate('incidents')} className="font-semibold underline">View in Observation History</button>
          {latestAlerts.length > 0 && <button onClick={() => onNavigate('alerts')} className="font-semibold underline">View alert{latestAlerts.length > 1 ? 's' : ''} #{latestAlerts.map((alert) => alert.alert_id).join(', #')} in Alert Register</button>}
        </div>
      </section>
      {latestAssessment.safety_decision.outcome === 'pending' && <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <p className="font-semibold">Assessment Pending</p>
        <p>Additional operator context is required to complete risk scoring. Review this observation in History{canComplete ? ', or complete its missing inputs here.' : '.'}</p>
        {canComplete && latestObservation?.detected_hazards.flatMap((hazard) => hazard.assessments.filter((item) => item.status === 'pending' && item.assessment_id != null)).map((item) => (
          <PendingAssessmentCompletion key={item.assessment_id} observation={latestObservation} assessment={item} onCompleted={onCompleted} />
        ))}
        <button onClick={() => onNavigate('incidents')} className="mt-3 font-semibold underline">Open Observation History</button>
      </section>}
    </>}
    {completion && <section className="rounded-xl border border-teal-200 bg-teal-50 p-5 text-sm text-teal-900 space-y-3">
      <h3 className="font-bold">Assessment #{completion.assessment_id} completed for Observation {completion.observation_id}</h3>
      <p>Severity {completion.assessment.severity} × likelihood {completion.assessment.likelihood} × exposure {completion.assessment.exposure} = risk score {completion.assessment.risk_score} ({completion.assessment.risk_band}).</p>
      <SafetyDecisionPanel decision={completion.safety_decision} />
      {completion.alert_ids.length > 0 && <p>Linked alert{completion.alert_ids.length > 1 ? 's' : ''} #{completion.alert_ids.join(', #')}. <button onClick={() => onNavigate('alerts')} className="font-semibold underline">Open Alert Register</button></p>}
      {completion.safety_decision.outcome === 'pending' && <p>Other findings still need assessment. <button onClick={() => onNavigate('incidents')} className="font-semibold underline">Continue in Observation History</button></p>}
      <button onClick={() => onNavigate('incidents')} className="font-semibold underline">View updated observation</button>
    </section>}
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
  return <AppShell activeSection={section} onNavigate={navigate} user={user} onLogout={() => { logout(); navigate('login'); }}>{section === 'overview' && <OverviewPage onNavigate={navigate} />}{(section === 'incidents' || section === 'analysis') && <SafetyWorkspace key={section} view={section} onNavigate={navigate} />}{section === 'alerts' && <AlertsPage />}{section === 'zones' && <ZoneAnalyticsPage />}{section === 'recurrence' && <RecurrenceAnalyticsPage onNavigate={navigate} />}{section === 'reports' && <ReportsPage />}</AppShell>;
}

export function App() { return <AuthProvider><AuthenticatedApp /></AuthProvider>; }
export default App;
