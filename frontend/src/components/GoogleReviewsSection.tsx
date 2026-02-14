/**
 * GoogleReviewsSection - Google Reviews tab with review cards, star distribution,
 * response tracking metrics, owner reply display, and filters.
 * Supports SerpAPI (full data with replies) and Google Places API (fallback, 5 reviews).
 */
import { useState, useEffect, useMemo } from 'react';
import { Star, ExternalLink, MessageSquare, Filter, CheckCircle2, Clock, XCircle, ArrowUpDown, TrendingUp } from 'lucide-react';
import { api } from '../api';

interface Review {
  author: string;
  author_photo: string;
  author_url: string;
  rating: number;
  text: string;
  time_desc: string;
  publish_time: string;
  google_maps_uri: string;
  has_response?: boolean;
  response_text?: string | null;
  response_date?: string | null;
  response_time?: string | null;
}

interface ReviewsData {
  rating: number;
  review_count: number;
  place_id: string;
  google_maps_url: string;
  reviews: Review[];
  star_distribution: Record<string, number>;
  needs_response: number;
  reviews_fetched: number;
  responded?: number;
  not_responded?: number;
  response_rate?: number;
  avg_response_hours?: number | null;
  avg_response_label?: string | null;
  source?: string;
  error?: string;
}

interface ApartmentsReview {
  review_id: string;
  author: string;
  rating: number;
  text: string;
  time_desc: string;
  has_response: boolean;
  response_text: string | null;
  response_date: string | null;
}

interface ApartmentsData {
  rating: number | null;
  review_count: number;
  reviews: ApartmentsReview[];
  star_distribution: Record<string, number>;
  reviews_fetched: number;
  responded: number;
  not_responded: number;
  needs_response: number;
  response_rate: number;
  source: string;
  url: string;
  error?: string;
}

interface GoogleReviewsSectionProps {
  propertyId: string;
  propertyIds?: string[];
  propertyName: string;
}

type ReviewSource = 'google' | 'apartments';
type ResponseFilterType = 'all' | 'responded' | 'not_responded' | 'needs_attention';
type SortType = 'newest' | 'oldest' | 'rating_high' | 'rating_low';

function parseTimeDesc(desc: string): number {
  if (!desc) return 0;
  const lower = desc.toLowerCase();
  const match = lower.match(/(\d+)/);
  const num = match ? parseInt(match[1]) : 1;
  if (lower.includes('hour')) return num;
  if (lower.includes('day')) return num * 24;
  if (lower.includes('week')) return num * 24 * 7;
  if (lower.includes('month')) return num * 24 * 30;
  if (lower.includes('year')) return num * 24 * 365;
  return 0;
}

function parseTimeDescToMonthsAgo(desc: string): number | null {
  if (!desc) return null;
  const lower = desc.toLowerCase().replace('edited ', '');
  const match = lower.match(/(\d+)/);
  const num = match ? parseInt(match[1]) : 1;
  if (lower.includes('hour') || lower.includes('minute')) return 0;
  if (lower.includes('day')) return 0;
  if (lower.includes('week')) return num <= 2 ? 0 : 1;
  if (lower.includes('month')) return num;
  if (lower.includes('year')) return num * 12;
  return null;
}

interface MonthBucket {
  label: string;
  count: number;
  avgRating: number;
  positive: number; // 4-5 star
  negative: number; // 1-3 star
}

function MonthlyTrendChart({ reviews }: { reviews: Review[] }) {
  const buckets = useMemo(() => {
    const now = new Date();
    const monthMap = new Map<number, { ratings: number[]; count: number; positive: number; negative: number }>();
    
    for (const r of reviews) {
      const monthsAgo = parseTimeDescToMonthsAgo(r.time_desc);
      if (monthsAgo === null || monthsAgo > 11) continue;
      if (!monthMap.has(monthsAgo)) {
        monthMap.set(monthsAgo, { ratings: [], count: 0, positive: 0, negative: 0 });
      }
      const b = monthMap.get(monthsAgo)!;
      b.ratings.push(r.rating);
      b.count++;
      if (r.rating >= 4) b.positive++;
      else b.negative++;
    }
    
    const result: MonthBucket[] = [];
    for (let i = 11; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const label = d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
      const entry = monthMap.get(i);
      result.push({
        label,
        count: entry?.count || 0,
        avgRating: entry && entry.ratings.length > 0
          ? Math.round(entry.ratings.reduce((a, b) => a + b, 0) / entry.ratings.length * 10) / 10
          : 0,
        positive: entry?.positive || 0,
        negative: entry?.negative || 0,
      });
    }
    return result;
  }, [reviews]);

  const maxCount = Math.max(...buckets.map(b => b.count), 1);
  const hasData = buckets.some(b => b.count > 0);

  if (!hasData) return null;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="w-4 h-4 text-slate-500" />
        <h3 className="text-sm font-semibold text-slate-700">Monthly Review Trend</h3>
        <span className="text-[10px] text-slate-400">Last 12 months · based on fetched reviews</span>
      </div>

      {/* Chart */}
      <div className="flex items-end gap-1.5" style={{ height: 160 }}>
        {buckets.map((b, i) => {
          const barHeight = b.count > 0 ? Math.max((b.count / maxCount) * 130, 8) : 0;
          const posH = b.count > 0 ? (b.positive / b.count) * barHeight : 0;
          const negH = barHeight - posH;
          return (
            <div key={i} className="flex-1 flex flex-col items-center justify-end h-full group relative">
              {/* Tooltip */}
              {b.count > 0 && (
                <div className="absolute -top-1 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-800 text-white text-[10px] rounded px-2 py-1 whitespace-nowrap z-10 pointer-events-none">
                  {b.count} reviews · {b.avgRating}★ avg
                </div>
              )}
              {/* Rating label */}
              {b.count > 0 && (
                <span className="text-[9px] font-semibold mb-0.5" style={{
                  color: b.avgRating >= 4 ? '#059669' : b.avgRating >= 3 ? '#d97706' : '#dc2626'
                }}>
                  {b.avgRating}
                </span>
              )}
              {/* Stacked bar */}
              <div className="w-full rounded-t" style={{ height: barHeight }}>
                {b.count > 0 && (
                  <>
                    <div className="w-full bg-emerald-400 rounded-t" style={{ height: posH }} />
                    {negH > 0 && <div className="w-full bg-rose-300" style={{ height: negH }} />}
                  </>
                )}
              </div>
              {/* Count label */}
              <span className="text-[9px] text-slate-400 mt-0.5 font-medium">{b.count || ''}</span>
              {/* Month label */}
              <span className="text-[8px] text-slate-400 mt-0.5">{b.label}</span>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 text-[10px] text-slate-500">
        <div className="flex items-center gap-1">
          <div className="w-2.5 h-2.5 rounded-sm bg-emerald-400" />
          <span>4-5★ (positive)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2.5 h-2.5 rounded-sm bg-rose-300" />
          <span>1-3★ (negative)</span>
        </div>
      </div>
    </div>
  );
}

function StarRating({ rating, size = 'sm' }: { rating: number; size?: 'sm' | 'lg' }) {
  const cls = size === 'lg' ? 'w-5 h-5' : 'w-3.5 h-3.5';
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map(s => (
        <Star
          key={s}
          className={`${cls} ${s <= rating ? 'text-yellow-400 fill-yellow-400' : 'text-slate-200 fill-slate-200'}`}
        />
      ))}
    </div>
  );
}

function StarBar({ star, count, total }: { star: number; count: number; total: number }) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-3 text-right text-slate-500 font-medium">{star}</span>
      <Star className="w-3 h-3 text-yellow-400 fill-yellow-400" />
      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className="h-full bg-yellow-400 rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-6 text-right text-slate-400">{count}</span>
    </div>
  );
}

export function GoogleReviewsSection({ propertyId, propertyIds, propertyName: _propertyName }: GoogleReviewsSectionProps) {
  const [data, setData] = useState<ReviewsData | null>(null);
  const [aptData, setAptData] = useState<ApartmentsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeSource, setActiveSource] = useState<ReviewSource>('google');
  const [starFilter, setStarFilter] = useState<number | null>(null);
  const [responseFilter, setResponseFilter] = useState<ResponseFilterType>('all');
  const [sortBy, setSortBy] = useState<SortType>('newest');

  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

  useEffect(() => {
    if (!effectiveIds.length) return;
    setLoading(true);
    // Fetch Apartments.com reviews in parallel
    Promise.all(effectiveIds.map(id => api.getApartmentsReviews(id).catch(() => null)))
      .then(results => {
        const valid = results.filter(r => r && !r.error) as ApartmentsData[];
        if (valid.length === 1) { setAptData(valid[0]); }
        else if (valid.length > 1) {
          // Merge multiple
          const allReviews = valid.flatMap(r => r.reviews || []);
          const mergedStarDist: Record<string, number> = {};
          for (const v of valid) { for (const [star, count] of Object.entries(v.star_distribution || {})) { mergedStarDist[star] = (mergedStarDist[star] || 0) + count; } }
          const totalFetched = valid.reduce((s, r) => s + (r.reviews_fetched || 0), 0);
          const totalResponded = valid.reduce((s, r) => s + (r.responded || 0), 0);
          const totalReviewCount = valid.reduce((s, r) => s + (r.review_count || 0), 0);
          const weightedRating = totalReviewCount > 0 ? valid.reduce((s, r) => s + (r.rating || 0) * (r.review_count || 0), 0) / totalReviewCount : null;
          setAptData({
            rating: weightedRating, review_count: totalReviewCount, reviews: allReviews,
            star_distribution: mergedStarDist, reviews_fetched: totalFetched,
            responded: totalResponded, not_responded: totalFetched - totalResponded,
            needs_response: valid.reduce((s, r) => s + (r.needs_response || 0), 0),
            response_rate: totalFetched > 0 ? Math.round((totalResponded / totalFetched) * 100) : 0,
            source: 'zembra/apartments.com', url: valid[0].url,
          });
        }
      }).catch(() => {});
    // Fetch Google reviews
    Promise.all(effectiveIds.map(id => api.getReviews(id).catch(() => null)))
      .then(results => {
        const valid = results.filter(Boolean) as ReviewsData[];
        if (valid.length === 0) { setData(null); return; }
        if (valid.length === 1) { setData(valid[0]); return; }
        // Merge multiple properties
        const totalReviewCount = valid.reduce((s, r) => s + (r.review_count || 0), 0);
        const weightedRating = totalReviewCount > 0
          ? valid.reduce((s, r) => s + (r.rating || 0) * (r.review_count || 0), 0) / totalReviewCount
          : 0;
        const allReviews = valid.flatMap(r => r.reviews || []);
        const mergedStarDist: Record<string, number> = {};
        for (const v of valid) {
          for (const [star, count] of Object.entries(v.star_distribution || {})) {
            mergedStarDist[star] = (mergedStarDist[star] || 0) + count;
          }
        }
        const totalFetched = valid.reduce((s, r) => s + (r.reviews_fetched || 0), 0);
        const totalResponded = valid.reduce((s, r) => s + (r.responded || 0), 0);
        const totalNotResponded = valid.reduce((s, r) => s + (r.not_responded || 0), 0);
        const totalNeedsResponse = valid.reduce((s, r) => s + (r.needs_response || 0), 0);
        const mergedResponseRate = totalFetched > 0 ? Math.round((totalResponded / totalFetched) * 100) : 0;
        // Pick best source type
        const source = valid.some(v => v.source === 'serpapi') ? 'serpapi'
          : valid.some(v => v.source === 'playwright') ? 'playwright' : valid[0].source;
        setData({
          rating: weightedRating,
          review_count: totalReviewCount,
          place_id: valid[0].place_id,
          google_maps_url: valid[0].google_maps_url,
          reviews: allReviews,
          star_distribution: mergedStarDist,
          needs_response: totalNeedsResponse,
          reviews_fetched: totalFetched,
          responded: totalResponded,
          not_responded: totalNotResponded,
          response_rate: mergedResponseRate,
          avg_response_hours: null,
          avg_response_label: null,
          source,
        });
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveIds.join(',')]);

  const hasFullData = data?.source === 'serpapi' || data?.source === 'playwright';

  const filteredReviews = useMemo(() => {
    if (!data) return [];
    let reviews = data.reviews;
    if (starFilter !== null) {
      reviews = reviews.filter(r => r.rating === starFilter);
    }
    if (responseFilter === 'responded') {
      reviews = reviews.filter(r => r.has_response);
    } else if (responseFilter === 'not_responded') {
      reviews = reviews.filter(r => !r.has_response);
    } else if (responseFilter === 'needs_attention') {
      reviews = reviews.filter(r => !r.has_response && r.rating <= 3);
    }
    reviews = [...reviews].sort((a, b) => {
      switch (sortBy) {
        case 'newest': return parseTimeDesc(a.time_desc) - parseTimeDesc(b.time_desc);
        case 'oldest': return parseTimeDesc(b.time_desc) - parseTimeDesc(a.time_desc);
        case 'rating_high': return b.rating - a.rating;
        case 'rating_low': return a.rating - b.rating;
        default: return 0;
      }
    });
    return reviews;
  }, [data, starFilter, responseFilter, sortBy]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
        <div className="animate-pulse text-sm text-slate-400">Loading reviews...</div>
      </div>
    );
  }

  if (!data || data.error) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
        <p className="text-sm text-slate-400">{data?.error || 'Unable to load reviews'}</p>
      </div>
    );
  }

  const responseRate = data.response_rate ?? 0;
  const responded = data.responded ?? 0;
  const notResponded = data.not_responded ?? 0;

  // Apartments.com derived values
  const aptResponseRate = aptData?.response_rate ?? 0;
  const aptResponded = aptData?.responded ?? 0;
  const aptNotResponded = aptData?.not_responded ?? 0;

  const aptFilteredReviews = (() => {
    if (!aptData) return [];
    let reviews: ApartmentsReview[] = aptData.reviews;
    if (starFilter !== null) reviews = reviews.filter(r => r.rating === starFilter);
    if (responseFilter === 'responded') reviews = reviews.filter(r => r.has_response);
    else if (responseFilter === 'not_responded') reviews = reviews.filter(r => !r.has_response);
    else if (responseFilter === 'needs_attention') reviews = reviews.filter(r => !r.has_response && r.rating <= 3);
    reviews = [...reviews].sort((a, b) => {
      switch (sortBy) {
        case 'newest': return new Date(b.time_desc || 0).getTime() - new Date(a.time_desc || 0).getTime();
        case 'oldest': return new Date(a.time_desc || 0).getTime() - new Date(b.time_desc || 0).getTime();
        case 'rating_high': return b.rating - a.rating;
        case 'rating_low': return a.rating - b.rating;
        default: return 0;
      }
    });
    return reviews;
  })();

  return (
    <div className="space-y-6">
      {/* Source Tabs */}
      <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1 w-fit">
        <button
          onClick={() => { setActiveSource('google'); setStarFilter(null); setResponseFilter('all'); }}
          className={`px-4 py-2 text-xs font-semibold rounded-md transition-all ${
            activeSource === 'google'
              ? 'bg-white text-slate-800 shadow-sm'
              : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          Google {data.rating ? `(${data.rating.toFixed(1)}★)` : ''}
        </button>
        {aptData && aptData.rating && (
          <button
            onClick={() => { setActiveSource('apartments'); setStarFilter(null); setResponseFilter('all'); }}
            className={`px-4 py-2 text-xs font-semibold rounded-md transition-all ${
              activeSource === 'apartments'
                ? 'bg-white text-slate-800 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Apartments.com {aptData.rating ? `(${aptData.rating.toFixed?.(1) ?? aptData.rating}★)` : ''}
          </button>
        )}
      </div>
      {/* Top Row: Rating Summary + Response Metrics + Star Distribution */}
      <div className="grid grid-cols-12 gap-6">
        {/* Overall Rating */}
        <div className="col-span-12 md:col-span-3">
          <div className="bg-white rounded-xl border border-slate-200 p-6 text-center">
            <div className="text-5xl font-bold text-slate-900">
              {activeSource === 'google'
                ? (data.rating?.toFixed(1) || '—')
                : (aptData?.rating?.toFixed?.(1) ?? aptData?.rating ?? '—')
              }
            </div>
            <StarRating rating={Math.round(activeSource === 'google' ? (data.rating || 0) : (aptData?.rating || 0))} size="lg" />
            <p className="text-sm text-slate-500 mt-2">
              {activeSource === 'google'
                ? `${data.review_count.toLocaleString()} reviews on Google`
                : `${aptData?.review_count?.toLocaleString() ?? 0} reviews on Apartments.com`
              }
            </p>
            <p className="text-[10px] text-slate-400 mt-1">
              {activeSource === 'google'
                ? `${data.reviews_fetched} fetched${data.source ? ` via ${data.source}` : ''}`
                : `${aptData?.reviews_fetched ?? 0} fetched via Zembra`
              }
            </p>
            {activeSource === 'google' && data.google_maps_url && (
              <a
                href={data.google_maps_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 mt-3 text-xs text-indigo-600 hover:text-indigo-700 font-medium"
              >
                View on Google Maps <ExternalLink className="w-3 h-3" />
              </a>
            )}
            {activeSource === 'apartments' && aptData?.url && (
              <a
                href={aptData.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 mt-3 text-xs text-indigo-600 hover:text-indigo-700 font-medium"
              >
                View on Apartments.com <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        </div>

        {/* Response Tracking */}
        <div className="col-span-12 md:col-span-5">
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="flex items-center gap-2 mb-4">
              <MessageSquare className="w-4 h-4 text-slate-500" />
              <h3 className="text-sm font-semibold text-slate-700">Response Tracking</h3>
              {(hasFullData || activeSource === 'apartments') && (
                <span className="px-1.5 py-0.5 text-[9px] font-medium bg-emerald-100 text-emerald-700 rounded">live</span>
              )}
            </div>

            {(() => {
              const showFull = hasFullData || activeSource === 'apartments';
              const dTotal = activeSource === 'google' ? data.reviews_fetched : (aptData?.reviews_fetched ?? 0);
              const dResponded = activeSource === 'google' ? responded : aptResponded;
              const dNotResponded = activeSource === 'google' ? notResponded : aptNotResponded;
              const dNeedsResponse = activeSource === 'google' ? data.needs_response : (aptData?.needs_response ?? 0);
              const dRate = activeSource === 'google' ? responseRate : aptResponseRate;
              if (showFull) return (
                <>
                  <div className="grid grid-cols-4 gap-3 mb-4">
                    <button onClick={() => setResponseFilter('all')} className="text-center">
                      <div className="text-2xl font-bold text-slate-900">{dTotal}</div>
                      <div className="text-[10px] text-slate-500 uppercase">Total</div>
                    </button>
                    <button onClick={() => setResponseFilter('responded')} className="text-center">
                      <div className="text-2xl font-bold text-emerald-600">{dResponded}</div>
                      <div className="text-[10px] text-slate-500 uppercase">Responded</div>
                    </button>
                    <button onClick={() => setResponseFilter('not_responded')} className="text-center">
                      <div className={`text-2xl font-bold ${dNotResponded > 0 ? 'text-rose-600' : 'text-slate-400'}`}>
                        {dNotResponded}
                      </div>
                      <div className="text-[10px] text-slate-500 uppercase">No Reply</div>
                    </button>
                    <button onClick={() => setResponseFilter('needs_attention')} className="text-center">
                      <div className={`text-2xl font-bold ${dNeedsResponse > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                        {dNeedsResponse}
                      </div>
                      <div className="text-[10px] text-slate-500 uppercase">≤3★ No Reply</div>
                    </button>
                  </div>
                  <div className="mb-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-slate-500">Response Rate</span>
                      <span className={`text-sm font-bold ${dRate >= 80 ? 'text-emerald-600' : dRate >= 50 ? 'text-amber-600' : 'text-rose-600'}`}>
                        {dRate}%
                      </span>
                    </div>
                    <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${dRate >= 80 ? 'bg-emerald-500' : dRate >= 50 ? 'bg-amber-500' : 'bg-rose-500'}`}
                        style={{ width: `${dRate}%` }}
                      />
                    </div>
                  </div>
                  {activeSource === 'google' && data.avg_response_label && (
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <Clock className="w-3.5 h-3.5" />
                      <span>Avg response time: <span className="font-semibold text-slate-700">{data.avg_response_label}</span></span>
                    </div>
                  )}
                </>
              );
              return (
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-slate-900">{dTotal}</div>
                    <div className="text-[10px] text-slate-500 uppercase">Reviews Loaded</div>
                  </div>
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${dNeedsResponse > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                      {dNeedsResponse}
                    </div>
                    <div className="text-[10px] text-slate-500 uppercase">≤3★ Reviews</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-slate-400">—</div>
                    <div className="text-[10px] text-slate-500 uppercase">Response Rate</div>
                  </div>
                </div>
              );
            })()}

            {activeSource === 'google' && !hasFullData && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mt-3">
                <p className="text-[11px] text-amber-700">
                  Add <span className="font-mono font-semibold">SERPAPI_API_KEY</span> to .env for full response tracking
                  (all reviews + owner replies + response times).
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Star Distribution */}
        <div className="col-span-12 md:col-span-4">
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Star Distribution</h3>
            <p className="text-[10px] text-slate-400 mb-3">Based on {activeSource === 'google' ? data.reviews_fetched : (aptData?.reviews_fetched ?? 0)} reviews fetched</p>
            <div className="space-y-2">
              {[5, 4, 3, 2, 1].map(s => {
                const dist = activeSource === 'google' ? data.star_distribution : (aptData?.star_distribution ?? {});
                const total = activeSource === 'google' ? data.reviews_fetched : (aptData?.reviews_fetched ?? 0);
                return (
                  <button
                    key={s}
                    onClick={() => setStarFilter(starFilter === s ? null : s)}
                    className={`w-full rounded transition-colors ${starFilter === s ? 'bg-yellow-50 ring-1 ring-yellow-300' : 'hover:bg-slate-50'}`}
                  >
                    <StarBar star={s} count={dist[String(s)] || 0} total={total} />
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Monthly Trend Chart (Google only — apartments uses absolute dates) */}
      {activeSource === 'google' && <MonthlyTrendChart reviews={data.reviews} />}

      {/* Filters + Reviews List */}
      <div className="bg-white rounded-xl border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <h3 className="text-sm font-semibold text-slate-700">
              Reviews {starFilter ? `(${starFilter}★)` : ''} — {activeSource === 'google' ? filteredReviews.length : aptFilteredReviews.length} shown
            </h3>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {(hasFullData || activeSource === 'apartments') && (
              <>
                <button
                  onClick={() => setResponseFilter(responseFilter === 'responded' ? 'all' : 'responded')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                    responseFilter === 'responded' ? 'bg-emerald-100 text-emerald-700 ring-1 ring-emerald-300' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  ✓ Responded
                </button>
                <button
                  onClick={() => setResponseFilter(responseFilter === 'not_responded' ? 'all' : 'not_responded')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                    responseFilter === 'not_responded' ? 'bg-amber-100 text-amber-700 ring-1 ring-amber-300' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  No Reply
                </button>
              </>
            )}
            <button
              onClick={() => setResponseFilter(responseFilter === 'needs_attention' ? 'all' : 'needs_attention')}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                responseFilter === 'needs_attention' ? 'bg-rose-100 text-rose-700 ring-1 ring-rose-300' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              ≤3★ Need Attention
            </button>
            <div className="flex items-center gap-1.5 ml-2 pl-2 border-l border-slate-200">
              <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value as SortType)}
                className="text-xs font-medium bg-slate-100 text-slate-600 rounded-lg px-2 py-1.5 border-0 cursor-pointer hover:bg-slate-200 focus:ring-1 focus:ring-indigo-300 focus:outline-none"
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="rating_high">Highest rated</option>
                <option value="rating_low">Lowest rated</option>
              </select>
            </div>
            {(starFilter !== null || responseFilter !== 'all') && (
              <button
                onClick={() => { setStarFilter(null); setResponseFilter('all'); }}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200"
              >
                Clear All
              </button>
            )}
          </div>
        </div>

        <div className="divide-y divide-slate-100">
          {activeSource === 'google' && (
            <>
              {filteredReviews.length === 0 && (
                <div className="p-6 text-center text-sm text-slate-400">No reviews match the current filter</div>
              )}
              {filteredReviews.map((review, i) => (
                <div key={i} className={`px-6 py-4 ${review.rating <= 3 && !review.has_response ? 'bg-rose-50/50' : ''}`}>
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0">
                      {review.author_photo ? (
                        <img src={review.author_photo} alt="" className="w-10 h-10 rounded-full object-cover" />
                      ) : (
                        <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center text-sm font-bold text-slate-500">
                          {review.author.charAt(0).toUpperCase()}
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-slate-800">{review.author}</span>
                        <StarRating rating={review.rating} />
                        <span className="text-xs text-slate-400">{review.time_desc}</span>
                        {hasFullData && review.has_response && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[9px] font-semibold bg-emerald-100 text-emerald-700 rounded uppercase">
                            <CheckCircle2 className="w-2.5 h-2.5" /> replied
                          </span>
                        )}
                        {hasFullData && !review.has_response && review.rating <= 3 && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[9px] font-semibold bg-rose-100 text-rose-700 rounded uppercase">
                            <XCircle className="w-2.5 h-2.5" /> needs reply
                          </span>
                        )}
                        {hasFullData && !review.has_response && review.rating > 3 && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[9px] font-semibold bg-slate-100 text-slate-500 rounded uppercase">
                            no reply
                          </span>
                        )}
                        {!hasFullData && review.rating <= 3 && (
                          <span className="px-1.5 py-0.5 text-[9px] font-semibold bg-rose-100 text-rose-700 rounded uppercase">
                            needs attention
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-600 mt-1.5 leading-relaxed">{review.text}</p>
                      {review.has_response && review.response_text && (
                        <div className="mt-3 ml-4 pl-3 border-l-2 border-indigo-200 bg-indigo-50/50 rounded-r-lg p-3">
                          <div className="flex items-center gap-1.5 mb-1">
                            <MessageSquare className="w-3 h-3 text-indigo-500" />
                            <span className="text-[11px] font-semibold text-indigo-700">Owner Response</span>
                            {review.response_date && (
                              <span className="text-[10px] text-indigo-400">· {review.response_date}</span>
                            )}
                          </div>
                          <p className="text-[12px] text-slate-600 leading-relaxed">{review.response_text}</p>
                        </div>
                      )}
                      {review.google_maps_uri && (
                        <a
                          href={review.google_maps_uri}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 mt-2 text-xs text-indigo-600 hover:text-indigo-700 font-medium"
                        >
                          {!review.has_response && review.rating <= 3 ? 'Respond on Google' : 'View on Google'} <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </>
          )}

          {activeSource === 'apartments' && (
            <>
              {aptFilteredReviews.length === 0 && (
                <div className="p-6 text-center text-sm text-slate-400">No reviews match the current filter</div>
              )}
              {aptFilteredReviews.map((review, i) => (
                <div key={i} className={`px-6 py-4 ${review.rating <= 3 && !review.has_response ? 'bg-rose-50/50' : ''}`}>
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0">
                      <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center text-sm font-bold text-orange-600">
                        {review.author ? review.author.charAt(0).toUpperCase() : 'A'}
                      </div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-slate-800">{review.author || 'Verified Resident'}</span>
                        <StarRating rating={review.rating} />
                        <span className="text-xs text-slate-400">
                          {review.time_desc ? new Date(review.time_desc).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : ''}
                        </span>
                        {review.has_response && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[9px] font-semibold bg-emerald-100 text-emerald-700 rounded uppercase">
                            <CheckCircle2 className="w-2.5 h-2.5" /> replied
                          </span>
                        )}
                        {!review.has_response && review.rating <= 3 && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[9px] font-semibold bg-rose-100 text-rose-700 rounded uppercase">
                            <XCircle className="w-2.5 h-2.5" /> needs reply
                          </span>
                        )}
                        {!review.has_response && review.rating > 3 && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[9px] font-semibold bg-slate-100 text-slate-500 rounded uppercase">
                            no reply
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-600 mt-1.5 leading-relaxed">{review.text}</p>
                      {review.has_response && review.response_text && (
                        <div className="mt-3 ml-4 pl-3 border-l-2 border-orange-200 bg-orange-50/50 rounded-r-lg p-3">
                          <div className="flex items-center gap-1.5 mb-1">
                            <MessageSquare className="w-3 h-3 text-orange-500" />
                            <span className="text-[11px] font-semibold text-orange-700">Management Response</span>
                          </div>
                          <p className="text-[12px] text-slate-600 leading-relaxed">{review.response_text}</p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
