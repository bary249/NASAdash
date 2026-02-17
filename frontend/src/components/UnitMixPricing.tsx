/**
 * UnitMixPricing - Compact table showing unit mix with pricing
 * Matches design: Table with floorplan, in-place rent, asking rent, delta
 * Now collapsible
 */
import { useState } from 'react';
import { TrendingUp, TrendingDown, ChevronDown, ChevronUp } from 'lucide-react';
import { InfoTooltip } from './InfoTooltip';

interface FloorplanRow {
  name: string;
  unitCount: number;
  inPlaceRent: number;
  askingRent: number;
}

interface UnitMixPricingProps {
  floorplans: FloorplanRow[];
  onRowClick?: (floorplan: string) => void;
  defaultExpanded?: boolean;
}

export function UnitMixPricing({ floorplans, onRowClick, defaultExpanded = true }: UnitMixPricingProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  // Format currency with max 2 decimal places
  const formatCurrency = (value: number) => {
    const rounded = Math.round(value * 100) / 100;
    return `$${rounded.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
  };

  const getDelta = (inPlace: number, asking: number) => {
    if (inPlace === 0) return { value: 0, formatted: '—' };
    const delta = asking - inPlace;
    // Round to max 2 decimal places to avoid floating point display issues
    const roundedDelta = Math.round(delta * 100) / 100;
    return {
      value: roundedDelta,
      formatted: roundedDelta >= 0 
        ? `+$${roundedDelta.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}` 
        : `-$${Math.abs(roundedDelta).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`,
    };
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between hover:bg-slate-100 transition-colors"
      >
        <h3 className="text-sm font-semibold text-slate-700 inline-flex items-center gap-1">Unit Mix & Pricing <InfoTooltip text="In-Place = avg rent currently being paid by occupied units (from RealPage Rent Roll). Asking = current market/asking rent for the floorplan. Delta = Asking minus In-Place. Source: RealPage Rent Roll & Pricing reports." /></h3>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        )}
      </button>

      {isExpanded && <div className="overflow-x-auto">
        <table className="w-full text-sm table-fixed">
          <colgroup>
            <col className="w-[24%]" />
            <col className="w-[22%]" />
            <col className="w-[22%]" />
            <col className="w-[16%]" />
            <col className="w-[16%]" />
          </colgroup>
          <thead>
            <tr className="border-b border-slate-100">
              <th className="px-2 py-2 text-left text-xs font-medium text-slate-500">Type</th>
              <th className="px-2 py-2 text-right text-xs font-medium text-slate-500">In-Place</th>
              <th className="px-2 py-2 text-right text-xs font-medium text-slate-500">Asking</th>
              <th className="px-2 py-2 text-right text-xs font-medium text-slate-500">Delta $</th>
              <th className="px-2 py-2 text-right text-xs font-medium text-slate-500">Delta %</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {floorplans.map((fp) => {
              const delta = getDelta(fp.inPlaceRent, fp.askingRent);
              const isPositive = delta.value >= 0;

              return (
                <tr 
                  key={fp.name}
                  onClick={() => onRowClick?.(fp.name)}
                  className={`
                    hover:bg-slate-50 transition-colors
                    ${onRowClick ? 'cursor-pointer' : ''}
                  `}
                >
                  <td className="px-2 py-2.5 truncate">
                    <div className="flex flex-col">
                      <span className="font-medium text-slate-900">{fp.name}</span>
                      <span className="text-xs text-slate-400">{fp.unitCount} units</span>
                    </div>
                  </td>
                  <td className="px-2 py-2.5 text-right font-medium text-slate-700 whitespace-nowrap">
                    {formatCurrency(fp.inPlaceRent)}
                  </td>
                  <td className="px-2 py-2.5 text-right font-medium text-slate-700 whitespace-nowrap">
                    {formatCurrency(fp.askingRent)}
                  </td>
                  <td className="px-2 py-2.5 text-right whitespace-nowrap">
                    <span className={`
                      inline-flex items-center gap-1 text-xs font-medium
                      ${isPositive ? 'text-emerald-600' : 'text-rose-600'}
                    `}>
                      {isPositive ? (
                        <TrendingUp className="w-3 h-3" />
                      ) : (
                        <TrendingDown className="w-3 h-3" />
                      )}
                      {delta.formatted}
                    </span>
                  </td>
                  <td className="px-2 py-2.5 text-right whitespace-nowrap">
                    <span className={`text-xs font-medium ${isPositive ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {fp.inPlaceRent > 0 ? `${((fp.askingRent - fp.inPlaceRent) / fp.inPlaceRent * 100).toFixed(1)}%` : '—'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            {(() => {
              const totalUnits = floorplans.reduce((s, f) => s + f.unitCount, 0);
              const totalOccUnits = floorplans.filter(f => f.inPlaceRent > 0).reduce((s, f) => s + f.unitCount, 0);
              const avgInPlace = totalOccUnits > 0 ? floorplans.filter(f => f.inPlaceRent > 0).reduce((s, f) => s + f.inPlaceRent * f.unitCount, 0) / totalOccUnits : 0;
              const avgAsking = totalUnits > 0 ? floorplans.reduce((s, f) => s + f.askingRent * f.unitCount, 0) / totalUnits : 0;
              const totalDelta = getDelta(avgInPlace, avgAsking);
              const deltaPct = avgInPlace > 0 ? ((avgAsking - avgInPlace) / avgInPlace * 100).toFixed(1) : '—';
              return (
                <tr className="border-t-2 border-slate-300 bg-slate-50 font-semibold text-slate-800">
                  <td className="px-2 py-2.5">
                    <div className="flex flex-col">
                      <span>Total</span>
                      <span className="text-xs text-slate-400 font-normal">{totalUnits} units</span>
                    </div>
                  </td>
                  <td className="px-2 py-2.5 text-right">{formatCurrency(avgInPlace)}</td>
                  <td className="px-2 py-2.5 text-right">{formatCurrency(avgAsking)}</td>
                  <td className="px-2 py-2.5 text-right">
                    <span className={`inline-flex items-center gap-1 text-xs font-medium ${totalDelta.value >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {totalDelta.formatted}
                    </span>
                  </td>
                  <td className="px-2 py-2.5 text-right">
                    <span className={`text-xs font-medium ${totalDelta.value >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {deltaPct !== '—' ? `${deltaPct}%` : '—'}
                    </span>
                  </td>
                </tr>
              );
            })()}
          </tfoot>
        </table>
      </div>}
    </div>
  );
}
