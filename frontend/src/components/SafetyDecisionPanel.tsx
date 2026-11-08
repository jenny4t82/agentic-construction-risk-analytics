import { AlertTriangle, Clock3, Info, ShieldAlert } from 'lucide-react';
import type { SafetyDecisionOutcome, SafetyDecisionResponse } from '../types';
import { formatConfidence, formatHazardType } from '../utils/formatters';

// Presentation only: the backend supplies the outcome, priority, risk band, and reason.
const outcomeDisplay: Record<SafetyDecisionOutcome, {
  title: string;
  explanation: string;
  classes: string;
  icon: typeof ShieldAlert;
}> = {
  alert: {
    title: 'Alert',
    explanation: 'Actionable alert indicated under the current system policy.',
    classes: 'border-rose-300 bg-rose-50 text-rose-950',
    icon: ShieldAlert,
  },
  warning: {
    title: 'Warning',
    explanation: 'A supported finding exists; no actionable alert is indicated.',
    classes: 'border-amber-300 bg-amber-50 text-amber-950',
    icon: AlertTriangle,
  },
  pending: {
    title: 'Pending Assessment',
    explanation: 'Evidence or scoring is incomplete and needs review.',
    classes: 'border-blue-300 bg-blue-50 text-blue-950',
    icon: Clock3,
  },
  no_alert: {
    title: 'No Actionable Alert',
    explanation: 'This result does not confirm complete PPE compliance or site safety.',
    classes: 'border-slate-300 bg-slate-50 text-slate-900',
    icon: Info,
  },
};

export function SafetyDecisionPanel({ decision, compact = false }: {
  decision: SafetyDecisionResponse;
  compact?: boolean;
}) {
  const display = outcomeDisplay[decision.outcome];
  const Icon = display.icon;
  return (
    <section aria-label="Safety decision" className={`rounded-xl border ${display.classes} ${compact ? 'p-4' : 'p-5'}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Icon size={compact ? 18 : 22} className="shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <h3 className="font-bold">{display.title}</h3>
            <p className="text-sm mt-1">{display.explanation}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="rounded-md border border-current/20 px-2 py-1">Risk band: {decision.risk_band ?? 'Not assessed'}</span>
          <span className="rounded-md border border-current/20 px-2 py-1">Notification priority: {decision.priority}</span>
        </div>
      </div>
      <p className="text-sm mt-3">{decision.reason}</p>
      {decision.supporting_evidence.length > 0 && (
        <div className="mt-3 border-t border-current/15 pt-3">
          <p className="text-xs font-semibold uppercase tracking-wide">Supporting findings</p>
          <ul className="mt-2 space-y-1 text-xs">
            {decision.supporting_evidence.map((item, index) => (
              <li key={`${item.hazard_type}-${item.source_label}-${index}`}>
                {formatHazardType(item.hazard_type)} · confidence {formatConfidence(item.detection_confidence)} · {item.risk_band ?? 'Unscored'}{item.risk_score === null ? '' : `, score ${item.risk_score}`}
              </li>
            ))}
          </ul>
        </div>
      )}
      {!compact && <p className="mt-3 text-xs opacity-75">Current provisional system decision policy · {decision.policy_version}</p>}
    </section>
  );
}
