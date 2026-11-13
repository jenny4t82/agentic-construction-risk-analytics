import { useEffect, useState } from 'react';
import { CameraOff, Image as ImageIcon } from 'lucide-react';
import { fetchObservationImage } from '../api/client';

interface Props {
  observationId: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function ObservationThumbnail({ observationId, size = 'sm', className = '' }: Props) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    let active = true;
    let createdUrl: string | null = null;

    const loadThumbnail = async () => {
      setIsLoading(true);
      setHasError(false);
      try {
        // Prefer annotated overlay for quick visual inspection, fallback to original
        let url: string;
        try {
          url = await fetchObservationImage(observationId, 'annotated');
        } catch {
          url = await fetchObservationImage(observationId, 'original');
        }
        if (active) {
          createdUrl = url;
          setImageUrl(url);
        } else {
          URL.revokeObjectURL(url);
        }
      } catch {
        if (active) setHasError(true);
      } finally {
        if (active) setIsLoading(false);
      }
    };

    void loadThumbnail();

    return () => {
      active = false;
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl);
      }
    };
  }, [observationId]);

  const sizeClasses = {
    sm: 'w-12 h-12',
    md: 'w-16 h-16',
    lg: 'w-24 h-24',
  }[size];

  if (isLoading) {
    return (
      <div
        className={`${sizeClasses} rounded-lg bg-slate-100 border border-slate-200 animate-pulse flex items-center justify-center shrink-0 ${className}`}
        aria-label="Loading thumbnail"
      >
        <ImageIcon size={16} className="text-slate-300" />
      </div>
    );
  }

  if (hasError || !imageUrl) {
    return (
      <div
        className={`${sizeClasses} rounded-lg bg-slate-50 border border-dashed border-slate-200 flex flex-col items-center justify-center text-slate-400 shrink-0 ${className}`}
        title="Image not available"
      >
        <CameraOff size={16} className="text-slate-300" />
        {size !== 'sm' && <span className="text-[9px] mt-0.5">No image</span>}
      </div>
    );
  }

  return (
    <div
      className={`${sizeClasses} rounded-lg bg-slate-900 border border-slate-200 overflow-hidden shrink-0 flex items-center justify-center ${className}`}
    >
      <img
        src={imageUrl}
        alt={`Observation ${observationId} evidence`}
        className="w-full h-full object-cover"
        loading="lazy"
      />
    </div>
  );
}
