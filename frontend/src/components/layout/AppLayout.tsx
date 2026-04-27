import { type ReactNode } from "react";
import { useLocation, useMatch } from "react-router-dom";
import { Sidebar } from "./Sidebar";

function usePageTitle(): string {
  const location = useLocation();
  const isDetail = useMatch("/route-groups/:id");
  if (isDetail) return "Route Group Detail";
  const titles: Record<string, string> = {
    "/": "Dashboard",
    "/explorer": "Data Explorer",
    "/logs": "Collection Logs",
    "/users": "User Management",
  };
  return titles[location.pathname] ?? "Flight Price Tracker";
}

interface AppLayoutProps {
  children: ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  usePageTitle();

  return (
    <div className="flex min-h-screen bg-transparent">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col lg:pl-[220px]">
        <main className="flex-1 px-4 pb-6 pt-6 sm:px-6 lg:overflow-y-auto lg:px-8 lg:pb-8">
          {children}
        </main>
      </div>
    </div>
  );
}
