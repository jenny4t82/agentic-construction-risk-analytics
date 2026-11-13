import { useState } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, Clock, History, RefreshCw, UserCheck } from 'lucide-react';
import { correctAssessmentContext, fetchAssessmentContext, ApiError } from '../api/client';
import type { AssessmentContextResponse, PendingAssessmentContext } from '../types';
import { formatDateTime } from '../utils/formatters';

interface Props {
  assessmentId: number;
  onSaved: () => void;
}

export function AssessmentContextEditor({ assessmentId, onSaved }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [record, setRecord] = useState<AssessmentContextResponse | null>(null);
  const [values, setValues] = useState({ people_count: '', duration_minutes: '', repeated_count: '' });
  const [initialValues, setInitialValues] = useState({ people_count: '', duration_minutes: '', repeated_count: '' });
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isConflict, setIsConflict] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const isDirty =
    values.people_count !== initialValues.people_count ||
    values.duration_minutes !== initialValues.duration_minutes ||
    values.repeated_count !== initialValues.repeated_count;

  const load = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    setIsConflict(false);
    try {
      const result = await fetchAssessmentContext(assessmentId);
      setRecord(result);
      const v = {
        people_count: String(result.context.people_count ?? ''),
        duration_minutes: String(result.context.duration_minutes ?? ''),
        repeated_count: String(result.context.repeated_count ?? ''),
      };
      setValues(v);
      setInitialValues(v);
      setIsOpen(true);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to load assessment context');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    if (isDirty) {
      if (!window.confirm('Discard unsaved assessment context changes?')) return;
    }
    setIsOpen(false);
    setErrorMessage(null);
    setSuccessMessage(null);
    setIsConflict(false);
    setShowHistory(false);
  };

  const save = async () => {
    if (!record) return;
    const people = Number(values.people_count);
    const duration = Number(values.duration_minutes);
    const repeated = Number(values.repeated_count);

    if (!Number.isInteger(people) || people < 1) {
      setErrorMessage('People exposed must be a whole number of at least 1.');
      return;
    }
    if (!Number.isInteger(duration) || duration < 1) {
      setErrorMessage('Exposure duration must be a whole number of at least 1 minute.');
      return;
    }
    if (!Number.isInteger(repeated) || repeated < 0) {
      setErrorMessage('Scoring repetition count must be a non-negative whole number (0 or greater).');
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    setIsConflict(false);

    try {
      const context: Required<PendingAssessmentContext> = {
        people_count: people,
        duration_minutes: duration,
        repeated_count: repeated,
      };
      const result = await correctAssessmentContext(assessmentId, record.revision, context);
      setRecord(result);
      const updatedV = {
        people_count: String(result.context.people_count ?? ''),
        duration_minutes: String(result.context.duration_minutes ?? ''),
        repeated_count: String(result.context.repeated_count ?? ''),
      };
      setValues(updatedV);
      setInitialValues(updatedV);
      setSuccessMessage(
        result.reconciliation.review_required
          ? 'Context corrected and risk recalculated. Existing linked alert history requires explicit operator review.'
          : 'Assessment context updated and risk score recalculated successfully.'
      );
      onSaved();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setIsConflict(true);
        setErrorMessage('Conflict detected: This assessment was modified by another operator. Reload latest context before retrying.');
      } else {
        setErrorMessage(error instanceof Error ? error.message : 'Unable to save assessment context');
      }
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) {
    return (
      <div className="inline-flex items-center gap-2">
        <button
          type="button"
          onClick={() => void load()}
          disabled={isLoading}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg border border-teal-200 text-teal-800 bg-teal-50/70 hover:bg-teal-100/70 transition-colors disabled:opacity-50"
        >
          {isLoading ? (
            <RefreshCw size={12} className="animate-spin text-teal-600" />
          ) : (
            <UserCheck size={12} className="text-teal-600" />
          )}
          <span>Edit Context</span>
        </button>
      </div>
    );
  }

  return (
    <div className="w-full mt-3 p-4 rounded-xl border border-teal-200 bg-teal-50/40 space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-teal-100 pb-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-teal-100 text-teal-800 flex items-center justify-center">
            <UserCheck size={15} />
          </div>
          <div>
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Assessment #{assessmentId} Context Editor
            </h4>
            <p className="text-[11px] text-slate-500">
              Revision: <span className="font-mono font-semibold text-teal-900">{record?.revision ?? 0}</span> · Status: {record?.assessment.status}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void load()}
            disabled={isLoading || isSaving}
            className="p-1.5 text-xs text-slate-500 hover:text-teal-700 rounded-md hover:bg-teal-100/50 transition-colors"
            title="Reload latest from server"
          >
            <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
          </button>
          <button
            type="button"
            onClick={handleClose}
            className="px-2.5 py-1 text-xs font-semibold text-slate-600 hover:text-slate-800 rounded-md hover:bg-slate-200/50 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>

      {/* Operator context note */}
      <div className="p-2.5 rounded-lg bg-white border border-teal-100 text-[11px] text-slate-600 leading-relaxed">
        <strong>Operator scoring inputs:</strong> These values represent contextual site risk conditions (people exposed, duration, repetition) rather than raw model detection counts. Corrections do not re-run YOLO or alter sibling assessments.
      </div>

      {/* Reconciliation notice if review required */}
      {record?.reconciliation.review_required && (
        <div role="alert" className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-start gap-2">
          <AlertTriangle size={15} className="text-amber-600 shrink-0 mt-0.5" />
          <div>
            <p className="font-bold">Alert Review Required</p>
            <p className="mt-0.5 text-[11px] text-amber-800">
              {record.reconciliation.reason || 'This hazard assessment was previously linked to an active alert. Updating its context flags the existing alert for operator review.'}
            </p>
            {record.reconciliation.alert_ids.length > 0 && (
              <p className="mt-1 text-[11px] font-mono text-amber-900">
                Linked Alert IDs: #{record.reconciliation.alert_ids.join(', #')}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Conflict banner */}
      {isConflict && (
        <div role="alert" className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-900 flex items-start justify-between gap-3">
          <div className="flex items-start gap-2">
            <AlertCircle size={15} className="text-rose-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">Revision Conflict (HTTP 409)</p>
              <p className="mt-0.5 text-[11px] text-rose-700">
                Another safety officer modified this assessment. Reload to inspect the updated context before saving.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void load()}
            className="px-3 py-1 bg-rose-100 hover:bg-rose-200 text-rose-800 rounded-md text-xs font-semibold shrink-0 transition-colors"
          >
            Reload Context
          </button>
        </div>
      )}

      {/* Success alert */}
      {successMessage && (
        <div role="status" className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-2">
          <CheckCircle2 size={14} className="text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* General error alert */}
      {errorMessage && !isConflict && (
        <div role="alert" className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
          <AlertCircle size={14} className="text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Edit Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
        className="space-y-3"
      >
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              People Exposed <span className="text-rose-500">*</span>
            </label>
            <input
              type="number"
              min={1}
              step={1}
              required
              value={values.people_count}
              onChange={(e) => setValues({ ...values, people_count: e.target.value })}
              className="w-full px-3 py-2 text-sm bg-white border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
              placeholder="Min 1"
            />
            <span className="text-[10px] text-slate-400 mt-0.5 block">Whole number ≥ 1</span>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Exposure Duration (min) <span className="text-rose-500">*</span>
            </label>
            <input
              type="number"
              min={1}
              step={1}
              required
              value={values.duration_minutes}
              onChange={(e) => setValues({ ...values, duration_minutes: e.target.value })}
              className="w-full px-3 py-2 text-sm bg-white border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
              placeholder="Min 1"
            />
            <span className="text-[10px] text-slate-400 mt-0.5 block">Duration in minutes ≥ 1</span>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Scoring Repetition Count <span className="text-rose-500">*</span>
            </label>
            <input
              type="number"
              min={0}
              step={1}
              required
              value={values.repeated_count}
              onChange={(e) => setValues({ ...values, repeated_count: e.target.value })}
              className="w-full px-3 py-2 text-sm bg-white border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
              placeholder="Min 0"
            />
            <span className="text-[10px] text-slate-400 mt-0.5 block">Repetition input ≥ 0</span>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={isSaving || !isDirty}
              className="px-4 py-2 bg-teal-700 hover:bg-teal-800 text-white rounded-lg text-xs font-semibold disabled:opacity-50 transition-colors shadow-xs"
            >
              {isSaving ? 'Recalculating…' : 'Save and recalculate'}
            </button>
            <button
              type="button"
              onClick={handleClose}
              className="px-3 py-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold transition-colors"
            >
              Cancel
            </button>
          </div>

          {record && record.audit_history.length > 0 && (
            <button
              type="button"
              onClick={() => setShowHistory((prev) => !prev)}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-teal-800 hover:text-teal-950 underline"
            >
              <History size={13} />
              <span>Correction History ({record.audit_history.length})</span>
              {showHistory ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>
          )}
        </div>
      </form>

      {/* Expandable Audit History Table */}
      {showHistory && record && record.audit_history.length > 0 && (
        <div className="mt-3 pt-3 border-t border-teal-100">
          <h5 className="text-[11px] font-bold uppercase tracking-wider text-slate-700 mb-2 flex items-center gap-1.5">
            <Clock size={12} className="text-teal-600" />
            Audit Trail for Assessment #{assessmentId}
          </h5>
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-[11px] text-left">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold">
                <tr>
                  <th className="py-2 px-3">Rev</th>
                  <th className="py-2 px-3">Date & Time</th>
                  <th className="py-2 px-3">Operator</th>
                  <th className="py-2 px-3">Context Values</th>
                  <th className="py-2 px-3">Risk Band & Score</th>
                  <th className="py-2 px-3">Safety Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {record.audit_history.map((audit) => (
                  <tr key={audit.revision} className="hover:bg-slate-50/50">
                    <td className="py-2 px-3 font-mono font-bold text-teal-800">r{audit.revision}</td>
                    <td className="py-2 px-3 whitespace-nowrap text-slate-600">{formatDateTime(audit.changed_at)}</td>
                    <td className="py-2 px-3 font-mono text-[10px] text-slate-500 truncate max-w-[120px]" title={audit.changed_by_user_id}>
                      {audit.changed_by_user_id}
                    </td>
                    <td className="py-2 px-3 whitespace-nowrap">
                      <span className="text-slate-400">
                        {audit.previous_values.people_count ?? '—'}p, {audit.previous_values.duration_minutes ?? '—'}m, {audit.previous_values.repeated_count ?? '—'}r
                      </span>
                      <span className="mx-1 text-slate-300">→</span>
                      <span className="font-semibold text-slate-900">
                        {audit.updated_values.people_count}p, {audit.updated_values.duration_minutes}m, {audit.updated_values.repeated_count}r
                      </span>
                    </td>
                    <td className="py-2 px-3 whitespace-nowrap">
                      <span className="text-slate-400">
                        {audit.previous_result.risk_band ?? 'Pending'} ({audit.previous_result.risk_score ?? '—'})
                      </span>
                      <span className="mx-1 text-slate-300">→</span>
                      <span className="font-bold text-teal-900">
                        {audit.updated_result.risk_band} ({audit.updated_result.risk_score})
                      </span>
                    </td>
                    <td className="py-2 px-3 whitespace-nowrap">
                      <span className="text-slate-400">{audit.previous_decision?.outcome ?? '—'}</span>
                      <span className="mx-1 text-slate-300">→</span>
                      <span className="font-semibold text-slate-800">{audit.updated_decision?.outcome}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
