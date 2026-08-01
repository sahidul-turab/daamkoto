import { useState, type FormEvent } from "react";
import { Eye, EyeOff, Loader2, LockKeyhole, ShieldCheck } from "lucide-react";
import { ApiError } from "../api";

interface Props {
  checking: boolean;
  onLogin: (password: string) => Promise<void>;
}

export function AdminLogin({ checking, onLogin }: Props) {
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!password || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await onLogin(password);
      setPassword("");
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 429) {
        setError("Too many attempts. Please wait before trying again.");
      } else {
        setError("That password is not correct.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (checking) {
    return (
      <div className="flex min-h-[55vh] items-center justify-center text-ink-3">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="mx-auto flex min-h-[62vh] max-w-lg items-center">
      <section className="glass w-full overflow-hidden p-6 sm:p-8">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-brand/30 bg-brand-strong/10 text-brand">
          <LockKeyhole className="h-6 w-6" />
        </div>
        <div className="mt-5 text-center">
          <h1 className="text-2xl font-bold">Owner access</h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-3">
            Sign in to view scraper health, retailer freshness, update times, and operational product details.
          </p>
        </div>

        <form className="mt-7 space-y-4" onSubmit={submit}>
          <label className="block">
            <span className="label">Admin password</span>
            <span className="relative block">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                autoFocus
                className="field !py-3 pr-12"
                placeholder="Enter your password"
              />
              <button
                type="button"
                onClick={() => setShowPassword((value) => !value)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-4 hover:text-ink"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </span>
          </label>

          {error && (
            <div className="rounded-xl border border-brand/30 bg-brand-strong/10 px-3 py-2.5 text-sm text-brand">
              {error}
            </div>
          )}

          <button className="btn-brand w-full !py-3" type="submit" disabled={!password || submitting}>
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            {submitting ? "Signing in…" : "Open admin panel"}
          </button>
        </form>

        <p className="mt-5 text-center text-[11px] leading-relaxed text-ink-4">
          Your password is verified by the API and is never stored in the browser.
        </p>
      </section>
    </div>
  );
}
