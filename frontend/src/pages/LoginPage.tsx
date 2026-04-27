import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plane } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/Button";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err: unknown) {
      const isNetworkError =
        err instanceof TypeError ||
        (err as { response?: unknown })?.response === undefined;

      setError(
        isNetworkError
          ? "Cannot reach the server. Make sure the backend is running."
          : "Invalid email or password. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-transparent">
      <div className="hidden flex-1 flex-col justify-between bg-gradient-to-br from-brand-700 via-brand-600 to-violet-600 px-12 py-10 text-white lg:flex">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 backdrop-blur">
            <Plane className="h-5 w-5" />
          </div>
          <span className="text-lg font-semibold">Flight Price Tracker</span>
        </div>

        <div className="max-w-md">
          <h1 className="text-3xl font-bold leading-tight">
            Track every route. Every day. Automatically.
          </h1>
          <p className="mt-4 text-base text-white/80">
            Collect the cheapest daily flight prices across hundreds of routes
            and export them to Excel on demand.
          </p>
        </div>

        <p className="text-xs text-white/60">© Flight Price Tracker</p>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center bg-transparent px-8 py-12">
        <div className="mb-8 flex flex-col items-center gap-3 text-center lg:hidden">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-600">
            <Plane className="h-6 w-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Flight Price Tracker</h1>
        </div>

        <div className="w-full max-w-sm">
          <div className="mb-6 text-center">
            <h2 className="text-2xl font-bold text-slate-900">Welcome back</h2>
            <p className="mt-1 text-sm text-slate-500">Sign in to your account</p>
          </div>

          <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_18px_50px_-38px_rgba(15,23,42,0.45)]">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="email" className="field-label">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="field-input"
                  placeholder="admin@example.com"
                />
              </div>

              <div>
                <label htmlFor="password" className="field-label">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="field-input"
                  placeholder="••••••••"
                />
              </div>

              {error ? (
                <p className="rounded-[10px] bg-red-50 px-3 py-2 text-sm text-red-600">
                  {error}
                </p>
              ) : null}

              <Button type="submit" variant="primary" loading={loading} className="w-full">
                Sign in
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
