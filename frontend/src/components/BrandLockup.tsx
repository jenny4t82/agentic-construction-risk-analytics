import { HardHat, Shield } from 'lucide-react';

/** Shared SafeSite mark for authentication and the application shell. */
export function BrandLockup({ compact = false, iconOnly = false }: { compact?: boolean; iconOnly?: boolean }) {
  return <div className="flex items-center gap-3" aria-label="SafeSite Risk Intelligence" title="SafeSite Risk Intelligence">
    <span className={`${compact ? 'h-10 w-10 rounded-xl' : 'h-11 w-11 rounded-2xl'} relative flex shrink-0 items-center justify-center bg-amber-400 text-[#102f33]`} aria-hidden="true">
      <Shield size={compact ? 28 : 31} strokeWidth={2.1} />
      <HardHat size={compact ? 15 : 17} strokeWidth={2.2} className="absolute top-[11px]" />
    </span>
    {!iconOnly && (
      <span className="whitespace-nowrap overflow-hidden">
        <span className="block font-bold tracking-tight leading-tight">SafeSite</span>
        <span className="block text-[10px] uppercase tracking-[.16em] text-teal-100/70">Risk Intelligence</span>
      </span>
    )}
  </div>;
}
