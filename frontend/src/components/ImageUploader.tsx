import React, { useState, useRef } from 'react';
import { UploadCloud, Image as ImageIcon, X, Sliders, AlertCircle, Loader2 } from 'lucide-react';
import type { ImageAssessmentParams } from '../types';

interface ImageUploaderProps {
  onAnalyze: (file: File, params: ImageAssessmentParams) => Promise<void>;
  isLoading: boolean;
  error: string | null;
}

const MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 10 MB limit matching backend MAX_IMAGE_SIZE

export const ImageUploader: React.FC<ImageUploaderProps> = ({
  onAnalyze,
  isLoading,
  error,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Optional inputs
  const [observationId, setObservationId] = useState('');
  const [workArea, setWorkArea] = useState('');
  const [peopleCount, setPeopleCount] = useState<string>('');
  const [durationMinutes, setDurationMinutes] = useState<string>('');
  const [repeatedCount, setRepeatedCount] = useState<string>('');

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = (file: File) => {
    setClientError(null);
    if (!['image/jpeg', 'image/png'].includes(file.type)) {
      setClientError('Invalid file type. Only JPEG and PNG image formats are supported.');
      return;
    }
    if (file.size > MAX_IMAGE_SIZE) {
      setClientError(
        `File size exceeds 10 MB limit (${(file.size / (1024 * 1024)).toFixed(2)} MB). Please select a smaller image.`
      );
      return;
    }

    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleClear = () => {
    setSelectedFile(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setClientError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    const params: ImageAssessmentParams = {
      observation_id: observationId.trim() || undefined,
      work_area: workArea.trim() || undefined,
      people_count: peopleCount.trim() ? parseInt(peopleCount.trim(), 10) : undefined,
      duration_minutes: durationMinutes.trim()
        ? parseInt(durationMinutes.trim(), 10)
        : undefined,
      repeated_count: repeatedCount.trim() ? parseInt(repeatedCount.trim(), 10) : undefined,
    };

    await onAnalyze(selectedFile, params);
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden mb-8">
      <div className="p-6 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Upload Site Image for Risk Assessment</h2>
          <p className="text-sm text-slate-500">
            Submit construction-site visual observations to detect PPE hazards and evaluate risk.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          aria-expanded={showAdvanced}
          aria-controls="scoring-inputs"
          className="flex items-center space-x-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 bg-slate-50 hover:bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200 transition-colors"
        >
          <Sliders className="w-3.5 h-3.5" />
          <span>{showAdvanced ? 'Hide Scoring Inputs' : 'Show Scoring Inputs'}</span>
        </button>
      </div>

      <form onSubmit={handleSubmit} className="p-6">
        {/* Error Banners */}
        {(clientError || error) && (
          <div className="mb-6 p-4 rounded-lg bg-red-50 border border-red-200 text-red-700 flex items-start space-x-3 text-sm">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-500 mt-0.5" />
            <div className="flex-1">
              <p className="font-medium">Assessment Request Error</p>
              <p className="text-red-600 mt-0.5">{clientError || error}</p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Dropzone & Preview (7 cols on lg) */}
          <div className="lg:col-span-7">
            {!previewUrl ? (
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-300 hover:border-amber-500 hover:bg-amber-50/20 rounded-xl p-8 text-center cursor-pointer transition-all flex flex-col items-center justify-center min-h-[220px]"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      handleFile(e.target.files[0]);
                    }
                  }}
                />
                <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 mb-3">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <p className="text-sm font-semibold text-slate-700 mb-1">
                  Click to browse or drag and drop image here
                </p>
                <p className="text-xs text-slate-400">
                  Supported formats: JPEG, PNG • Maximum size: 10 MB
                </p>
              </div>
            ) : (
              <div className="relative rounded-xl border border-slate-200 overflow-hidden bg-slate-900 group">
                <img
                  src={previewUrl}
                  alt="Site inspection preview"
                  className="w-full h-64 object-contain"
                />
                <div className="absolute top-3 right-3 flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={handleClear}
                    disabled={isLoading}
                    className="p-1.5 rounded-full bg-slate-900/80 hover:bg-slate-900 text-white backdrop-blur-xs transition-colors"
                    title="Remove image"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="p-3 bg-slate-900/90 text-white text-xs flex justify-between items-center border-t border-slate-800">
                  <div className="flex items-center space-x-2 truncate">
                    <ImageIcon className="w-3.5 h-3.5 text-slate-400" />
                    <span className="truncate">{selectedFile?.name}</span>
                  </div>
                  <span className="text-slate-400 shrink-0">
                    {((selectedFile?.size || 0) / (1024 * 1024)).toFixed(2)} MB
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Contextual & Operational Inputs (5 cols on lg) */}
          <div className="lg:col-span-5 flex flex-col justify-between">
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Work Area / Location
                  </label>
                  <input
                    type="text"
                    value={workArea}
                    onChange={(e) => setWorkArea(e.target.value)}
                    placeholder="e.g. Sector-3 Scaffolding"
                    disabled={isLoading}
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Observation ID
                  </label>
                  <input
                    type="text"
                    value={observationId}
                    onChange={(e) => setObservationId(e.target.value)}
                    placeholder="Auto UUID"
                    disabled={isLoading}
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                  />
                </div>
              </div>

              {/* Collapsible advanced scoring inputs */}
              <div
                id="scoring-inputs"
                className={`space-y-4 ${showAdvanced ? 'block' : 'hidden'}`}
              >
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                      Duration (min)
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={durationMinutes}
                      onChange={(e) => setDurationMinutes(e.target.value)}
                      placeholder="e.g. 45"
                      disabled={isLoading}
                      className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                      Repetitions
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={repeatedCount}
                      onChange={(e) => setRepeatedCount(e.target.value)}
                      placeholder="e.g. 2"
                      disabled={isLoading}
                      className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    People Count
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={peopleCount}
                    onChange={(e) => setPeopleCount(e.target.value)}
                    placeholder="Auto from image"
                    disabled={isLoading}
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                  />
                </div>

                <div className="p-3 bg-amber-50/70 rounded-lg border border-amber-200/60 text-xs text-amber-800">
                  <span className="font-semibold">Note on Risk Scoring:</span> Duration and repetitions
                  are required to calculate risk scores (S × L × E). If omitted, hazards will be
                  detected but kept in <span className="font-semibold">pending status</span>.
                </div>
              </div>
            </div>

            {/* Submit Button */}
            <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-end space-x-3">
              {selectedFile && (
                <button
                  type="button"
                  onClick={handleClear}
                  disabled={isLoading}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors"
                >
                  Clear
                </button>
              )}
              <button
                type="submit"
                disabled={!selectedFile || isLoading}
                className="flex items-center space-x-2 px-5 py-2.5 rounded-lg text-sm font-semibold text-white bg-amber-600 hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-xs transition-colors"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Analyzing Image...</span>
                  </>
                ) : (
                  <>
                    <UploadCloud className="w-4 h-4" />
                    <span>Run Visual Assessment</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
};
