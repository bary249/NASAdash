/**
 * Delinquency Section - Shows delinquency, eviction, and collections data
 * 
 * Displays data parsed from RealPage Delinquent and Prepaid reports.
 */
import { useState, useEffect } from 'react';
import { AlertTriangle, DollarSign, Users, TrendingDown, ChevronDown, ChevronUp } from 'lucide-react';
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

export function DelinquencySection({ propertyId }: Props) {
  const [data, setData] = useState<DelinquencyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [showEvictions, setShowEvictions] = useState(false);

  useEffect(() => {
    // Reset state immediately when property changes
    setData(null);
    setError(null);
    setShowDetails(false);
    setLoading(true);

    const fetchData = async () => {
      try {
        const response = await fetch(`/api/v2/properties/${propertyId}/delinquency`);
        if (!response.ok) {
          if (response.status === 404) {
            setData(null);
            return;
          }
          throw new Error(`Failed to fetch: ${response.status}`);
        }
        const result = await response.json();
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load delinquency data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [propertyId]);

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

  const { delinquency_aging, evictions, collections } = data;
  const totalAgingAbs = Math.abs(delinquency_aging.current) + Math.abs(delinquency_aging.days_0_30) + 
                        Math.abs(delinquency_aging.days_31_60) + Math.abs(delinquency_aging.days_61_90) + 
                        Math.abs(delinquency_aging.days_90_plus);

  // Get ALL delinquent residents (sorted by amount)
  const allDelinquent = data.resident_details
    ?.filter(r => r.total_delinquent > 0)
    ?.sort((a, b) => b.total_delinquent - a.total_delinquent) || [];

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

        {/* Net Balance */}
        <div className={`${data.net_balance >= 0 ? 'bg-red-50 border-red-100' : 'bg-blue-50 border-blue-100'} border rounded-xl p-4`}>
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown className={`w-4 h-4 ${data.net_balance >= 0 ? 'text-red-500' : 'text-blue-500'}`} />
            <span className={`text-xs font-medium uppercase ${data.net_balance >= 0 ? 'text-red-600' : 'text-blue-600'}`}>Net Balance</span>
          </div>
          <div className={`text-2xl font-bold ${data.net_balance >= 0 ? 'text-red-700' : 'text-blue-700'}`}>
            {formatCurrency(data.net_balance)}
          </div>
          <div className={`text-xs mt-1 ${data.net_balance >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
            Delinquent − Prepaid
          </div>
        </div>

        {/* Collections */}
        <div className="bg-amber-50 border border-amber-100 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Users className="w-4 h-4 text-amber-500" />
            <span className="text-xs font-medium text-amber-600 uppercase">Collections</span>
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
              label="Current" 
              value={delinquency_aging.current} 
              total={totalAgingAbs}
              color="bg-blue-400"
            />
            <AgingBar 
              label="0-30 Days" 
              value={delinquency_aging.days_0_30} 
              total={totalAgingAbs}
              color="bg-yellow-400"
            />
            <AgingBar 
              label="31-60 Days" 
              value={delinquency_aging.days_31_60} 
              total={totalAgingAbs}
              color="bg-orange-400"
            />
            <AgingBar 
              label="61-90 Days" 
              value={delinquency_aging.days_61_90} 
              total={totalAgingAbs}
              color="bg-red-400"
            />
            <AgingBar 
              label="90+ Days" 
              value={delinquency_aging.days_90_plus} 
              total={totalAgingAbs}
              color="bg-red-600"
            />
          </div>
        </div>

        {/* Collections Aging */}
        <div className="bg-slate-50 rounded-xl p-4">
          <h4 className="text-sm font-semibold text-slate-700 mb-4">Collections Aging (Former Residents)</h4>
          <div className="space-y-3">
            <AgingBar 
              label="Current" 
              value={collections.current || 0} 
              total={collections.total}
              color="bg-blue-400"
            />
            <AgingBar 
              label="0-30 Days" 
              value={collections.days_0_30} 
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
                    <th className="px-4 py-2 text-right text-xs font-medium text-red-700 uppercase">0-30</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-red-700 uppercase">31-60</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-red-700 uppercase">90+</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-red-100">
                  {evictionUnits.map((r, idx) => (
                    <tr key={idx} className="bg-red-50 hover:bg-red-100">
                      <td className="px-4 py-2 font-medium text-red-800">{r.unit}</td>
                      <td className="px-4 py-2 text-red-600">{r.status}</td>
                      <td className="px-4 py-2 text-right font-medium text-red-700">{formatCurrency(r.total_delinquent)}</td>
                      <td className="px-4 py-2 text-right text-red-600">{r.days_30 > 0 ? formatCurrency(r.days_30) : '-'}</td>
                      <td className="px-4 py-2 text-right text-red-600">{r.days_60 > 0 ? formatCurrency(r.days_60) : '-'}</td>
                      <td className="px-4 py-2 text-right text-red-600">{r.days_90_plus > 0 ? formatCurrency(r.days_90_plus) : '-'}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-red-300 bg-red-50 font-semibold text-red-800">
                    <td className="px-4 py-2" colSpan={2}>Total</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(evictionUnits.reduce((s, r) => s + r.total_delinquent, 0))}</td>
                    <td className="px-4 py-2" colSpan={3}></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Delinquent Units - Expandable */}
      {allDelinquent.length > 0 && (
        <div className="border border-slate-200 rounded-xl overflow-hidden">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors"
          >
            <span className="text-sm font-semibold text-slate-700">
              Delinquent Units ({allDelinquent.length}) — {formatCurrency(allDelinquent.reduce((s, r) => s + r.total_delinquent, 0))}
            </span>
            {showDetails ? (
              <ChevronUp className="w-4 h-4 text-slate-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-500" />
            )}
          </button>
          
          {showDetails && (
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
                  {allDelinquent.map((resident, idx) => (
                    <tr key={idx} className={resident.is_eviction ? 'bg-red-50' : resident.is_former ? 'bg-amber-50' : 'hover:bg-slate-50'}>
                      <td className="px-4 py-2 font-medium">
                        {resident.unit}
                        {resident.is_eviction && (
                          <span className="ml-2 text-xs text-red-600 font-semibold">EVICTION</span>
                        )}
                        {resident.is_former && (
                          <span className="ml-2 text-xs text-amber-600 font-semibold">FORMER</span>
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
                    <td className="px-4 py-2" colSpan={2}>Total ({allDelinquent.length} units)</td>
                    <td className="px-4 py-2 text-right text-red-700">{formatCurrency(allDelinquent.reduce((s, r) => s + r.total_delinquent, 0))}</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(allDelinquent.reduce((s, r) => s + r.days_30, 0))}</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(allDelinquent.reduce((s, r) => s + r.days_60, 0))}</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(allDelinquent.reduce((s, r) => s + (r.current || 0), 0))}</td>
                    <td className="px-4 py-2 text-right">{formatCurrency(allDelinquent.reduce((s, r) => s + r.days_90_plus, 0))}</td>
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
