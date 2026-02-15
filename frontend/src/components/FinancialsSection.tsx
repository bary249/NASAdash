/**
 * Financials Section - Monthly Transaction Summary (P&L view)
 * 
 * Displays data from RealPage Report 4020 (Monthly Transaction Summary).
 * Shows P&L summary (gross rent → collections) plus transaction detail.
 */
import { useState, useEffect } from 'react';
import { DollarSign, ChevronDown, ChevronUp } from 'lucide-react';
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

interface FinancialsData {
  property_id: string;
  summary: FinancialSummary;
  charges: TransactionItem[];
  losses: TransactionItem[];
  payments: TransactionItem[];
}

interface Props {
  propertyId: string;
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

function TransactionTable({ items, title }: { items: TransactionItem[]; title: string }) {
  const [expanded, setExpanded] = useState(false);
  if (items.length === 0) return null;
  const totalThisMonth = items.reduce((sum, i) => sum + i.this_month, 0);
  const displayItems = expanded ? items : items.filter(i => Math.abs(i.this_month) > 0).slice(0, 5);

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-700">{title}</span>
          <span className="text-[10px] text-slate-400">{items.length} items</span>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-sm font-semibold tabular-nums ${totalThisMonth < 0 ? 'text-rose-600' : 'text-slate-800'}`}>{fmt(totalThisMonth)}</span>
          {expanded ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
        </div>
      </button>
      {displayItems.length > 0 && (
        <div className="border-t border-slate-100">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-400 uppercase tracking-wider">
                <th className="text-left px-5 py-2 font-medium">Description</th>
                <th className="text-right px-5 py-2 font-medium">This Month</th>
                <th className="text-right px-5 py-2 font-medium hidden sm:table-cell">YTD</th>
              </tr>
            </thead>
            <tbody>
              {displayItems.map((item, i) => (
                <tr key={i} className="border-t border-slate-50 hover:bg-slate-50/50">
                  <td className="px-5 py-2">
                    <div className="text-slate-700 text-xs">{item.description}</div>
                    <div className="text-[10px] text-slate-400">{item.group_name}</div>
                  </td>
                  <td className={`text-right px-5 py-2 tabular-nums font-medium ${item.this_month < 0 ? 'text-rose-600' : 'text-slate-700'}`}>
                    {fmt(item.this_month)}
                  </td>
                  <td className={`text-right px-5 py-2 tabular-nums hidden sm:table-cell ${item.ytd_through < 0 ? 'text-rose-500' : 'text-slate-400'}`}>
                    {fmt(item.ytd_through)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!expanded && items.length > displayItems.length && (
            <button
              onClick={() => setExpanded(true)}
              className="w-full py-2 text-[11px] text-indigo-500 hover:text-indigo-600 border-t border-slate-100 font-medium"
            >
              View all {items.length} line items
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function FinancialsSection({ propertyId }: Props) {
  const [data, setData] = useState<FinancialsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!propertyId) return;
    setLoading(true);
    setError(null);
    api.getFinancials(propertyId)
      .then(setData)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [propertyId]);

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
        subtitle={`${formatPeriod(s.fiscal_period)} · Report date ${s.report_date}`}
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

      {/* Transaction Detail */}
      <TransactionTable items={data.charges} title="Revenue & Charges" />
      <TransactionTable items={data.losses} title="Losses & Concessions" />
      <TransactionTable items={data.payments} title="Payments Received" />
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
