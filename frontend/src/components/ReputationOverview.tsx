/**
 * ReputationOverview - Multi-source reputation summary with Review Power metrics.
 * Shows ratings from Google (+ placeholder ILS slots) and response tracking.
 * Per PHH design partner feedback.
 */
import { useState, useEffect } from 'react';
import { Star, MessageSquare, AlertTriangle, ExternalLink, CheckCircle2 } from 'lucide-react';
import { SectionHeader } from './SectionHeader';
import { api } from '../api';

interface ReputationSource {
  source: string;
  name: string;
  rating: number | null;
  review_count: number;
  url: string;
  star_distribution: Record<string, number> | null;
}

interface ReviewPower {
  response_rate: number;
  avg_response_hours: number | null;
  avg_response_label: string | null;
  needs_attention: number;
  responded: number;
  not_responded: number;
  total_reviews: number;
}

interface ReputationData {
  property_id: string;
  overall_rating: number;
  sources: ReputationSource[];
  review_power: ReviewPower;
}

interface Props {
  propertyId: string;
  propertyIds?: string[];
}

function StarRating({ rating }: { rating: number }) {
  const stars = [];
  for (let i = 1; i <= 5; i++) {
    const fill = rating >= i ? 'text-yellow-400' : rating >= i - 0.5 ? 'text-yellow-300' : 'text-slate-200';
    stars.push(<Star key={i} className={`w-4 h-4 ${fill} fill-current`} />);
  }
  return <div className="flex items-center gap-0.5">{stars}</div>;
}

function RatingGauge({ value, max = 5, color }: { value: number; max?: number; color: string }) {
  const pct = (value / max) * 100;
  return (
    <div className="h-2 bg-slate-200 rounded-full overflow-hidden w-full">
      <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function ReputationOverview({ propertyId, propertyIds }: Props) {
  const [data, setData] = useState<ReputationData | null>(null);
  const [loading, setLoading] = useState(true);

  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

  useEffect(() => {
    setData(null);
    setLoading(true);
    // Use first property for reputation (multi-property merge not meaningful for reviews)
    api.getReputation(effectiveIds[0])
      .then(d => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
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

  if (!data) {
    return (
      <div className="venn-section">
        <SectionHeader title="Reputation & Reviews" icon={Star} />
        <div className="text-center py-8 text-slate-500">No reputation data available</div>
      </div>
    );
  }

  const { sources, review_power } = data;
  const activeSources = sources.filter(s => s.rating !== null);
  const pendingSources: ReputationSource[] = [];

  return (
    <div className="venn-section">
      <SectionHeader title="Reputation & Reviews" icon={Star} />

      <div className="grid md:grid-cols-2 gap-6">
        {/* Left: ILS Ratings Grid */}
        <div className="space-y-4">
          <h4 className="text-sm font-semibold text-slate-700">Listing Ratings</h4>

          {/* Active sources with data */}
          {activeSources.map(src => (
            <div key={src.source} className="flex items-center gap-4 bg-white border border-slate-200 rounded-xl p-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold text-slate-800">{src.name}</span>
                  {src.url && (
                    <a href={src.url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:text-blue-700">
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <StarRating rating={src.rating!} />
                  <span className="text-lg font-bold text-slate-800">{src.rating?.toFixed(1)}</span>
                  <span className="text-xs text-slate-500">({src.review_count} reviews)</span>
                </div>
                <RatingGauge value={src.rating!} color="bg-yellow-400" />
              </div>
            </div>
          ))}

          {/* Pending ILS sources (no data yet) */}
          {pendingSources.map(src => (
            <div key={src.source} className="flex items-center gap-4 bg-slate-50 border border-dashed border-slate-200 rounded-xl p-4 opacity-60">
              <div className="flex-1">
                <span className="text-sm font-medium text-slate-500">{src.name}</span>
                <div className="text-xs text-slate-400 mt-1">Coming soon</div>
              </div>
            </div>
          ))}
        </div>

        {/* Right: Review Power */}
        <div className="bg-slate-50 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <MessageSquare className="w-4 h-4 text-indigo-500" />
            <h4 className="text-sm font-semibold text-slate-700">Review Power</h4>
          </div>

          <div className="space-y-4">
            {/* Response Rate */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-slate-600">Response Rate</span>
                <span className={`text-sm font-bold ${review_power.response_rate >= 80 ? 'text-emerald-600' : review_power.response_rate >= 50 ? 'text-amber-600' : 'text-red-600'}`}>
                  {review_power.response_rate}%
                </span>
              </div>
              <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    review_power.response_rate >= 80 ? 'bg-emerald-400' :
                    review_power.response_rate >= 50 ? 'bg-amber-400' : 'bg-red-400'
                  }`}
                  style={{ width: `${review_power.response_rate}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-slate-400 mt-1">
                <span>{review_power.responded} responded</span>
                <span>{review_power.not_responded} pending</span>
              </div>
            </div>

            {/* Needs Attention */}
            {review_power.needs_attention > 0 && (
              <div className="flex items-center gap-3 bg-red-50 rounded-lg p-3 border border-red-200">
                <AlertTriangle className="w-5 h-5 text-red-500" />
                <div>
                  <div className="text-xs text-red-600">Needs Attention</div>
                  <div className="text-sm font-bold text-red-700">
                    {review_power.needs_attention} low-rated reviews without response
                  </div>
                </div>
              </div>
            )}

            {review_power.needs_attention === 0 && review_power.total_reviews > 0 && (
              <div className="flex items-center gap-3 bg-emerald-50 rounded-lg p-3 border border-emerald-200">
                <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                <div>
                  <div className="text-xs text-emerald-600">All Clear</div>
                  <div className="text-sm font-bold text-emerald-700">
                    No low-rated reviews need a response
                  </div>
                </div>
              </div>
            )}

            {/* Total Reviews */}
            <div className="text-center pt-2 border-t border-slate-200">
              <span className="text-xs text-slate-500">
                Based on {review_power.total_reviews} fetched reviews
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
