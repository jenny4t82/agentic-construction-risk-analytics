import { useState, type FormEvent, type ReactNode } from 'react';
import { ArrowRight, Eye, EyeOff, ShieldCheck } from 'lucide-react';
import { useAuth } from './AuthContext';
import { BrandLockup } from '../components/BrandLockup';

interface AuthPageProps {
  onNavigate: (page: 'login' | 'signup') => void;
}

function AuthFrame({ children }: AuthPageProps & { children: ReactNode }) {
  return (
    <main className="min-h-screen bg-[#eef3f4] flex items-center justify-center p-6">
      <div className="w-full max-w-5xl min-h-[620px] grid lg:grid-cols-[0.9fr_1.1fr] bg-white rounded-[2rem] overflow-hidden shadow-2xl shadow-slate-200/80">
        <section className="hidden lg:flex bg-[#102f33] text-white p-12 flex-col justify-between relative overflow-hidden">
          <div className="absolute -right-24 -top-24 w-72 h-72 rounded-full border-[40px] border-teal-700/30" />
          <div className="absolute -left-28 bottom-20 w-80 h-80 rounded-full border-[50px] border-amber-400/10" />
          <div className="relative">
            <BrandLockup />
            <div className="mt-24 max-w-sm">
              <p className="text-amber-300 text-xs font-bold uppercase tracking-[0.2em]">Built for safer decisions</p>
              <h1 className="text-4xl font-bold leading-tight mt-4">See risk clearly. Act before it escalates.</h1>
              <p className="mt-5 text-teal-100/75 leading-relaxed">A focused workspace for construction-site observations, safety alerts, and explainable risk intelligence.</p>
            </div>
          </div>
          <div className="relative flex items-center gap-3 text-sm text-teal-100/70"><ShieldCheck className="text-amber-300" size={18} /> Human-reviewed safety intelligence</div>
        </section>
        <section className="p-7 sm:p-12 flex flex-col justify-center"><div className="mb-8 rounded-xl bg-[#102f33] p-3 text-white lg:hidden"><BrandLockup compact /></div>{children}<div className="mt-8 text-center text-xs text-slate-400">SafeSite Risk Intelligence · Educational prototype</div></section>
      </div>
    </main>
  );
}

function PasswordField({ value, onChange, newPassword = false }: { value: string; onChange: (value: string) => void; newPassword?: boolean }) {
  const [visible, setVisible] = useState(false);
  return <div className="relative"><input className="auth-input pr-11" type={visible ? 'text' : 'password'} value={value} onChange={(event) => onChange(event.target.value)} placeholder={newPassword ? '8+ characters' : 'Password'} required minLength={newPassword ? 8 : undefined} /><button type="button" onClick={() => setVisible((current) => !current)} className="absolute right-3 top-3 text-slate-400" aria-label={visible ? 'Hide password' : 'Show password'}>{visible ? <EyeOff size={18} /> : <Eye size={18} />}</button></div>;
}

export function LoginPage({ onNavigate }: AuthPageProps) {
  const { login } = useAuth();
  const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [error, setError] = useState<string | null>(null); const [pending, setPending] = useState(false);
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(null); setPending(true); try { await login(email, password); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to sign in'); } finally { setPending(false); } };
  return <AuthFrame onNavigate={onNavigate}><div className="max-w-md mx-auto w-full"><p className="text-sm font-semibold text-teal-700">Welcome back</p><h2 className="text-3xl font-bold text-slate-900 mt-2">Sign in to your workspace</h2><p className="text-slate-500 mt-3">Review recorded safety findings and alerts with your authorized role.</p><form onSubmit={submit} className="mt-8 space-y-5"><label className="auth-label">Email<input className="auth-input" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" required /></label><label className="auth-label">Password<PasswordField value={password} onChange={setPassword} /></label>{error && <div className="auth-error">{error}</div>}<button className="auth-button" disabled={pending}>{pending ? 'Signing in…' : 'Sign in'}<ArrowRight size={17} /></button></form><p className="text-sm text-slate-500 mt-7 text-center">New to SafeSite? <button onClick={() => onNavigate('signup')} className="font-bold text-teal-700 hover:text-teal-900">Create an account</button></p></div></AuthFrame>;
}

export function SignupPage({ onNavigate }: AuthPageProps) {
  const { signup, login } = useAuth();
  const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [error, setError] = useState<string | null>(null); const [pending, setPending] = useState(false);
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(null); if (password.length < 8) { setError('Password must be at least 8 characters.'); return; } setPending(true); try { await signup(email, password); await login(email, password); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to create account'); } finally { setPending(false); } };
  return <AuthFrame onNavigate={onNavigate}><div className="max-w-md mx-auto w-full"><p className="text-sm font-semibold text-teal-700">Start with SafeSite</p><h2 className="text-3xl font-bold text-slate-900 mt-2">Create your account</h2><p className="text-slate-500 mt-3">Public signup creates a standard user account. Safety Officer and Admin access is granted by an existing Admin.</p><form onSubmit={submit} className="mt-8 space-y-5"><label className="auth-label">Email<input className="auth-input" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" required /></label><label className="auth-label">Password<PasswordField value={password} onChange={setPassword} newPassword /><span className="text-xs text-slate-500">Use at least 8 characters.</span></label>{error && <div className="auth-error">{error}</div>}<button className="auth-button" disabled={pending}>{pending ? 'Creating account…' : 'Create account'}<ArrowRight size={17} /></button></form><p className="text-sm text-slate-500 mt-7 text-center">Already registered? <button onClick={() => onNavigate('login')} className="font-bold text-teal-700 hover:text-teal-900">Sign in</button></p></div></AuthFrame>;
}
