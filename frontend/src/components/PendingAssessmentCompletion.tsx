import { useRef, useState, type FormEvent } from 'react';
import { completePendingAssessment } from '../api/client';
import type { AssessmentCompletionResponse, ObservationDetailResponse, PendingAssessmentContext, PersistedAssessmentResponse } from '../types';

interface Props {
  observation: ObservationDetailResponse;
  assessment: PersistedAssessmentResponse;
  onCompleted: (result: AssessmentCompletionResponse) => void;
}

const contextFields = [
  { key: 'people_count', label: 'People exposed', min: 1, suffix: '' },
  { key: 'duration_minutes', label: 'Exposure duration', min: 1, suffix: 'minutes' },
  { key: 'repeated_count', label: 'Repetition count', min: 0, suffix: '' },
] as const;

export function PendingAssessmentCompletion({ observation, assessment, onCompleted }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sent = useRef(false);
  const [completed, setCompleted] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (assessment.assessment_id == null || sent.current) return;
    const context: PendingAssessmentContext = {};
    for (const field of contextFields) {
      if (observation[field.key] != null && values[field.key] === undefined) continue;
      const raw = values[field.key]?.trim() ?? '';
      const number = Number(raw);
      if (!raw || !Number.isInteger(number) || number < field.min) {
        setError(`${field.label} must be a whole number of at least ${field.min}.`);
        return;
      }
      context[field.key] = number;
    }
    sent.current = true;
    setSubmitting(true);
    setError(null);
    try {
      const result = await completePendingAssessment(assessment.assessment_id, context);
      setCompleted(true);
      onCompleted(result);
    } catch (reason) {
      sent.current = false;
      setError(reason instanceof Error ? reason.message : 'Unable to complete assessment');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form data-pending-assessment={assessment.assessment_id} onSubmit={submit} className="w-full mt-3 p-3 rounded-lg border border-amber-200 bg-amber-50 space-y-3">
      <div>
        <p className="font-semibold text-amber-900">Assessment Pending</p>
        <p className="text-amber-800 mt-1">Complete missing context for assessment #{assessment.assessment_id}. Severity is derived from the supported hazard type.</p>
      </div>
      <div className="grid gap-2 sm:grid-cols-3">
        {contextFields.map((field) => {
          const existing = observation[field.key];
          return <label key={field.key} className="text-slate-700 font-medium">
            {field.label}{field.suffix && ` (${field.suffix})`}
            {(
              <input className="auth-input mt-1" type="number" min={field.min} step="1" required
                value={values[field.key] ?? (existing == null ? '' : String(existing))}
                onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))} />
            )}
            {existing != null && <span className="block text-xs text-slate-500">Recorded context: {existing}. Completion cannot replace recorded values; use Edit Context after completion to correct them.</span>}
          </label>;
        })}
      </div>
      <p className="text-slate-600">Repetition is operator-supplied scoring context; it is not calculated from work-area recurrence.</p>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      <button type="submit" disabled={submitting || completed || assessment.assessment_id == null}
        className="px-3 py-2 rounded bg-amber-700 text-white font-semibold disabled:opacity-50">
        {submitting ? 'Completing…' : 'Complete Assessment'}
      </button>
    </form>
  );
}
