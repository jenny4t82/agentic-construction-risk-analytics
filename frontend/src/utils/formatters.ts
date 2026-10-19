import type { RiskBand } from '../types';

export const HAZARD_LABELS: Record<string, string> = {
  missing_safety_helmet: 'Missing Safety Helmet',
  missing_safety_vest: 'Missing Safety Vest',
  missing_protective_mask: 'Missing Protective Mask',
  missing_safety_gloves: 'Missing Safety Gloves',
  missing_safety_boots: 'Missing Safety Boots',
  missing_safety_goggles: 'Missing Safety Goggles',
};

export function formatHazardType(hazardType: string): string {
  if (HAZARD_LABELS[hazardType]) {
    return HAZARD_LABELS[hazardType];
  }
  return hazardType
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function formatRiskBand(band: RiskBand | string | null | undefined): {
  label: string;
  badgeClass: string;
  dotClass: string;
} {
  switch (band) {
    case 'Critical':
      return {
        label: 'Critical',
        badgeClass: 'bg-red-50 text-red-700 border-red-200 ring-red-600/20',
        dotClass: 'bg-red-500',
      };
    case 'High':
      return {
        label: 'High',
        badgeClass: 'bg-orange-50 text-orange-700 border-orange-200 ring-orange-600/20',
        dotClass: 'bg-orange-500',
      };
    case 'Moderate':
      return {
        label: 'Moderate',
        badgeClass: 'bg-amber-50 text-amber-700 border-amber-200 ring-amber-600/20',
        dotClass: 'bg-amber-500',
      };
    case 'Low':
      return {
        label: 'Low',
        badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200 ring-emerald-600/20',
        dotClass: 'bg-emerald-500',
      };
    default:
      return {
        label: band || 'Pending',
        badgeClass: 'bg-slate-100 text-slate-700 border-slate-200 ring-slate-600/20',
        dotClass: 'bg-slate-400',
      };
  }
}

export function formatConfidence(conf: number | null | undefined): string {
  if (conf === null || conf === undefined) return 'N/A';
  return `${(conf * 100).toFixed(1)}%`;
}

export function formatDateTime(isoString?: string | null): string {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}
