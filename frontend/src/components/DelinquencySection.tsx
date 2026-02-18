/**
 * Delinquency Section - Shows delinquency, eviction, and collections data
 * 
 * Displays data parsed from RealPage Delinquent and Prepaid reports.
 */
import { useState, useEffect } from 'react';
import { AlertTriangle, DollarSign, Users, ChevronDown, ChevronUp } from 'lucide-react';
import { SectionHeader } from './SectionHeader';

interface DelinquencyAging {
  current: number;
  days_0_30: number;
  days_31_60: number;
  days_61_90: number;
  days_90_plus: number;
  total: number;
}


interface EvictionSummary {
  total_balance: number;
  unit_count: number;
  filed_count: number;
  writ_count: number;
}

interface CollectionsSummary {
  current: number;
  days_0_30: number;
  days_31_60: number;
  days_61_90: number;
  days_90_plus: number;
  total: number;
}

interface ResidentDelinquency {
  unit: string;
  status: string;
  total_prepaid: number;
  total_delinquent: number;
  net_balance: number;
  current: number;
  days_30: number;
  days_60: number;
  days_90_plus: number;
  deposits_held: number;
  is_eviction: boolean;
  is_former?: boolean;
}

interface DelinquencyReport {
  property_name: string;
  report_date: string;
  total_prepaid: number;
  total_delinquent: number;
  net_balance: number;
  delinquency_aging: DelinquencyAging;
  evictions: EvictionSummary;
  collections: CollectionsSummary;
  deposits_held: number;
  outstanding_deposits: number;
  resident_count: number;
  resident_details?: ResidentDelinquency[];
}

interface Props {
  propertyId: string;
  propertyIds?: string[];
}

function formatCurrency(value: number): string {
  const absValue = Math.abs(value);
  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(absValue);
  return value < 0 ? `(${formatted})` : formatted;
}

function AgingBar({ label, value, total, color }: { label: string; value: number; total: number; color: string }) {
  const percentage = total > 0 ? Math.min((Math.abs(value) / total) * 100, 100) : 0;
  
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-500 w-16">{label}</span>
      <div className="flex-1 h-4 bg-slate-100 rounded-full overflow-hidden">
        <div 
          className={`h-full ${color} transition-all duration-500`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className={`text-sm font-medium w-24 text-right ${value > 0 ? 'text-red-600' : 'text-slate-600'}`}>
        {formatCurrency(value)}
      </span>
    </div>
  );
}

export function DelinquencySection({ propertyId, propertyIds }: Props) {
  const [data, setData] = useState<DelinquencyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCurrentDetails, setShowCurrentDetails] = useState(false);
  const [showFormerDetails, setShowFormerDetails] = useState(false);
  const [showEvictions, setShowEvictions] = useState(false);

  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

  useEffect(() => {
    setData(null);
    setError(null);
    setShowCurrentDetails(false);
    setShowFormerDetails(false);
    setLoading(true);

    const fetchData = async () => {
      try {
        const results = await Promise.all(
          effectiveIds.map(async (pid) => {
            const response = await fetch(`/api/v2/properties/${pid}/delinquency`);
            if (!response.ok) {
              if (response.status === 404) return null;
              throw new Error(`Failed to fetch: ${response.status}`);
            }
            return response.json();
          })
        );
        const valid = results.filter(Boolean) as DelinquencyReport[];
        if (valid.length === 0) { setData(null); return; }
        if (valid.length === 1) { setData(valid[0]); return; }
        // Merge multiple reports
        const merged: DelinquencyReport = {
          property_name: `${valid.length} Properties`,
          report_date: valid[0].report_date,
          total_prepaid: valid.reduce((s, r) => s + r.total_prepaid, 0),
          total_delinquent: valid.reduce((s, r) => s + r.total_delinquent, 0),
          net_balance: valid.reduce((s, r) => s + r.net_balance, 0),
          delinquency_aging: {
            current: valid.reduce((s, r) => s + r.delinquency_aging.current, 0),
            days_0_30: valid.reduce((s, r) => s + r.delinquency_aging.days_0_30, 0),
            days_31_60: valid.reduce((s, r) => s + r.delinquency_aging.days_31_60, 0),
            days_61_90: valid.reduce((s, r) => s + r.delinquency_aging.days_61_90, 0),
            days_90_plus: valid.reduce((s, r) => s + r.delinquency_aging.days_90_plus, 0),
            total: valid.reduce((s, r) => s + r.delinquency_aging.total, 0),
          },
          evictions: {
            total_balance: valid.reduce((s, r) => s + r.evictions.total_balance, 0),
            unit_count: valid.reduce((s, r) => s + r.evictions.unit_count, 0),
            filed_count: valid.reduce((s, r) => s + r.evictions.filed_count, 0),
            writ_count: valid.reduce((s, r) => s + r.evictions.writ_count, 0),
          },
          collections: {
            current: valid.reduce((s, r) => s + (r.collections?.current || 0), 0),
            days_0_30: valid.reduce((s, r) => s + (r.collections?.days_0_30 || 0), 0),
            days_31_60: valid.reduce((s, r) => s + (r.collections?.days_31_60 || 0), 0),
            days_61_90: valid.reduce((s, r) => s + (r.collections?.days_61_90 || 0), 0),
            days_90_plus: valid.reduce((s, r) => s + (r.collections?.days_90_plus || 0), 0),
            total: valid.reduce((s, r) => s + (r.collections?.total || 0), 0),
          },
          deposits_held: valid.reduce((s, r) => s + (r.deposits_held || 0), 0),
          outstanding_deposits: valid.reduce((s, r) => s + (r.outstanding_deposits || 0), 0),
          resident_count: valid.reduce((s, r) => s + r.resident_count, 0),
          resident_details: valid.flatMap(r => r.resident_details || []),
        };
        setData(merged);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load delinquency data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveIds.join(',')]);

  if (loading) {
    return (
      <div className="venn-section animate-pulse">
        <div className="h-8 bg-slate-200 rounded w-48 mb-4" />
        <div className="h-32 bg-slate-100 rounded" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="venn-section">
        <SectionHeader 
          title="Delinquencies & Collections" 
          icon={AlertTriangle}
        />
        <div className="text-center py-8 text-red-500">{error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="venn-section">
        <SectionHeader 
          title="Delinquencies & Collections" 
          icon={AlertTriangle}
        />
        <div className="text-center py-8 text-slate-500">
          No delinquency report available for this property
        </div>
      </div>
    );
  }

  const { evictions, collections } = data;
  const collections_0_30 = (collections.days_0_30 || 0) + (collections.current || 0);

  // Split delinquent residents into current vs former
  const allDelinquent = data.resident_details
    ?.filter(r => r.total_delinquent > 0)
    ?.sort((a, b) => b.total_delinquent - a.total_delinquent) || [];

  const currentResidents = allDelinquent.filter(r => !r.is_former);
  const formerResidents = allDelinquent.filter(r => r.is_former);

  const currentTotal = currentResidents.reduce((s, r) => s + r.total_delinquent, 0);
  const formerTotal = formerResidents.reduce((s, r) => s + r.total_delinquent, 0);

  // Compute aging from current residents only (so it matches the Current Resident AR table)
  const aging_0_30 = currentResidents.reduce((s, r) => s + (r.days_30 || 0) + (r.current || 0), 0);
  const aging_31_60 = currentResidents.reduce((s, r) => s + (r.days_60 || 0), 0);
  const aging_61_90 = currentResidents.reduce((s, r) => {
    // 61-90 = total - (0-30) - (31-60) - (90+)
    const bucket = Math.max(0, r.total_delinquent - (r.days_30 || 0) - (r.current || 0) - (r.days_60 || 0) - (r.days_90_plus || 0));
    return s + bucket;
  }, 0);
  const aging_90_plus = currentResidents.reduce((s, r) => s + (r.days_90_plus || 0), 0);
  const totalAgingAbs = Math.abs(aging_0_30) + Math.abs(aging_31_60) + Math.abs(aging_61_90) + Math.abs(aging_90_plus);

  // Eviction units from resident_details
  const evictionUnits = data.resident_details
    ?.filter(r => r.is_eviction)
    ?.sort((a, b) => b.total_delinquent - a.total_delinquent) || [];

  return (
    <div className="venn-section">
      <SectionHeader 
        title="Delinquencies & Collections" 
        icon={AlertTriangle}
        description={`Report Date: ${data.report_date}`}
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {/* Total Delinquent */}
        <div className="bg-red-50 border border-red-100 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-4 h-4 text-red-500" />
            <span className="text-xs font-medium text-red-600 uppercase">Total Delinquent</span>
          </div>
          <div className="text-2xl font-bold text-red-700">
            {formatCurrency(data.total_delinquent)}
          </div>
          <div className="text-xs text-red-500 mt-1">
            {data.resident_count} residents with balances
          </div>
        </div>

        {/* Total Prepaid */}
        <div className="bg-green-50 border border-green-100 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-4 h-4 text-green-500" />
            <span className="text-xs font-medium text-green-600 uppercase">Total Prepaid</span>
          </div>
          <div className="text-2xl font-bold text-green-700">
            {formatCurrency(Math.abs(data.total_prepaid))}
          </div>
          <div className="text-xs text-green-500 mt-1">
            Credits on accounts
          </div>
        </div>

        {/* Collections */}
        <div className="bg-amber-50 border border-amber-100 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Users className="w-4 h-4 text-amber-500" />
            <span className="text-xs font-medium text-amber-600 uppercase">Former Residents Balance</span>
          </div>
          <div className="text-2xl font-bold text-amber-700">
            {formatCurrency(collections.total)}
          </div>
          <div className="text-xs text-amber-500 mt-1">
            Former residents owed
          </div>
        </div>
      </div>

      {/* Aging Breakdown */}
      <div className="grid md:grid-cols-2 gap-6 mb-6">
        {/* Delinquency Aging */}
        <div className="bg-slate-50 rounded-xl p-4">
          <h4 className="text-sm font-semibold text-slate-700 mb-4">Delinquency Aging</h4>
          <div className="space-y-3">
            <AgingBar 
              label="0-30 Days" 
              value={aging_0_30} 
              total={totalAgingAbs}
              color="bg-yellow-400"
            />
            <AgingBar 
              label="31-60 Days" 
              value={aging_31_60} 
              total={totalAgingAbs}
              color="bg-orange-400"
            />
            <AgingBar 
              label="61-90 Days" 
              value={aging_61_90} 
              total={totalAgingAbs}
              color="bg-red-400"
            />
            <AgingBar 
              label="90+ Days" 
              value={aging_90_plus} 
              total={totalAgingAbs}
              color="bg-red-600"
            />
          </div>
        </div>

        {/* Collections Aging */}
        <div className="bg-slate-50 rounded-xl p-4">
          <h4 className="text-sm font-semibold text-slate-700 mb-4">Former Residents Balance Aging</h4>
          <div className="space-y-3">
            <AgingBar 
              label="0-30 Days" 
              value={collections_0_30} 
              total={collections.total}
              color="bg-yellow-400"
            />
            <AgingBar 
              label="31-60 Days" 
              value={collections.days_31_60} 
              total={collections.total}
              color="bg-orange-400"
            />
            <AgingBar 
              label="61-90 Days" 
              value={collections.days_61_90} 
              total={collections.total}
              color="bg-red-400"
            />
            <AgingBar 
              label="90+ Days" 
              value={collections.days_90_plus} 
              total={collections.total}
              color="bg-red-600"
            />
          </div>
        </div>
      </div>

      {/* Evictions Summary — Clickable drill-through */}
      {evictions.unit_count > 0 && (
        <div className="border border-red-200 rounded-xl mb-6 overflow-hidden">
          <button
            onClick={() => setShowEvictions(!showEvictions)}
            className="w-full bg-red-50 px-4 py-4 flex items-center justify-between hover:bg-red-100 transition-colors"
          >
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-600" />
              <h4 className="text-sm font-semibold text-red-700">Active Evictions</h4>
              <span className="text-[10px] text-red-400 font-normal">(may include non-payment & lease violations)</span>
            </div>
            {showEvictions ? (
              <ChevronUp className="w-4 h-4 text-red-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-red-500" />
            )}
          </button>
          <div className="bg-red-50 px-4 pb-4">
            <div className="grid grid-cols-2 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold text-red-700">{evictions.unit_count}</div>
                <div className="text-xs text-red-600">Units</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-red-700">{formatCurrency(evictions.total_balance)}</div>
                <div className="text-xs text-red-600">Total Owed</div>
              </div>
            </div>
          </div>
          {showEvictions && evictionUnits.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-red-100">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-red-700 uppercase">Unit</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-red-700 uppercase">Status</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-red-700 uppercase">Delinquent</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-red-700 uppercase">Deposits</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-red-700 uppercase">Net Exposure</th>
                    <th className="px-4 py-2 text-center text-xs font-medium text-red-700 uppercase">Est. Days</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-red-100">
                  {evictionUnits.map((r, idx) => {
                    const estDays = r.days_90_plus > 0 ? '90+' : r.days_60 > 0 ? '60–90' : r.days_30 > 0 ? '30–60' : '<30';
                    const netExposure = r.total_delinquent - (r.deposits_held || 0);
                    return (
                      <tr key={idx} className="bg-red-50 hover:bg-red-100">
                        <td className="px-4 py-2 font-medium text-red-800">{r.unit}</td>
                        <td className="px-4 py-2 text-red-600 text-xs">{r.status}</td>
                        <td className="px-4 py-2 text-right font-medium text-red-700">{formatCurrency(r.total_delinquent)}</td>
                        <td className="px-4 py-2 text-right text-slate-500">{r.deposits_held ? formatCurrency(r.deposits_held) : '—'}</td>
                        <td className={`px-4 py-2 text-right font-semibold ${netExposure > 0 ? 'text-red-700' : 'text-emerald-600'}`}>{formatCurrency(netExposure)}</td>
                        <td className="px-4 py-2 text-center">
                          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${estDays === '90+' ? 'bg-red-200 text-red-800' : estDays === '60–90' ? 'bg-orange-200 text-orange-800' : estDays === '30–60' ? 'bg-amber-200 text-amber-800' : 'bg-yellow-100 text-yellow-800'}`}>
                            {estDays}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-red-300 bg-red-50 font-semibold text-red-800">
                    <td className="px-4 py-2" colSpan={2}>Total ({evictionUnits.length})</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(evictionUnits.reduce((s, r) => s + r.total_delinquent, 0))}</td>
                    <td className="px-4 py-2 text-right text-slate-500">{formatCurrency(evictionUnits.reduce((s, r) => s + (r.deposits_held || 0), 0))}</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(evictionUnits.reduce((s, r) => s + r.total_delinquent - (r.deposits_held || 0), 0))}</td>
                    <td className="px-4 py-2"></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Current Resident AR - Primary section */}
      {currentResidents.length > 0 && (
        <div className="border border-slate-200 rounded-xl overflow-hidden mb-4">
          <button
            onClick={() => setShowCurrentDetails(!showCurrentDetails)}
            className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors"
          >
            <span className="text-sm font-semibold text-slate-700">
              Current Resident AR ({currentResidents.length}) — {formatCurrency(currentTotal)}
            </span>
            {showCurrentDetails ? (
              <ChevronUp className="w-4 h-4 text-slate-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-500" />
            )}
          </button>
          
          {showCurrentDetails && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-100">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase">Unit</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase">Status</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase">Delinquent</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase">0-30</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase">31-60</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase">61-90</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase">90+</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {currentResidents.map((resident, idx) => (
                    <tr key={idx} className={resident.is_eviction ? 'bg-red-50' : 'hover:bg-slate-50'}>
                      <td className="px-4 py-2 font-medium">
                        {resident.unit}
                        {resident.is_eviction && (
                          <span className="ml-2 text-xs text-red-600 font-semibold">EVICTION</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-slate-600">{resident.status}</td>
                      <td className="px-4 py-2 text-right font-medium text-red-600">
                        {formatCurrency(resident.total_delinquent)}
                      </td>
                      <td className="px-4 py-2 text-right text-slate-600">
                        {resident.days_30 > 0 ? formatCurrency(resident.days_30) : '-'}
                      </td>
                      <td className="px-4 py-2 text-right text-slate-600">
                        {resident.days_60 > 0 ? formatCurrency(resident.days_60) : '-'}
                      </td>
                      <td className="px-4 py-2 text-right text-slate-600">
                        {(resident.current || 0) > 0 ? formatCurrency(resident.current || 0) : '-'}
                      </td>
                      <td className="px-4 py-2 text-right text-slate-600">
                        {resident.days_90_plus > 0 ? formatCurrency(resident.days_90_plus) : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-slate-300 font-semibold text-slate-800 bg-slate-50">
                    <td className="px-4 py-2" colSpan={2}>Total ({currentResidents.length} units)</td>
                    <td className="px-4 py-2 text-right text-red-700">{formatCurrency(currentTotal)}</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(currentResidents.reduce((s, r) => s + r.days_30, 0))}</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(currentResidents.reduce((s, r) => s + r.days_60, 0))}</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(currentResidents.reduce((s, r) => s + (r.current || 0), 0))}</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(currentResidents.reduce((s, r) => s + r.days_90_plus, 0))}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Former Resident AR - Secondary section */}
      {formerResidents.length > 0 && (
        <div className="border border-amber-200 rounded-xl overflow-hidden">
          <button
            onClick={() => setShowFormerDetails(!showFormerDetails)}
            className="w-full flex items-center justify-between px-4 py-3 bg-amber-50 hover:bg-amber-100 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-amber-600" />
              <span className="text-sm font-semibold text-amber-700">
                Former Resident AR ({formerResidents.length}) — {formatCurrency(formerTotal)}
              </span>
            </div>
            {showFormerDetails ? (
              <ChevronUp className="w-4 h-4 text-amber-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-amber-500" />
            )}
          </button>
          
          {showFormerDetails && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-amber-100">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-amber-700 uppercase">Unit</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-amber-700 uppercase">Status</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-amber-700 uppercase">Delinquent</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-amber-700 uppercase">0-30</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-amber-700 uppercase">31-60</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-amber-700 uppercase">61-90</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-amber-700 uppercase">90+</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-amber-100">
                  {formerResidents.map((resident, idx) => (
                    <tr key={idx} className="bg-amber-50 hover:bg-amber-100">
                      <td className="px-4 py-2 font-medium text-amber-800">{resident.unit}</td>
                      <td className="px-4 py-2 text-amber-600">{resident.status}</td>
                      <td className="px-4 py-2 text-right font-medium text-amber-700">
                        {formatCurrency(resident.total_delinquent)}
                      </td>
                      <td className="px-4 py-2 text-right text-amber-600">
                        {resident.days_30 > 0 ? formatCurrency(resident.days_30) : '-'}
                      </td>
                      <td className="px-4 py-2 text-right text-amber-600">
                        {resident.days_60 > 0 ? formatCurrency(resident.days_60) : '-'}
                      </td>
                      <td className="px-4 py-2 text-right text-amber-600">
                        {(resident.current || 0) > 0 ? formatCurrency(resident.current || 0) : '-'}
                      </td>
                      <td className="px-4 py-2 text-right text-amber-600">
                        {resident.days_90_plus > 0 ? formatCurrency(resident.days_90_plus) : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-amber-300 font-semibold text-amber-800 bg-amber-50">
                    <td className="px-4 py-2" colSpan={2}>Total ({formerResidents.length} units)</td>
                    <td className="px-4 py-2 text-right text-amber-700">{formatCurrency(formerTotal)}</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(formerResidents.reduce((s, r) => s + r.days_30, 0))}</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(formerResidents.reduce((s, r) => s + r.days_60, 0))}</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(formerResidents.reduce((s, r) => s + (r.current || 0), 0))}</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(formerResidents.reduce((s, r) => s + r.days_90_plus, 0))}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
