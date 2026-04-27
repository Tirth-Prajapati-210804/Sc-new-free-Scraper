import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";

const LoginPage = lazy(() =>
  import("./pages/LoginPage").then((m) => ({ default: m.LoginPage })),
);
const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage })),
);
const RouteGroupDetailPage = lazy(() =>
  import("./pages/RouteGroupDetailPage").then((m) => ({
    default: m.RouteGroupDetailPage,
  })),
);
const DataExplorerPage = lazy(() =>
  import("./pages/DataExplorerPage").then((m) => ({
    default: m.DataExplorerPage,
  })),
);
const CollectionLogsPage = lazy(() =>
  import("./pages/CollectionLogsPage").then((m) => ({
    default: m.CollectionLogsPage,
  })),
);
const UsersPage = lazy(() =>
  import("./pages/UsersPage").then((m) => ({ default: m.UsersPage })),
);
const NotFoundPage = lazy(() =>
  import("./pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage })),
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function PageFallback() {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ToastProvider>
            <Suspense fallback={<PageFallback />}>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route
                  element={
                    <ProtectedRoute>
                      <AppLayout>
                        <Outlet />
                      </AppLayout>
                    </ProtectedRoute>
                  }
                >
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/route-groups/:id" element={<RouteGroupDetailPage />} />
                  <Route path="/explorer" element={<DataExplorerPage />} />
                  <Route path="/logs" element={<CollectionLogsPage />} />
                  <Route path="/users" element={<UsersPage />} />
                </Route>
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
}
