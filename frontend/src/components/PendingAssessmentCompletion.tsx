import { useState, type FormEvent } from 'react';
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

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (assessment.assessment_id == null) return;
    const context: PendingAssessmentContext = {};
    for (const field of contextFields) {
      if (observation[field.key] != null) continue;
      const raw = values[field.key]?.trim() ?? '';
      const number = Number(raw);
      if (!raw || !Number.isInteger(number) || number < field.min) {
        setError(`${field.label} must be a whole number of at least ${field.min}.`);
        return;
      }
      context[field.key] = number;
    }
    setSubmitting(true);
    setError(null);
    try {
      onCompleted(await completePendingAssessment(assessment.assessment_id, context));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to complete assessment');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="w-full mt-3 p-3 rounded-lg border border-amber-200 bg-amber-50 space-y-3">
      <div>
        <p className="font-semibold text-amber-900">Assessment Pending</p>
        <p className="text-amber-800 mt-1">Complete missing context for assessment #{assessment.assessment_id}. Severity is derived from the supported hazard type.</p>
      </div>
      <div className="grid gap-2 sm:grid-cols-3">
        {contextFields.map((field) => {
          const existing = observation[field.key];
          return <label key={field.key} className="text-slate-700 font-medium">
            {field.label}{field.suffix && ` (${field.suffix})`}
            {existing == null ? (
              <input className="auth-input mt-1" type="number" min={field.min} step="1" required
                value={values[field.key] ?? ''}
                onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))} />
            ) : <span className="block mt-1 p-2 rounded border border-slate-200 bg-white">{existing} recorded</span>}
          </label>;
        })}
      </div>
      <p className="text-slate-600">Repetition is operator-supplied scoring context; it is not calculated from work-area recurrence.</p>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      <button type="submit" disabled={submitting || assessment.assessment_id == null}
        className="px-3 py-2 rounded bg-amber-700 text-white font-semibold disabled:opacity-50">
        {submitting ? 'Completing…' : 'Complete Assessment'}
      </button>
    </form>
  );
}
