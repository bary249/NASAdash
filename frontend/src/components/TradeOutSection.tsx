import { useState, useEffect } from 'react';
import { ArrowRightLeft, TrendingUp, TrendingDown } from 'lucide-react';
import { SectionHeader } from './SectionHeader';

interface TradeOut {
  unit_id: string;
  unit_type: string;
  prior_rent: number;
  new_rent: number;
  dollar_change: number;
  pct_change: number;
  move_in_date: string;
}

interface TradeOutData {
  tradeouts: TradeOut[];
  summary: {
    count: number;
    avg_prior_rent: number;
    avg_new_rent: number;
    avg_dollar_change: number;
    avg_pct_change: number;
  };
}

interface TradeOutSectionProps {
  propertyId: string;
}

export function TradeOutSection({ propertyId }: TradeOutSectionProps) {
  const [data, setData] = useState<TradeOutData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      if (!propertyId) return;
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/v2/properties/${propertyId}/tradeouts`);
        if (!response.ok) throw new Error('Failed to fetch trade-outs');
        const result = await response.json();
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [propertyId]);

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(val);

  const formatPercent = (val: number) => {
    const sign = val >= 0 ? '+' : '';
    return `${sign}${val.toFixed(1)}%`;
  };

  const formatDollarChange = (val: number) => {
    const sign = val >= 0 ? '+' : '';
    return `${sign}${formatCurrency(val)}`;
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <SectionHeader title="Lease Trade-Outs" icon={ArrowRightLeft} />
        <div className="animate-pulse space-y-4 mt-4">
          <div className="h-8 bg-gray-200 rounded w-1/3"></div>
          <div className="h-32 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <SectionHeader title="Lease Trade-Outs" icon={ArrowRightLeft} />
        <p className="text-red-500 mt-4">{error}</p>
      </div>
    );
  }

  if (!data || data.tradeouts.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <SectionHeader title="Lease Trade-Outs" icon={ArrowRightLeft} />
        <p className="text-gray-500 mt-4 text-sm">No trade-out data available for this property.</p>
      </div>
    );
  }

  const { tradeouts, summary } = data;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <SectionHeader title="Lease Trade-Outs" icon={ArrowRightLeft} />
      
      {/* Summary Row */}
      <div className="mt-4 grid grid-cols-4 gap-4 p-4 bg-gray-50 rounded-lg mb-4">
        <div>
          <p className="text-xs text-gray-500 uppercase">Trade-Outs</p>
          <p className="text-xl font-semibold">{summary.count}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 uppercase">Avg Prior Rent</p>
          <p className="text-xl font-semibold">{formatCurrency(summary.avg_prior_rent)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 uppercase">Avg New Rent</p>
          <p className="text-xl font-semibold">{formatCurrency(summary.avg_new_rent)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 uppercase">Avg Change</p>
          <p className={`text-xl font-semibold flex items-center gap-1 ${summary.avg_pct_change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {summary.avg_pct_change >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            {formatPercent(summary.avg_pct_change)}
          </p>
        </div>
      </div>

      {/* Trade-Outs Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Unit</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Prior Rent</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">New Rent</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">$ Change</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">% Change</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Move-In</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {tradeouts.map((t, idx) => (
              <tr key={idx} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-sm font-medium text-gray-900">{t.unit_id}</td>
                <td className="px-4 py-3 text-sm text-gray-500">{t.unit_type}</td>
                <td className="px-4 py-3 text-sm text-gray-500 text-right">{formatCurrency(t.prior_rent)}</td>
                <td className="px-4 py-3 text-sm text-gray-900 text-right font-medium">{formatCurrency(t.new_rent)}</td>
                <td className={`px-4 py-3 text-sm text-right font-medium ${t.dollar_change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatDollarChange(t.dollar_change)}
                </td>
                <td className={`px-4 py-3 text-sm text-right font-medium ${t.pct_change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatPercent(t.pct_change)}
                </td>
                <td className="px-4 py-3 text-sm text-gray-500 text-right">{t.move_in_date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
