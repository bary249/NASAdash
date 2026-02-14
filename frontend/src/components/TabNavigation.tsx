/**
 * TabNavigation - Tab navigation for Overview, Renewals, Leasing, Delinquencies
 * Matches design: Icon tabs with labels
 */
import { LayoutDashboard, RefreshCw, FileText, AlertTriangle, Package, ShieldAlert, Star, Eye, Crosshair } from 'lucide-react';

export type TabId = 'overview' | 'renewals' | 'leasing' | 'delinquencies' | 'rentable' | 'risk' | 'reviews' | 'watchlist' | 'watchpoints';

interface Tab {
  id: TabId;
  label: string;
  icon: typeof LayoutDashboard;
  color: string;
}

const tabs: Tab[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard, color: 'text-emerald-600' },
  { id: 'leasing', label: 'Leasing', icon: FileText, color: 'text-amber-600' },
  { id: 'rentable', label: 'Rentable Items', icon: Package, color: 'text-purple-600' },
  { id: 'renewals', label: 'Renewals', icon: RefreshCw, color: 'text-sky-600' },
  { id: 'delinquencies', label: 'Delinquencies', icon: AlertTriangle, color: 'text-rose-600' },
  { id: 'risk', label: 'Risk Scores', icon: ShieldAlert, color: 'text-indigo-600' },
  { id: 'reviews', label: 'Reviews', icon: Star, color: 'text-yellow-600' },
  { id: 'watchlist', label: 'Watch List', icon: Eye, color: 'text-red-600' },
  { id: 'watchpoints', label: 'Watchpoints', icon: Crosshair, color: 'text-violet-600' },
];

interface TabNavigationProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

export function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  return (
    <div className="flex items-center gap-1 bg-white rounded-xl p-1 border border-slate-200 shadow-sm">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
              ${isActive 
                ? 'bg-slate-100 text-slate-900' 
                : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }
            `}
          >
            <Icon className={`w-4 h-4 ${isActive ? tab.color : ''}`} />
            <span>{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}
