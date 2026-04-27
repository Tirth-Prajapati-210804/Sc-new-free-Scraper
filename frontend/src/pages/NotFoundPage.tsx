import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-lg rounded-[32px] border border-slate-200 bg-white px-8 py-10 text-center shadow-[0_18px_50px_-38px_rgba(15,23,42,0.45)]">
        <p className="text-[72px] font-bold leading-none text-slate-200">404</p>
        <h1 className="mt-4 text-2xl font-bold text-slate-900">Page not found</h1>
        <p className="mt-2 text-sm text-slate-500">This page doesn&apos;t exist or was moved.</p>
        <Link to="/" className="mt-6 inline-flex text-sm font-medium text-brand-600 hover:text-brand-700">
          Back to Dashboard
        </Link>
      </div>
    </div>
  );
}
