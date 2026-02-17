/**
 * PropertyCard - Large property image card with name, units, rating
 * Matches design: Left side property card with building image
 */
import { Building2, Star, MapPin } from 'lucide-react';

interface PropertyCardProps {
  name: string;
  floors?: number;
  units: number;
  rating?: number;
  reviewCount?: number;
  imageUrl?: string;
  address?: string;
  city?: string;
  state?: string;
  vacantReady?: number;
  agedVacancy?: number;
}

export function PropertyCard({
  name,
  floors,
  units,
  rating,
  reviewCount,
  imageUrl,
  address,
  city,
  state,
  vacantReady = 0,
  agedVacancy = 0,
}: PropertyCardProps) {
  // Default building image (gradient placeholder)
  const hasImage = imageUrl && imageUrl.length > 0;

  return (
    <div className="relative h-full min-h-[280px] rounded-2xl overflow-hidden shadow-lg group">
      {/* Background Image or Gradient */}
      {hasImage ? (
        <img 
          src={imageUrl} 
          alt={name}
          className="absolute inset-0 w-full h-full object-cover"
          referrerPolicy="no-referrer"
          crossOrigin="anonymous"
        />
      ) : (
        <div className="absolute inset-0 bg-gradient-to-br from-slate-700 via-slate-800 to-slate-900">
          {/* Decorative building silhouette */}
          <div className="absolute bottom-0 left-0 right-0 h-3/4 flex items-end justify-center opacity-20">
            <Building2 className="w-48 h-48 text-white" />
          </div>
        </div>
      )}
      
      {/* Gradient Overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
      
      {/* Content */}
      <div className="absolute bottom-0 left-0 right-0 p-5 text-white">
        <h2 className="text-2xl font-bold mb-1 drop-shadow-lg">{name}</h2>
        
        <div className="flex items-center gap-3 text-sm text-white/80">
          {floors && (
            <>
              <span>{floors} Floors</span>
              <span className="text-white/40">•</span>
            </>
          )}
          <span>{units} Units</span>
          {rating != null && (
            <>
              <span className="text-white/40">•</span>
              <div className="flex items-center gap-1">
                <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />
                <span>{rating.toFixed(1)}{reviewCount ? ` (${reviewCount})` : ''}</span>
              </div>
            </>
          )}
        </div>
        
        {/* Location */}
        {(address || city) && (
          <div className="flex items-center gap-1.5 mt-2 text-xs text-white/60">
            <MapPin className="w-3.5 h-3.5" />
            <span>{address || `${city}, ${state}`}</span>
          </div>
        )}

        {/* Vacancy Badges - matching design */}
        <div className="flex items-center gap-2 mt-3">
          <span className="px-2.5 py-1 bg-emerald-500 text-white text-xs font-medium rounded-full">
            {vacantReady} Ready
          </span>
          {agedVacancy > 0 && (
            <span className="px-2.5 py-1 bg-rose-400 text-white text-xs font-medium rounded-full">
              {agedVacancy} unit &gt;90 days
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
