/**
 * Income Statement Section — GL Account Detail from RealPage Report 3836.
 * 
 * Complements FinancialsSection (Report 4020) by showing the GL-level breakdown
 * and unique metrics not available in the transaction summary (employee units,
 * admin/down units). Overlapping KPIs are intentionally omitted.
 */
import { useState, useEffect } from 'react';
import { Receipt, ChevronDown, ChevronUp } from 'lucide-react';
import { useSortable } from '../hooks/useSortable';
import { SortHeader } from './SortHeader';
import { SectionHeader } from './SectionHeader';
import { api } from '../api';

interface GLItem {
  gl_code: string;
  name: string;
  sign: string;
  amount: number;
  category: string;
}

interface IncomeData {
  property_id: string;
  summary: {
    fiscal_period: string;
    market_rent: number;
    loss_to_lease: number;
    loss_to_lease_pct: number;
    vacancy: number;
    vacancy_pct: number;
    concessions: number;
    concessions_pct: number;
    bad_debt: number;
    admin_down_units: number;
    employee_units: number;
    other_income: number;
    total_potential_income: number;
    total_income: number;
    effective_rent_pct: number;
  };
  totals: Record<string, number>;
  sections: Record<string, GLItem[]>;
}

interface Props {
  propertyId: string;
  propertyIds?: string[];
}

function fmt(value: number): string {
  const absValue = Math.abs(value);
  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD',
    minimumFractionDigits: 0, maximumFractionDigits: 0,
  }).format(absValue);
  return value < 0 ? `(${formatted})` : formatted;
}

function formatPeriod(fp: string): string {
  if (!fp || fp.length !== 6) return fp;
  const mo = fp.substring(0, 2);
  const yr = fp.substring(2);
  const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${names[parseInt(mo, 10) - 1] || mo} ${yr}`;
}

function GLGroupTable({ label, items }: { label: string; items: GLItem[] }) {
  const { sorted, sortKey, sortDir, toggleSort } = useSortable(items);
  const subtotal = items.reduce((sum, item) => sum + (item.sign === '-' ? -item.amount : item.amount), 0);
  return (
    <div>
      <div className="px-5 py-2 bg-slate-50 border-b border-slate-100">
        <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{label}</span>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr>
            <SortHeader label="GL Code" column="gl_code" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} className="pl-5 pr-2 w-28" />
            <SortHeader label="Description" column="name" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} className="px-2" />
            <SortHeader label="+/−" column="sign" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="center" className="px-2 w-10" />
            <SortHeader label="Amount" column="amount" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="right" className="pr-5 pl-2 w-28" />
          </tr>
        </thead>
        <tbody>
          {sorted.map((item, i) => (
            <tr key={i} className="border-b border-slate-50 hover:bg-slate-50/50">
              <td className="pl-5 pr-2 py-1.5 text-slate-400 font-mono w-28 shrink-0">{item.gl_code || '—'}</td>
              <td className="px-2 py-1.5 text-slate-700">{item.name}</td>
              <td className="px-2 py-1.5 text-center text-slate-400 w-10">{item.sign}</td>
              <td className={`pr-5 pl-2 py-1.5 text-right tabular-nums font-medium w-28 ${item.sign === '-' ? 'text-rose-600' : 'text-slate-700'}`}>
                {fmt(item.amount)}
              </td>
            </tr>
          ))}
          <tr className="bg-slate-50/50">
            <td colSpan={2} className="pl-5 py-1.5 text-xs font-semibold text-slate-500">Subtotal</td>
            <td />
            <td className="pr-5 py-1.5 text-right tabular-nums font-semibold text-slate-700 text-xs">{fmt(subtotal)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export default function IncomeStatementSection({ propertyId, propertyIds }: Props) {
  const [data, setData] = useState<IncomeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [glOpen, setGlOpen] = useState(true);
  const [propCount, setPropCount] = useState(0);

  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];
  const isMulti = effectiveIds.length > 1;

  useEffect(() => {
    if (!effectiveIds.length || !effectiveIds[0]) return;
    setLoading(true);
    setError(null);
    setData(null);

    const fetchAll = async () => {
      try {
        const results = await Promise.all(
          effectiveIds.map(id => api.getIncomeStatement(id).catch(() => null))
        );
        const valid = results.filter(Boolean) as IncomeData[];
        if (valid.length === 0) {
          setError('No income statement data available.');
          return;
        }
        setPropCount(valid.length);
        if (valid.length === 1) {
          setData(valid[0]);
          return;
        }
        // Merge multiple properties — only sections and unique summary fields needed
        const allSections: Record<string, GLItem[]> = {};
        for (const d of valid) {
          for (const [section, items] of Object.entries(d.sections)) {
            if (!allSections[section]) allSections[section] = [];
            for (const item of items) {
              const existing = allSections[section].find(x => x.gl_code === item.gl_code && x.name === item.name);
              if (existing) {
                existing.amount += item.amount;
              } else {
                allSections[section].push({ ...item });
              }
            }
          }
        }
        const mergedTotals: Record<string, number> = {};
        for (const d of valid) {
          for (const [k, v] of Object.entries(d.totals)) {
            mergedTotals[k] = (mergedTotals[k] || 0) + v;
          }
        }
        const merged: IncomeData = {
          property_id: 'consolidated',
          summary: {
            fiscal_period: valid[0].summary.fiscal_period,
            market_rent: valid.reduce((s, d) => s + d.summary.market_rent, 0),
            loss_to_lease: valid.reduce((s, d) => s + d.summary.loss_to_lease, 0),
            loss_to_lease_pct: 0,
            vacancy: valid.reduce((s, d) => s + d.summary.vacancy, 0),
            vacancy_pct: 0,
            concessions: valid.reduce((s, d) => s + d.summary.concessions, 0),
            concessions_pct: 0,
            bad_debt: valid.reduce((s, d) => s + d.summary.bad_debt, 0),
            admin_down_units: valid.reduce((s, d) => s + d.summary.admin_down_units, 0),
            employee_units: valid.reduce((s, d) => s + d.summary.employee_units, 0),
            other_income: valid.reduce((s, d) => s + d.summary.other_income, 0),
            total_potential_income: valid.reduce((s, d) => s + d.summary.total_potential_income, 0),
            total_income: valid.reduce((s, d) => s + d.summary.total_income, 0),
            effective_rent_pct: 0,
          },
          totals: mergedTotals,
          sections: allSections,
        };
        setData(merged);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveIds.join(',')]);

  if (loading) {
    return (
      <div className="space-y-4">
        <SectionHeader title="GL Revenue Detail" icon={Receipt} />
        <div className="flex items-center justify-center py-12 text-slate-400 text-sm">
          <div className="animate-spin mr-2 h-4 w-4 border-2 border-slate-300 border-t-transparent rounded-full" />
          Loading GL detail...
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <SectionHeader title="GL Revenue Detail" icon={Receipt} />
        <div className="bg-white border border-slate-200 rounded-xl p-6 text-center text-slate-400 text-sm">
          {error === 'API error: 404 Not Found'
            ? 'No income statement data available for this property yet.'
            : `Failed to load: ${error}`}
        </div>
      </div>
    );
  }

  const s = data.summary;
  const hasUniqueMetrics = s.admin_down_units > 0 || s.employee_units > 0;
  const allItems = Object.values(data.sections).flat();
  const totalItems = allItems.length;

  // Group GL items by prefix for a cleaner view
  const glGroups: { label: string; prefix: string; items: GLItem[] }[] = [
    { label: 'Market Rent', prefix: '5100-0001', items: [] },
    { label: 'Adjustments', prefix: '5100-02', items: [] },
    { label: 'Fees & Other Income', prefix: '52', items: [] },
    { label: 'Utilities Income', prefix: '53', items: [] },
    { label: 'Delinquency / A/R', prefix: '12', items: [] },
    { label: 'Other', prefix: '', items: [] },
  ];
  for (const item of allItems) {
    const gc = item.gl_code || '';
    let placed = false;
    for (const g of glGroups) {
      if (g.prefix && gc.startsWith(g.prefix)) {
        g.items.push(item);
        placed = true;
        break;
      }
    }
    if (!placed) {
      glGroups[glGroups.length - 1].items.push(item);
    }
  }

  return (
    <div className="space-y-5">
      <SectionHeader
        title="GL Revenue Detail"
        icon={Receipt}
        subtitle={`${isMulti ? `${propCount} Properties · ` : ''}${formatPeriod(s.fiscal_period)} · Accrual basis (Report 3836)`}
      />

      {/* Unique metrics only — employee units, admin/down (not in 4020) */}
      {hasUniqueMetrics && (
        <div className="flex gap-3">
          {s.employee_units > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-4 flex-1">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider font-medium mb-1">Employee Units</div>
              <div className="text-lg font-bold text-amber-700 tabular-nums">{fmt(s.employee_units)}</div>
              <div className="text-[10px] text-slate-400 mt-0.5">Revenue offset from staff housing</div>
            </div>
          )}
          {s.admin_down_units > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-4 flex-1">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider font-medium mb-1">Admin / Down Units</div>
              <div className="text-lg font-bold text-amber-700 tabular-nums">{fmt(s.admin_down_units)}</div>
              <div className="text-[10px] text-slate-400 mt-0.5">Revenue offset from offline units</div>
            </div>
          )}
        </div>
      )}

      {/* GL Account Table — open by default */}
      {totalItems > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <button
            onClick={() => setGlOpen(!glOpen)}
            className="w-full flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors"
          >
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">GL Account Breakdown</span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">{totalItems} line items</span>
              {glOpen ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
            </div>
          </button>
          {glOpen && (
            <div className="border-t border-slate-100">
              {glGroups.filter(g => g.items.length > 0).map((group) => (
                <GLGroupTable key={group.label} label={group.label} items={group.items} />
              ))}
              {/* Report totals */}
              {Object.keys(data.totals).length > 0 && (
                <div className="px-5 py-3 bg-slate-50 border-t border-slate-200">
                  {Object.entries(data.totals).map(([label, amount]) => (
                    <div key={label} className="flex justify-between py-0.5">
                      <span className="text-xs font-semibold text-slate-600">{label}</span>
                      <span className={`text-xs font-bold tabular-nums ${label.includes('INCOME') ? 'text-indigo-700' : 'text-slate-700'}`}>{fmt(amount)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
