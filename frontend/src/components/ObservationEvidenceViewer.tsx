import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useModalFocus } from '../utils/useModalFocus';
import { CameraOff, Maximize2, X } from 'lucide-react';
import { fetchObservationImage } from '../api/client';

interface Props {
  observationId: string;
}

export function ObservationEvidenceViewer({ observationId }: Props) {
  const [images, setImages] = useState<{ original?: string; annotated?: string }>({});
  const [loading, setLoading] = useState(true);
  const [modalImage, setModalImage] = useState<{ url: string; title: string } | null>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const closeModal = useCallback(() => setModalImage(null), []);
  useModalFocus(!!modalImage, modalRef, closeModal);

  useEffect(() => {
    let active = true;
    const urls: string[] = [];

    const loadVariant = async (variant: 'original' | 'annotated') => {
      try {
        const url = await fetchObservationImage(observationId, variant);
        urls.push(url);
        if (active) {
          setImages((prev) => ({ ...prev, [variant]: url }));
        } else {
          URL.revokeObjectURL(url);
        }
      } catch {
        // Variant may be unavailable for older observations or text-only entries
      }
    };

    void Promise.allSettled([loadVariant('original'), loadVariant('annotated')]).then(() => {
      if (active) setLoading(false);
    });

    return () => {
      active = false;
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [observationId]);

  return (
    <div>
      <h5 className="font-bold text-slate-700 mb-2.5 uppercase tracking-wider text-[11px] flex items-center justify-between">
        <span>Image Evidence & Detections</span>
        <span className="text-slate-400 font-normal lowercase">Authenticated evidence</span>
      </h5>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="h-48 rounded-xl bg-slate-100 border border-slate-200 animate-pulse flex items-center justify-center">
            <span className="text-xs text-slate-400 font-medium">Loading original…</span>
          </div>
          <div className="h-48 rounded-xl bg-slate-100 border border-slate-200 animate-pulse flex items-center justify-center">
            <span className="text-xs text-slate-400 font-medium">Loading detection overlay…</span>
          </div>
        </div>
      ) : !images.original && !images.annotated ? (
        <div className="p-6 rounded-xl border border-dashed border-slate-200 bg-white text-center">
          <CameraOff size={24} className="text-slate-300 mx-auto mb-1.5" />
          <p className="text-xs text-slate-500 font-medium">Visual evidence unavailable for this observation.</p>
          <p className="text-[11px] text-slate-400 mt-0.5">Older persisted records or synthetic submissions do not carry stored images.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {images.original && (
            <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-2xs group flex flex-col">
              <div className="px-3 py-2 bg-slate-50 border-b border-slate-100 flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-700">Original Upload</span>
                <button
                  type="button"
                  onClick={() => setModalImage({ url: images.original!, title: `Original Image · Observation ${observationId}` })}
                  className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200/50 transition-colors"
                  title="Enlarge original image"
                  aria-label="Enlarge original image"
                >
                  <Maximize2 size={13} />
                </button>
              </div>
              <button type="button" aria-label="Preview original image" onClick={() => setModalImage({ url: images.original!, title: `Original Image · Observation ${observationId}` })} className="bg-slate-950 p-1 flex items-center justify-center min-h-[180px] max-h-[280px]">
                <img
                  src={images.original}
                  alt={`Original upload for observation ${observationId}`}
                  className="max-h-[260px] w-auto max-w-full object-contain cursor-zoom-in"
                  onClick={() => setModalImage({ url: images.original!, title: `Original Image · Observation ${observationId}` })}
                  loading="lazy"
                />
              </button>
            </div>
          )}

          {images.annotated && (
            <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-2xs group flex flex-col">
              <div className="px-3 py-2 bg-slate-50 border-b border-slate-100 flex items-center justify-between">
                <span className="text-xs font-semibold text-teal-800 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-teal-500 animate-pulse" />
                  <span>Detection Overlay</span>
                </span>
                <button
                  type="button"
                  onClick={() => setModalImage({ url: images.annotated!, title: `Detection Overlay · Observation ${observationId}` })}
                  className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200/50 transition-colors"
                  title="Enlarge detection overlay"
                  aria-label="Enlarge detection overlay"
                >
                  <Maximize2 size={13} />
                </button>
              </div>
              <button type="button" aria-label="Preview detection overlay" onClick={() => setModalImage({ url: images.annotated!, title: `Detection Overlay · Observation ${observationId}` })} className="bg-slate-950 p-1 flex items-center justify-center min-h-[180px] max-h-[280px]">
                <img
                  src={images.annotated}
                  alt={`Detection overlay for observation ${observationId}`}
                  className="max-h-[260px] w-auto max-w-full object-contain cursor-zoom-in"
                  onClick={() => setModalImage({ url: images.annotated!, title: `Detection Overlay · Observation ${observationId}` })}
                  loading="lazy"
                />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Full-view Modal */}
      {modalImage && createPortal(
        <div
          ref={modalRef}
          tabIndex={-1}
          role="dialog"
          aria-modal="true"
          aria-label={modalImage.title}
          className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-xs flex items-center justify-center p-4"
          onClick={() => setModalImage(null)}
        >
          <div
            className="relative bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden max-w-5xl max-h-[90vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-4 py-3 bg-slate-800/90 border-b border-slate-700/80 flex items-center justify-between text-white">
              <span className="text-xs font-semibold">{modalImage.title}</span>
              <button
                type="button"
                onClick={() => setModalImage(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                aria-label="Close modal"
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-2 flex items-center justify-center overflow-auto max-h-[calc(90vh-60px)]">
              <img
                src={modalImage.url}
                alt={modalImage.title}
                className="max-h-[80vh] max-w-full object-contain"
              />
            </div>
          </div>
        </div>, document.body
      )}
    </div>
  );
}
