/**
 * Financials Section - Monthly Transaction Summary (P&L view)
 * 
 * Displays data from RealPage Report 4020 (Monthly Transaction Summary).
 * Shows P&L summary (gross rent → collections) plus transaction detail.
 */
import { useState, useEffect } from 'react';
import { DollarSign, ChevronDown, ChevronUp, ChevronRight } from 'lucide-react';
import { DrillThroughModal } from './DrillThroughModal';
import { SectionHeader } from './SectionHeader';
import { api } from '../api';

interface TransactionItem {
  group: string;
  group_name: string;
  code: string;
  description: string;
  ytd_last_month: number;
  this_month: number;
  ytd_through: number;
}

interface FinancialSummary {
  fiscal_period: string;
  report_date: string;
  gross_market_rent: number;
  gain_to_lease: number;
  loss_to_lease: number;
  gross_potential: number;
  total_other_charges: number;
  total_possible_collections: number;
  total_collection_losses: number;
  total_adjustments: number;
  past_due_end_prior: number;
  prepaid_end_prior: number;
  past_due_end_current: number;
  prepaid_end_current: number;
  net_change_past_due_prepaid: number;
  total_losses_and_adjustments: number;
  current_monthly_collections: number;
  total_monthly_collections: number;
  collection_rate: number;
}

interface PaymentMethod {
  method: string;
  amount: number;
}

interface ComputedMetrics {
  total_units: number;
  occupied_units: number;
  vacant_units: number;
  avg_market_rent: number;
  avg_effective_rent: number;
  rev_pau: number;
  economic_occupancy: number;
  loss_to_lease_pct: number;
  concession_total: number;
  concession_pct: number;
  bad_debt_total: number;
  bad_debt_pct: number;
  vacancy_loss_total: number;
  vacancy_loss_pct: number;
  other_income: number;
  other_income_per_unit: number;
  payment_methods: PaymentMethod[];
}

interface FinancialsData {
  property_id: string;
  summary: FinancialSummary;
  computed?: ComputedMetrics;
  charges: TransactionItem[];
  losses: TransactionItem[];
  payments: TransactionItem[];
}

interface Props {
  propertyId: string;
  propertyIds?: string[];
}

function fmt(value: number): string {
  const absValue = Math.abs(value);
  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
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

// TransactionTable removed — replaced by drill-through buttons + modal (FN-6)

function pct(value: number): string {
  return `${value >= 0 ? '' : '-'}${Math.abs(value).toFixed(2)}%`;
}

function mergeComputed(items: ComputedMetrics[]): ComputedMetrics {
  const sum = (fn: (c: ComputedMetrics) => number) => items.reduce((a, c) => a + fn(c), 0);
  const totalUnits = sum(c => c.total_units);
  const occUnits = sum(c => c.occupied_units);
  const totalCollections = items.reduce((a, c) => a + c.rev_pau * c.total_units, 0);
  const totalPossible = totalCollections / (items[0]?.economic_occupancy / 100 || 1);
  // Merge payment methods
  const pmMap = new Map<string, number>();
  for (const c of items) {
    for (const pm of c.payment_methods) {
      pmMap.set(pm.method, (pmMap.get(pm.method) || 0) + pm.amount);
    }
  }
  return {
    total_units: totalUnits,
    occupied_units: occUnits,
    vacant_units: sum(c => c.vacant_units),
    avg_market_rent: totalUnits > 0 ? Math.round(sum(c => c.avg_market_rent * c.total_units) / totalUnits * 100) / 100 : 0,
    avg_effective_rent: occUnits > 0 ? Math.round(sum(c => c.avg_effective_rent * c.occupied_units) / occUnits * 100) / 100 : 0,
    rev_pau: totalUnits > 0 ? Math.round(totalCollections / totalUnits * 100) / 100 : 0,
    economic_occupancy: totalPossible > 0 ? Math.round(totalCollections / totalPossible * 1000) / 10 : 0,
    loss_to_lease_pct: items.length > 0 ? Math.round(sum(c => c.loss_to_lease_pct) / items.length * 100) / 100 : 0,
    concession_total: sum(c => c.concession_total),
    concession_pct: items.length > 0 ? Math.round(sum(c => c.concession_pct * c.total_units) / (totalUnits || 1) * 100) / 100 : 0,
    bad_debt_total: sum(c => c.bad_debt_total),
    bad_debt_pct: items.length > 0 ? Math.round(sum(c => c.bad_debt_pct * c.total_units) / (totalUnits || 1) * 100) / 100 : 0,
    vacancy_loss_total: sum(c => c.vacancy_loss_total),
    vacancy_loss_pct: items.length > 0 ? Math.round(sum(c => c.vacancy_loss_pct * c.total_units) / (totalUnits || 1) * 100) / 100 : 0,
    other_income: sum(c => c.other_income),
    other_income_per_unit: totalUnits > 0 ? Math.round(sum(c => c.other_income) / totalUnits * 100) / 100 : 0,
    payment_methods: Array.from(pmMap.entries()).map(([method, amount]) => ({ method, amount: Math.round(amount * 100) / 100 })).sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount)),
  };
}

function mergeSummaries(items: FinancialSummary[]): FinancialSummary {
  const sum = (fn: (s: FinancialSummary) => number) => items.reduce((a, s) => a + fn(s), 0);
  const totalPossible = sum(s => s.total_possible_collections);
  const totalCollections = sum(s => s.total_monthly_collections);
  return {
    fiscal_period: items[0].fiscal_period,
    report_date: items[0].report_date,
    gross_market_rent: sum(s => s.gross_market_rent),
    gain_to_lease: sum(s => s.gain_to_lease),
    loss_to_lease: sum(s => s.loss_to_lease),
    gross_potential: sum(s => s.gross_potential),
    total_other_charges: sum(s => s.total_other_charges),
    total_possible_collections: totalPossible,
    total_collection_losses: sum(s => s.total_collection_losses),
    total_adjustments: sum(s => s.total_adjustments),
    past_due_end_prior: sum(s => s.past_due_end_prior),
    prepaid_end_prior: sum(s => s.prepaid_end_prior),
    past_due_end_current: sum(s => s.past_due_end_current),
    prepaid_end_current: sum(s => s.prepaid_end_current),
    net_change_past_due_prepaid: sum(s => s.net_change_past_due_prepaid),
    total_losses_and_adjustments: sum(s => s.total_losses_and_adjustments),
    current_monthly_collections: sum(s => s.current_monthly_collections),
    total_monthly_collections: totalCollections,
    collection_rate: totalPossible > 0 ? Math.round(totalCollections / totalPossible * 1000) / 10 : 0,
  };
}

function mergeTransactions(arrays: TransactionItem[][]): TransactionItem[] {
  const map = new Map<string, TransactionItem>();
  for (const items of arrays) {
    for (const item of items) {
      const key = `${item.code}|${item.description}`;
      const existing = map.get(key);
      if (existing) {
        existing.ytd_last_month += item.ytd_last_month;
        existing.this_month += item.this_month;
        existing.ytd_through += item.ytd_through;
      } else {
        map.set(key, { ...item });
      }
    }
  }
  return Array.from(map.values());
}

export default function FinancialsSection({ propertyId, propertyIds }: Props) {
  const [data, setData] = useState<FinancialsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [propCount, setPropCount] = useState(0);
  const [revOptOpen, setRevOptOpen] = useState(false);
  const [payMethodsOpen, setPayMethodsOpen] = useState(false);
  const [txnDrillOpen, setTxnDrillOpen] = useState(false);
  const [txnDrillTitle, setTxnDrillTitle] = useState('');
  const [txnDrillItems, setTxnDrillItems] = useState<TransactionItem[]>([]);

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
          effectiveIds.map(id => api.getFinancials(id).catch(() => null))
        );
        const valid = results.filter(Boolean) as FinancialsData[];
        if (valid.length === 0) {
          setError('No financial data available for selected properties.');
          return;
        }
        setPropCount(valid.length);
        if (valid.length === 1) {
          setData(valid[0]);
          return;
        }
        // Merge into consolidated view
        const merged: FinancialsData = {
          property_id: 'consolidated',
          summary: mergeSummaries(valid.map(d => d.summary)),
          computed: mergeComputed(valid.filter(d => d.computed).map(d => d.computed!)),
          charges: mergeTransactions(valid.map(d => d.charges)),
          losses: mergeTransactions(valid.map(d => d.losses)),
          payments: mergeTransactions(valid.map(d => d.payments)),
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
        <SectionHeader title="Financials" icon={DollarSign} />
        <div className="flex items-center justify-center py-12 text-slate-400 text-sm">
          <div className="animate-spin mr-2 h-4 w-4 border-2 border-slate-300 border-t-transparent rounded-full" />
          Loading financial data...
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <SectionHeader title="Financials" icon={DollarSign} />
        <div className="bg-white border border-slate-200 rounded-xl p-6 text-center text-slate-400 text-sm">
          {error === 'API error: 404 Not Found'
            ? 'No financial data available for this property yet.'
            : `Failed to load financials: ${error}`}
        </div>
      </div>
    );
  }

  const s = data.summary;
  const collectionPct = s.collection_rate;

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Financials"
        icon={DollarSign}
        subtitle={`${isMulti ? `${propCount} Properties (Consolidated) · ` : ''}${formatPeriod(s.fiscal_period)} · Report date ${s.report_date}`}
      />

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider font-medium mb-1">Gross Potential</div>
          <div className="text-xl font-bold text-slate-900 tabular-nums">{fmt(s.gross_potential)}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Market rent per leases</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider font-medium mb-1">Total Possible</div>
          <div className="text-xl font-bold text-slate-900 tabular-nums">{fmt(s.total_possible_collections)}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Rent + other charges</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider font-medium mb-1">Collections</div>
          <div className="text-xl font-bold text-emerald-700 tabular-nums">{fmt(s.total_monthly_collections)}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">{collectionPct}% effective rate</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider font-medium mb-1">Losses & Adjustments</div>
          <div className="text-xl font-bold text-rose-700 tabular-nums">{fmt(s.total_losses_and_adjustments)}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Concessions, credits, write-offs</div>
        </div>
      </div>

      {/* Collection Rate Bar */}
      <div className="bg-white border border-slate-200 rounded-xl px-5 py-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-600">Effective Collection Rate</span>
          <span className="text-sm font-bold text-slate-800">{collectionPct}%</span>
        </div>
        <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${collectionPct >= 90 ? 'bg-emerald-500' : collectionPct >= 75 ? 'bg-amber-500' : 'bg-rose-500'}`}
            style={{ width: `${Math.min(collectionPct, 100)}%` }}
          />
        </div>
      </div>

      {/* P&L Statement */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100">
          <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">Income Statement</span>
        </div>
        <div className="px-5 py-3 text-xs">
          <PLLine label="Gross Market Rent" value={s.gross_market_rent} bold />
          {(s.gain_to_lease !== 0 || s.loss_to_lease !== 0) && (
            <>
              <PLLine label="Gain to Lease" value={s.gain_to_lease} indent />
              <PLLine label="Loss to Lease" value={s.loss_to_lease} indent />
            </>
          )}
          <PLLine label="Gross Potential (per leases)" value={s.gross_potential} bold />
          <PLLine label="Other Monthly Charges" value={s.total_other_charges} />
          <div className="border-t border-slate-200 my-2" />
          <PLLine label="Total Possible Collections" value={s.total_possible_collections} bold highlight="indigo" />
          <PLLine label="Less: Collection Losses" value={s.total_collection_losses} />
          <PLLine label="Less: Adjustments" value={s.total_adjustments} />
          <PLLine label="Net Change Past Due / Prepaid" value={s.net_change_past_due_prepaid} />
          <div className="border-t border-slate-200 my-2" />
          <PLLine label="Total Losses & Adjustments" value={s.total_losses_and_adjustments} />
          <div className="border-t-2 border-slate-300 my-2" />
          <PLLine label="Total Monthly Collections" value={s.total_monthly_collections} bold highlight="emerald" />
        </div>
      </div>

      {/* Revenue Optimization Metrics (#47 — collapsible) */}
      {data.computed && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <button onClick={() => setRevOptOpen(!revOptOpen)} className="w-full flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors">
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">Revenue Optimization</span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">RevPAU {fmt(data.computed.rev_pau)}</span>
              {revOptOpen ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
            </div>
          </button>
          {revOptOpen && <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-slate-100 border-t border-slate-100">
            <MetricCell label="RevPAU" value={fmt(data.computed.rev_pau)} sub="Revenue per available unit" />
            <MetricCell label="Avg Effective Rent" value={fmt(data.computed.avg_effective_rent)} sub={`Market: ${fmt(data.computed.avg_market_rent)}`} />
            <MetricCell label="Economic Occupancy" value={`${data.computed.economic_occupancy}%`} sub="Collections ÷ Possible" />
            <MetricCell label="Other Income / Unit" value={fmt(data.computed.other_income_per_unit)} sub={`Total: ${fmt(data.computed.other_income)}`} />
            <MetricCell label="Loss-to-Lease" value={pct(data.computed.loss_to_lease_pct)} sub="% of Gross Market Rent" warn={Math.abs(data.computed.loss_to_lease_pct) > 3} />
            <MetricCell label="Concessions" value={pct(data.computed.concession_pct)} sub={fmt(data.computed.concession_total)} warn={data.computed.concession_pct > 3} />
            <MetricCell label="Bad Debt" value={pct(data.computed.bad_debt_pct)} sub={fmt(data.computed.bad_debt_total)} warn={data.computed.bad_debt_pct > 1} />
            <MetricCell label="Vacancy Loss" value={pct(data.computed.vacancy_loss_pct)} sub={fmt(data.computed.vacancy_loss_total)} warn={data.computed.vacancy_loss_pct > 5} />
          </div>}
        </div>
      )}

      {/* Payment Methods Breakdown (#47 — collapsible) */}
      {data.computed && data.computed.payment_methods.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <button onClick={() => setPayMethodsOpen(!payMethodsOpen)} className="w-full flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors">
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">Payment Methods</span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">{data.computed.payment_methods.length} methods</span>
              {payMethodsOpen ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
            </div>
          </button>
          {payMethodsOpen && <div className="px-5 py-3 border-t border-slate-100">
            {data.computed.payment_methods.map((pm, i) => {
              const maxAmt = Math.max(...data.computed!.payment_methods.map(p => Math.abs(p.amount)));
              const barPct = maxAmt > 0 ? Math.abs(pm.amount) / maxAmt * 100 : 0;
              return (
                <div key={i} className="flex items-center gap-3 py-1.5">
                  <div className="w-48 text-xs text-slate-600 shrink-0 truncate">{pm.method}</div>
                  <div className="flex-1 h-4 bg-slate-50 rounded overflow-hidden">
                    <div className="h-full bg-indigo-100 rounded" style={{ width: `${Math.max(barPct, 1)}%` }} />
                  </div>
                  <div className="w-24 text-xs font-medium text-slate-700 tabular-nums text-right shrink-0">{fmt(pm.amount)}</div>
                </div>
              );
            })}
          </div>}
        </div>
      )}

      {/* Transaction Detail — drill-through buttons */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {[
          { items: data.charges, title: 'Revenue & Charges', color: 'text-indigo-700', bg: 'bg-indigo-50 border-indigo-200 hover:bg-indigo-100' },
          { items: data.losses, title: 'Losses & Concessions', color: 'text-rose-700', bg: 'bg-rose-50 border-rose-200 hover:bg-rose-100' },
          { items: data.payments, title: 'Payments Received', color: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200 hover:bg-emerald-100' },
        ].map(({ items, title, color, bg }) => {
          const total = items.reduce((s, i) => s + i.this_month, 0);
          return (
            <button
              key={title}
              onClick={() => { setTxnDrillTitle(title); setTxnDrillItems(items); setTxnDrillOpen(true); }}
              className={`flex items-center justify-between rounded-xl border px-4 py-3 transition-colors cursor-pointer ${bg}`}
            >
              <div className="text-left">
                <div className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">{title}</div>
                <div className={`text-lg font-bold tabular-nums ${color}`}>{fmt(total)}</div>
                <div className="text-[10px] text-slate-400">{items.length} line items</div>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-400" />
            </button>
          );
        })}
      </div>

      {/* Transaction drill-through modal */}
      <DrillThroughModal
        isOpen={txnDrillOpen}
        onClose={() => setTxnDrillOpen(false)}
        title={txnDrillTitle}
        data={txnDrillItems}
        columns={[
          { key: 'description', label: 'Description' },
          { key: 'group_name', label: 'Category' },
          { key: 'code', label: 'Code' },
          { key: 'this_month', label: 'This Month', format: (v: unknown) => fmt(Number(v) || 0) },
          { key: 'ytd_through', label: 'YTD', format: (v: unknown) => fmt(Number(v) || 0) },
        ]}
      />
    </div>
  );
}

function MetricCell({ label, value, sub, warn }: { label: string; value: string; sub?: string; warn?: boolean }) {
  return (
    <div className="bg-white px-4 py-3">
      <div className="text-[10px] text-slate-400 uppercase tracking-wider font-medium mb-0.5">{label}</div>
      <div className={`text-base font-bold tabular-nums ${warn ? 'text-rose-600' : 'text-slate-800'}`}>{value}</div>
      {sub && <div className="text-[10px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  );
}

function PLLine({ label, value, bold, indent, highlight }: { label: string; value: number; bold?: boolean; indent?: boolean; highlight?: string }) {
  const color = highlight === 'emerald'
    ? 'text-emerald-700'
    : highlight === 'indigo'
      ? 'text-indigo-700'
      : value < 0
        ? 'text-rose-600'
        : 'text-slate-800';
  return (
    <div className={`flex justify-between py-1 ${indent ? 'pl-5' : ''}`}>
      <span className={bold ? 'font-semibold text-slate-700' : 'text-slate-500'}>{label}</span>
      <span className={`tabular-nums ${bold ? 'font-semibold' : 'font-medium'} ${color}`}>{fmt(value)}</span>
    </div>
  );
}
