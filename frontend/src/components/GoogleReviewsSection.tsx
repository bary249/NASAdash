/**
 * GoogleReviewsSection - Google Reviews tab with review cards, star distribution,
 * response tracking metrics, owner reply display, and filters.
 * Supports SerpAPI (full data with replies) and Google Places API (fallback, 5 reviews).
 */
import { useState, useEffect, useMemo } from 'react';
import { Star, ExternalLink, MessageSquare, Filter, CheckCircle2, Clock, XCircle, ArrowUpDown } from 'lucide-react';
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

interface GoogleReviewsSectionProps {
  propertyId: string;
  propertyName: string;
}

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

export function GoogleReviewsSection({ propertyId, propertyName: _propertyName }: GoogleReviewsSectionProps) {
  const [data, setData] = useState<ReviewsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [starFilter, setStarFilter] = useState<number | null>(null);
  const [responseFilter, setResponseFilter] = useState<ResponseFilterType>('all');
  const [sortBy, setSortBy] = useState<SortType>('newest');

  useEffect(() => {
    if (!propertyId) return;
    setLoading(true);
    api.getReviews(propertyId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [propertyId]);

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

  return (
    <div className="space-y-6">
      {/* Top Row: Rating Summary + Response Metrics + Star Distribution */}
      <div className="grid grid-cols-12 gap-6">
        {/* Overall Rating */}
        <div className="col-span-12 md:col-span-3">
          <div className="bg-white rounded-xl border border-slate-200 p-6 text-center">
            <div className="text-5xl font-bold text-slate-900">{data.rating?.toFixed(1) || '—'}</div>
            <StarRating rating={Math.round(data.rating || 0)} size="lg" />
            <p className="text-sm text-slate-500 mt-2">{data.review_count.toLocaleString()} reviews on Google</p>
            <p className="text-[10px] text-slate-400 mt-1">
              {data.reviews_fetched} fetched{data.source ? ` via ${data.source}` : ''}
            </p>
            {data.google_maps_url && (
              <a
                href={data.google_maps_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 mt-3 text-xs text-indigo-600 hover:text-indigo-700 font-medium"
              >
                View on Google Maps <ExternalLink className="w-3 h-3" />
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
              {hasFullData && (
                <span className="px-1.5 py-0.5 text-[9px] font-medium bg-emerald-100 text-emerald-700 rounded">live</span>
              )}
            </div>

            {hasFullData ? (
              <>
                <div className="grid grid-cols-4 gap-3 mb-4">
                  <button onClick={() => setResponseFilter('all')} className="text-center">
                    <div className="text-2xl font-bold text-slate-900">{data.reviews_fetched}</div>
                    <div className="text-[10px] text-slate-500 uppercase">Total</div>
                  </button>
                  <button onClick={() => setResponseFilter('responded')} className="text-center">
                    <div className="text-2xl font-bold text-emerald-600">{responded}</div>
                    <div className="text-[10px] text-slate-500 uppercase">Responded</div>
                  </button>
                  <button onClick={() => setResponseFilter('not_responded')} className="text-center">
                    <div className={`text-2xl font-bold ${notResponded > 0 ? 'text-rose-600' : 'text-slate-400'}`}>
                      {notResponded}
                    </div>
                    <div className="text-[10px] text-slate-500 uppercase">No Reply</div>
                  </button>
                  <button onClick={() => setResponseFilter('needs_attention')} className="text-center">
                    <div className={`text-2xl font-bold ${data.needs_response > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                      {data.needs_response}
                    </div>
                    <div className="text-[10px] text-slate-500 uppercase">≤3★ No Reply</div>
                  </button>
                </div>

                {/* Response Rate Bar */}
                <div className="mb-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-slate-500">Response Rate</span>
                    <span className={`text-sm font-bold ${responseRate >= 80 ? 'text-emerald-600' : responseRate >= 50 ? 'text-amber-600' : 'text-rose-600'}`}>
                      {responseRate}%
                    </span>
                  </div>
                  <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${responseRate >= 80 ? 'bg-emerald-500' : responseRate >= 50 ? 'bg-amber-500' : 'bg-rose-500'}`}
                      style={{ width: `${responseRate}%` }}
                    />
                  </div>
                </div>

                {/* Avg Response Time */}
                {data.avg_response_label && (
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <Clock className="w-3.5 h-3.5" />
                    <span>Avg response time: <span className="font-semibold text-slate-700">{data.avg_response_label}</span></span>
                  </div>
                )}
              </>
            ) : (
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-slate-900">{data.reviews_fetched}</div>
                  <div className="text-[10px] text-slate-500 uppercase">Reviews Loaded</div>
                </div>
                <div className="text-center">
                  <div className={`text-2xl font-bold ${data.needs_response > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                    {data.needs_response}
                  </div>
                  <div className="text-[10px] text-slate-500 uppercase">≤3★ Reviews</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-slate-400">—</div>
                  <div className="text-[10px] text-slate-500 uppercase">Response Rate</div>
                </div>
              </div>
            )}

            {!hasFullData && (
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
            <p className="text-[10px] text-slate-400 mb-3">Based on {data.reviews_fetched} reviews fetched</p>
            <div className="space-y-2">
              {[5, 4, 3, 2, 1].map(s => (
                <button
                  key={s}
                  onClick={() => setStarFilter(starFilter === s ? null : s)}
                  className={`w-full rounded transition-colors ${starFilter === s ? 'bg-yellow-50 ring-1 ring-yellow-300' : 'hover:bg-slate-50'}`}
                >
                  <StarBar star={s} count={data.star_distribution[String(s)] || 0} total={data.reviews_fetched} />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Filters + Reviews List */}
      <div className="bg-white rounded-xl border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <h3 className="text-sm font-semibold text-slate-700">
              Reviews {starFilter ? `(${starFilter}★)` : ''} — {filteredReviews.length} shown
            </h3>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {hasFullData && (
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
          {filteredReviews.length === 0 && (
            <div className="p-6 text-center text-sm text-slate-400">No reviews match the current filter</div>
          )}
          {filteredReviews.map((review, i) => (
            <div key={i} className={`px-6 py-4 ${review.rating <= 3 && !review.has_response ? 'bg-rose-50/50' : ''}`}>
              <div className="flex items-start gap-3">
                {/* Author Avatar */}
                <div className="flex-shrink-0">
                  {review.author_photo ? (
                    <img src={review.author_photo} alt="" className="w-10 h-10 rounded-full object-cover" />
                  ) : (
                    <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center text-sm font-bold text-slate-500">
                      {review.author.charAt(0).toUpperCase()}
                    </div>
                  )}
                </div>

                {/* Review Content */}
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

                  {/* Owner Reply (SerpAPI only) */}
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

                  {/* Action link */}
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
        </div>
      </div>
    </div>
  );
}
