import { Search } from "lucide-react";

export function AppHeader() {
  return <header className="app-header"><div className="brand-lockup"><span className="brand-mark" aria-hidden="true">F</span><div className="brand-name">Frontend Copilot <span>AI product workspace</span></div></div><div className="header-tools"><div className="header-search" aria-hidden="true"><Search size={14} /><span>Search tools and guides</span></div><div className="user-control"><span className="user-avatar" aria-hidden="true">FC</span><span>Product team</span></div></div></header>;
}