import React, { useState, useRef, useId } from 'react';
import {
  UploadCloud,
  X,
  AlertCircle,
  Loader2,
  ShieldAlert,
  Eye,
  FlaskConical,
  Info,
  SlidersHorizontal,
  RefreshCw,
} from 'lucide-react';
import { submitExperimentalSafetyDetect } from '../api/client';
import { SafetyDecisionPanel } from './SafetyDecisionPanel';
import type {
  ExperimentalSafetyDetectResponse,
  ImageAssessmentParams,
} from '../types';
import { formatHazardType, formatConfidence } from '../utils/formatters';

const MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 10 MB limit matching backend

export const ExperimentalSafetyViewer: React.FC = () => {
  const fileInputId = useId();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [result, setResult] = useState<ExperimentalSafetyDetectResponse | null>(null);

  // Overlay settings
  const [showBoxes, setShowBoxes] = useState<boolean>(true);
  const [showNonHazards, setShowNonHazards] = useState<boolean>(true);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // Optional operational risk scoring toggle
  const [showExposureInputs, setShowExposureInputs] = useState<boolean>(false);
  const [workArea, setWorkArea] = useState<string>('');
  const [peopleCount, setPeopleCount] = useState<string>('');
  const [durationMinutes, setDurationMinutes] = useState<string>('');
  const [repeatedCount, setRepeatedCount] = useState<string>('');

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = (file: File) => {
    setClientError(null);
    setResult(null);

    const validTypes = ['image/jpeg', 'image/png', 'image/jpg'];
    if (!validTypes.includes(file.type.toLowerCase()) && !/\.(jpe?g|png)$/i.test(file.name)) {
      setClientError('Invalid file type. Please upload a PNG, JPG, or JPEG construction image.');
      return;
    }

    if (file.size > MAX_IMAGE_SIZE) {
      setClientError(
        `File size exceeds 10 MB limit (${(file.size / (1024 * 1024)).toFixed(2)} MB). Please choose a smaller image.`
      );
      return;
    }

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
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
    setResult(null);
    setClientError(null);
    setHoveredIndex(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleRunDetection = async () => {
    if (!selectedFile) return;

    setIsLoading(true);
    setClientError(null);

    let params: ImageAssessmentParams | undefined = undefined;
    if (showExposureInputs) {
      params = {
        work_area: workArea.trim() || undefined,
        people_count: peopleCount.trim() ? parseInt(peopleCount.trim(), 10) : undefined,
        duration_minutes: durationMinutes.trim()
          ? parseInt(durationMinutes.trim(), 10)
          : undefined,
        repeated_count: repeatedCount.trim() ? parseInt(repeatedCount.trim(), 10) : undefined,
      };
    }

    try {
      const data = await submitExperimentalSafetyDetect(selectedFile, params);
      setResult(data);
    } catch (err) {
      setClientError(
        err instanceof Error
          ? err.message
          : 'Safety detection failed. Please ensure the backend is running with YOLO weights.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  // Filter detections based on user toggle
  const visibleDetections = result
    ? result.detections.map((det, index) => ({ det, index })).filter(({ det }) => {
        if (!showNonHazards && !det.is_hazard) return false;
        return true;
      })
    : [];

  return (
    <div className="space-y-8">
      {/* Banner / Header */}
      <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 sm:p-8 text-white shadow-lg">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <FlaskConical className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                  Experimental Safety Visualizer
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 font-medium">
                    Testing Bench
                  </span>
                </h1>
                <p className="text-xs sm:text-sm text-slate-400">
                  Direct inspection test bench for YOLOv8 checkpoint (<code>weights/best.pt</code>) and Safety Agent heuristics
                </p>
              </div>
            </div>
          </div>

          {/* Mode Pill Badges */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="px-3 py-1 rounded-md bg-slate-800 border border-slate-700 text-slate-300">
              Model: <strong className="text-white">weights/best.pt</strong>
            </span>
            <span className="px-3 py-1 rounded-md bg-emerald-950/60 border border-emerald-700/50 text-emerald-300">
              Backend: <strong className="text-white">POST /experimental/safety/detect</strong>
            </span>
            <span className="px-3 py-1 rounded-md bg-blue-950/60 border border-blue-700/50 text-blue-300">
              Persistence: <strong className="text-white">Stateless (No DB Writes)</strong>
            </span>
          </div>
        </div>

        {/* Informational Callout */}
        <div className="mt-5 p-3.5 bg-slate-800/80 rounded-xl border border-slate-700/60 flex items-start gap-3 text-xs text-slate-300">
          <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            Upload any construction image (PNG, JPG, JPEG) to run real-time YOLO object detection and evaluate Safety Agent hazard logic.
            Detections are rendered with <strong>actual model coordinates</strong> returned by FastAPI.
            This experimental tool operates completely in-memory: <em>no observation database records are created and no notifications are dispatched</em>.
          </div>
        </div>
      </div>

      {/* Upload & Controls Section */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-6 border-b border-slate-100 flex items-center justify-between flex-wrap gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Upload Construction Image</h2>
            <p className="text-sm text-slate-500">
              Select an image from your computer to visualize safety PPE hazards.
            </p>
          </div>

          {selectedFile && (
            <button
              onClick={handleClear}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-rose-600 bg-slate-100 hover:bg-rose-50 rounded-lg transition-colors border border-slate-200"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Clear & Try Another Image</span>
            </button>
          )}
        </div>

        <div className="p-6 space-y-6">
          {/* Client or API Error Banner */}
          {clientError && (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 flex items-start justify-between gap-3 text-sm">
              <div className="flex items-start gap-2.5">
                <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Inspection Error</p>
                  <p className="text-xs text-rose-700 mt-0.5">{clientError}</p>
                </div>
              </div>
              <button
                onClick={() => setClientError(null)}
                className="text-rose-400 hover:text-rose-600"
                aria-label="Dismiss error"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Upload Dropzone (When no file selected) */}
          {!selectedFile && (
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              className="border-2 border-dashed border-slate-300 hover:border-amber-500 hover:bg-amber-500/5 transition-colors rounded-xl p-8 sm:p-12 text-center cursor-pointer group"
            >
              <input
                id={fileInputId}
                ref={fileInputRef}
                type="file"
                accept="image/png, image/jpeg, image/jpg"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    handleFile(e.target.files[0]);
                  }
                }}
              />
              <label htmlFor={fileInputId} className="cursor-pointer flex flex-col items-center">
                <div className="w-14 h-14 rounded-full bg-slate-100 group-hover:bg-amber-100 text-slate-500 group-hover:text-amber-600 flex items-center justify-center transition-colors mb-4">
                  <UploadCloud className="w-7 h-7" />
                </div>
                <p className="text-sm font-semibold text-slate-800 mb-1">
                  Click to select or drag and drop a construction-site image
                </p>
                <p className="text-xs text-slate-500">
                  Supported formats: <strong>PNG, JPG, JPEG</strong> (Max size: 10 MB)
                </p>
              </label>
            </div>
          )}

          {/* Image Selected Preview & Action Bar */}
          {selectedFile && previewUrl && (
            <div className="space-y-6">
              {/* File Info & Action Button */}
              <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-50 rounded-xl border border-slate-200">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-600 flex items-center justify-center">
                    <FlaskConical className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-900 truncate max-w-xs sm:max-w-md">
                      {selectedFile.name}
                    </p>
                    <p className="text-xs text-slate-500">
                      {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • {selectedFile.type || 'image'}
                      {result ? ` • Native Dimensions: ${result.image_width} × ${result.image_height} px` : ''}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setShowExposureInputs(!showExposureInputs)}
                    className="inline-flex items-center space-x-1.5 px-3 py-2 text-xs font-medium text-slate-600 bg-white hover:bg-slate-100 rounded-lg transition-colors border border-slate-200"
                    title="Toggle optional site exposure inputs"
                  >
                    <SlidersHorizontal className="w-3.5 h-3.5" />
                    <span>{showExposureInputs ? 'Hide Exposure Inputs' : 'Optional Risk Scoring Inputs'}</span>
                  </button>

                  <button
                    onClick={handleRunDetection}
                    disabled={isLoading}
                    className="inline-flex items-center space-x-2 px-5 py-2.5 bg-amber-600 hover:bg-amber-700 disabled:bg-amber-400 text-white font-medium text-sm rounded-lg transition-colors shadow-sm disabled:cursor-not-allowed"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Running YOLO Model...</span>
                      </>
                    ) : (
                      <>
                        <Eye className="w-4 h-4" />
                        <span>Run YOLO Safety Detection</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Optional Site Exposure Parameters (to demonstrate scored risk assessment vs un-scored detection) */}
              {showExposureInputs && (
                <div className="p-4 bg-amber-50/60 rounded-xl border border-amber-200/80 text-xs space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-amber-900 flex items-center gap-1.5">
                      <SlidersHorizontal className="w-3.5 h-3.5" />
                      Optional Operational Site Exposure Inputs (for SiteRiskAgent scoring)
                    </p>
                    <span className="text-[10px] text-amber-700 bg-amber-100 px-2 py-0.5 rounded">
                      When omitted, visual detections remain cleanly un-scored (pending)
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                    <div>
                      <label className="block font-medium text-slate-700 mb-1">Work Area</label>
                      <input
                        type="text"
                        placeholder="e.g. Roof Section A"
                        value={workArea}
                        onChange={(e) => setWorkArea(e.target.value)}
                        className="w-full px-2.5 py-1.5 bg-white border border-slate-300 rounded-md text-xs focus:ring-1 focus:ring-amber-500"
                      />
                    </div>
                    <div>
                      <label className="block font-medium text-slate-700 mb-1">People Count</label>
                      <input
                        type="number"
                        min="1"
                        placeholder="e.g. 2"
                        value={peopleCount}
                        onChange={(e) => setPeopleCount(e.target.value)}
                        className="w-full px-2.5 py-1.5 bg-white border border-slate-300 rounded-md text-xs focus:ring-1 focus:ring-amber-500"
                      />
                    </div>
                    <div>
                      <label className="block font-medium text-slate-700 mb-1">Duration (minutes)</label>
                      <input
                        type="number"
                        min="1"
                        placeholder="e.g. 45"
                        value={durationMinutes}
                        onChange={(e) => setDurationMinutes(e.target.value)}
                        className="w-full px-2.5 py-1.5 bg-white border border-slate-300 rounded-md text-xs focus:ring-1 focus:ring-amber-500"
                      />
                    </div>
                    <div>
                      <label className="block font-medium text-slate-700 mb-1">Repeated Count</label>
                      <input
                        type="number"
                        min="0"
                        placeholder="e.g. 2"
                        value={repeatedCount}
                        onChange={(e) => setRepeatedCount(e.target.value)}
                        className="w-full px-2.5 py-1.5 bg-white border border-slate-300 rounded-md text-xs focus:ring-1 focus:ring-amber-500"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Viewer Display Box with Real SVG Bounding Box Overlays */}
              <div className="rounded-xl border border-slate-200 overflow-hidden bg-slate-950 shadow-inner">
                {/* Overlay Controls Bar */}
                {result && (
                  <div className="p-3 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-300">
                    <div className="flex items-center space-x-4">
                      <label className="flex items-center space-x-2 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={showBoxes}
                          onChange={(e) => setShowBoxes(e.target.checked)}
                          className="rounded text-amber-500 focus:ring-amber-400"
                        />
                        <span>Show Bounding Boxes</span>
                      </label>

                      <label className="flex items-center space-x-2 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={showNonHazards}
                          onChange={(e) => setShowNonHazards(e.target.checked)}
                          className="rounded text-blue-500 focus:ring-blue-400"
                        />
                        <span>Show Context Detections (Person, Gear)</span>
                      </label>
                    </div>

                    <div className="flex items-center space-x-2 text-[11px]">
                      <span className="flex items-center gap-1 text-rose-400">
                        <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block"></span>
                        Hazard Violations ({result.detected_hazards.length})
                      </span>
                      <span className="text-slate-600">•</span>
                      <span className="flex items-center gap-1 text-blue-400">
                        <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block"></span>
                        Total Detections ({result.detections.length})
                      </span>
                    </div>
                  </div>
                )}

                {/* Visual Viewport */}
                <div className="relative w-full flex items-center justify-center p-2 sm:p-4 bg-slate-950 select-none overflow-hidden">
                  <div className="relative inline-block max-w-full">
                    {/* The Actual Uploaded Image */}
                    <img
                      src={previewUrl}
                      alt="Construction site visual preview"
                      className="max-h-[600px] w-auto max-w-full rounded-md object-contain block"
                    />

                    {/* SVG Bounding Boxes Overlay matching exact backend coordinates & image dimensions */}
                    {result && showBoxes && result.image_width > 0 && result.image_height > 0 && (
                      <svg
                        viewBox={`0 0 ${result.image_width} ${result.image_height}`}
                        className="absolute inset-0 w-full h-full pointer-events-none"
                        preserveAspectRatio="none"
                      >
                        {visibleDetections.map(({ det, index }) => {
                          const [xMin, yMin, xMax, yMax] = det.box;
                          const width = Math.max(0, xMax - xMin);
                          const height = Math.max(0, yMax - yMin);
                          const isHovered = hoveredIndex === index;
                          const isHazard = det.is_hazard;

                          const strokeColor = isHazard ? '#ef4444' : '#3b82f6';
                          const fillColor = isHazard
                            ? isHovered
                              ? 'rgba(239, 68, 68, 0.35)'
                              : 'rgba(239, 68, 68, 0.15)'
                            : isHovered
                              ? 'rgba(59, 130, 246, 0.3)'
                              : 'rgba(59, 130, 246, 0.08)';

                          // Font and badge scaling
                          const fontSize = Math.max(12, Math.round(result.image_width * 0.016));
                          const badgeHeight = fontSize + 8;
                          const labelText = `${det.class_name} ${(det.confidence * 100).toFixed(1)}%`;
                          const badgeWidth = labelText.length * (fontSize * 0.58) + 12;
                          const badgeY = yMin >= badgeHeight ? yMin - badgeHeight : yMin;

                          return (
                            <g key={index} className="transition-all duration-150">
                              {/* Detection Bounding Box */}
                              <rect
                                x={xMin}
                                y={yMin}
                                width={width}
                                height={height}
                                fill={fillColor}
                                stroke={strokeColor}
                                strokeWidth={isHovered ? 4 : isHazard ? 3 : 2}
                                strokeDasharray={isHazard ? undefined : '4 2'}
                              />

                              {/* Label Pill Background */}
                              <rect
                                x={xMin}
                                y={badgeY}
                                width={badgeWidth}
                                height={badgeHeight}
                                fill={strokeColor}
                                rx={4}
                              />

                              {/* Label Text */}
                              <text
                                x={xMin + 6}
                                y={badgeY + fontSize}
                                fill="#ffffff"
                                fontSize={fontSize}
                                fontWeight="bold"
                                fontFamily="sans-serif"
                              >
                                {labelText}
                              </text>
                            </g>
                          );
                        })}
                      </svg>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Detection Results & Safety Agent Analysis */}
      {result && (
        <div className="space-y-6">
          {/* Section 1: Shared safety decision from the backend */}
          <SafetyDecisionPanel decision={result.safety_decision} />

          <div
            className={`rounded-xl border p-5 shadow-xs ${
              result.routing_status === 'review_required'
                ? 'bg-rose-50 border-rose-200 text-rose-950'
                : result.routing_status === 'no_findings'
                  ? 'bg-slate-50 border-slate-200 text-slate-800'
                  : 'bg-amber-50 border-amber-200 text-amber-950'
            }`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide opacity-70">
                  LangGraph Conditional Routing
                </p>
                <h3 className="mt-1 text-base font-bold">
                  {result.routing_status === 'review_required'
                    ? 'Safety review required'
                    : result.routing_status === 'no_findings'
                      ? 'No supported PPE violations detected'
                      : 'Safety assessment pending or incomplete'}
                </h3>
                <p className="mt-1 text-sm opacity-80">{result.routing_reason}</p>
              </div>
              <span className="rounded-full border border-current/20 px-3 py-1 text-xs font-semibold">
                {result.routing_decision}
              </span>
            </div>
          </div>

          {/* Section 2: Model Detection vs Risk Assessment Distinction (Requirement 7) */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-blue-500/10 text-blue-600 border border-blue-500/20 flex items-center justify-center shrink-0">
                <Info className="w-5 h-5" />
              </div>
              <div className="space-y-2 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-base font-bold text-slate-900">
                    Understanding Visual Detections vs. Risk Assessment Scoring
                  </h3>
                  <span
                    className={`text-xs font-semibold px-2.5 py-1 rounded-md ${
                      result.is_risk_assessed
                        ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                        : 'bg-amber-100 text-amber-800 border border-amber-200'
                    }`}
                  >
                    Scoring Status: {result.is_risk_assessed ? 'Fully Scored' : 'Pending / Visual Only'}
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                  {result.status_note}
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 text-xs">
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <p className="font-semibold text-slate-800 mb-1">
                      📸 YOLO Model Detections (Computer Vision)
                    </p>
                    <p className="text-slate-600">
                      Evaluates image pixels using the trained weights at <code>weights/best.pt</code> to locate PPE violations (e.g., <code>NO-Hardhat</code>) and context classes (<code>Person</code>).
                    </p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <p className="font-semibold text-slate-800 mb-1">
                      ⚖️ Risk Agent Assessment (Operational Scoring)
                    </p>
                    <p className="text-slate-600">
                      Calculates numerical risk (Severity × Likelihood × Exposure) only when operational factors (task duration, crew count, recurrence) are known.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Section 3: Completed Scored Risk Assessments (If operational inputs were provided) */}
          {result.is_risk_assessed && result.assessments.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
              <div className="p-5 border-b border-slate-100 bg-slate-50">
                <h3 className="text-base font-bold text-slate-900">
                  Fully Scored Risk Assessments ({result.assessments.length})
                </h3>
                <p className="text-xs text-slate-500">
                  Calculated by SiteRiskAgent using Severity × Likelihood × Exposure rule-based scoring
                </p>
              </div>
              <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                {result.assessments.map((assessment, i) => (
                  <div
                    key={i}
                    className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900 text-sm">
                        {formatHazardType(assessment.hazard_type)}
                      </span>
                      <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-200">
                        {assessment.risk_band} • Score {assessment.risk_score}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                      <div className="p-2 bg-white rounded border border-slate-200">
                        <span className="text-slate-400 block text-[10px]">Severity</span>
                        <strong className="text-slate-800">{assessment.severity} / 5</strong>
                      </div>
                      <div className="p-2 bg-white rounded border border-slate-200">
                        <span className="text-slate-400 block text-[10px]">Likelihood</span>
                        <strong className="text-slate-800">{assessment.likelihood} / 5</strong>
                      </div>
                      <div className="p-2 bg-white rounded border border-slate-200">
                        <span className="text-slate-400 block text-[10px]">Exposure</span>
                        <strong className="text-slate-800">{assessment.exposure} / 5</strong>
                      </div>
                    </div>
                    <p className="text-xs text-slate-600 bg-white p-2.5 rounded border border-slate-200">
                      {assessment.explanation}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section 4: Safety Findings & Recommendations */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Safety Findings (Detected Hazards) */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
              <div className="p-5 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-slate-900">Safety Findings</h3>
                  <p className="text-xs text-slate-500">
                    Supported PPE hazard violations identified by Safety Agent
                  </p>
                </div>
                <span className="text-xs font-semibold px-2.5 py-1 rounded bg-slate-200 text-slate-700">
                  {result.detected_hazards.length} Hazards
                </span>
              </div>

              <div className="p-6 space-y-3">
                {result.detected_hazards.length === 0 ? (
                  <div className="text-center py-6 text-slate-500 text-sm flex flex-col items-center">
                    <Info className="w-8 h-8 text-slate-400 mb-2" />
                    <p className="font-medium text-slate-800">No supported explicit PPE violation detected</p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      This does not confirm complete PPE compliance. Only supported explicit violation classes are reported.
                    </p>
                  </div>
                ) : (
                  result.detected_hazards.map((hazard, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-lg border border-rose-200 bg-rose-50/50 flex items-center justify-between"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center space-x-2">
                          <span className="text-sm font-bold text-rose-900">
                            {formatHazardType(hazard.hazard_type)}
                          </span>
                          <span className="text-[11px] px-2 py-0.5 rounded bg-rose-200/80 text-rose-800 font-mono">
                            {hazard.source_label}
                          </span>
                        </div>
                        <p className="text-xs text-rose-700">
                          Classification Confidence:{' '}
                          <strong>{formatConfidence(hazard.confidence ?? null)}</strong>
                        </p>
                      </div>
                      <ShieldAlert className="w-5 h-5 text-rose-500 shrink-0" />
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Proposed Safety Recommendations */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
              <div className="p-5 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Safety Agent Recommendations
                  </h3>
                  <p className="text-xs text-slate-500">
                    Prescribed corrective mitigations for identified hazards
                  </p>
                </div>
                <span className="text-xs font-semibold px-2.5 py-1 rounded bg-slate-200 text-slate-700">
                  {result.recommendations.length} Proposed
                </span>
              </div>

              <div className="p-6 space-y-3">
                {result.recommendations.length === 0 ? (
                  <div className="text-center py-6 text-slate-500 text-sm flex flex-col items-center">
                    <Info className="w-8 h-8 text-slate-400 mb-2" />
                    <p className="font-medium text-slate-800">No recommendations generated</p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      This does not confirm that no safety action is needed.
                    </p>
                  </div>
                ) : (
                  result.recommendations.map((rec, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-lg border border-slate-200 bg-slate-50 space-y-1.5"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-900">
                          {formatHazardType(rec.hazard_type)}
                        </span>
                        <div className="flex items-center space-x-1.5">
                          <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-medium capitalize">
                            {rec.priority}
                          </span>
                          <span className="px-2 py-0.5 rounded bg-slate-200 text-slate-700 font-medium">
                            {rec.status}
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-slate-700">{rec.recommendation_text}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Section 5: Raw Model Detections Coordinate Table */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
            <div className="p-5 border-b border-slate-100 bg-slate-50 flex items-center justify-between flex-wrap gap-2">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Model Detections & Bounding Box Coordinates ({result.detections.length})
                </h3>
                <p className="text-xs text-slate-500">
                  Actual pixel coordinates <code>[x_min, y_min, x_max, y_max]</code> returned by the YOLO model
                </p>
              </div>
              <span className="text-xs text-slate-400">
                Hover over a row to highlight its bounding box on the image above
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-600">
                <thead className="bg-slate-100/75 text-slate-700 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 px-4">#</th>
                    <th className="py-2.5 px-4">Class Name</th>
                    <th className="py-2.5 px-4">Type</th>
                    <th className="py-2.5 px-4">Confidence</th>
                    <th className="py-2.5 px-4">x_min</th>
                    <th className="py-2.5 px-4">y_min</th>
                    <th className="py-2.5 px-4">x_max</th>
                    <th className="py-2.5 px-4">y_max</th>
                    <th className="py-2.5 px-4">Box Size</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {result.detections.map((det, idx) => {
                    const [x1, y1, x2, y2] = det.box;
                    const width = Math.round(x2 - x1);
                    const height = Math.round(y2 - y1);
                    const isHovered = hoveredIndex === idx;

                    return (
                      <tr
                        key={idx}
                        onMouseEnter={() => setHoveredIndex(idx)}
                        onMouseLeave={() => setHoveredIndex(null)}
                        className={`transition-colors cursor-pointer ${
                          isHovered
                            ? 'bg-amber-50 font-medium'
                            : det.is_hazard
                              ? 'bg-rose-50/30 hover:bg-rose-50/60'
                              : 'hover:bg-slate-50'
                        }`}
                      >
                        <td className="py-2.5 px-4 font-mono text-slate-400">{idx + 1}</td>
                        <td className="py-2.5 px-4">
                          <span
                            className={`font-semibold ${
                              det.is_hazard ? 'text-rose-700' : 'text-slate-800'
                            }`}
                          >
                            {det.class_name}
                          </span>
                        </td>
                        <td className="py-2.5 px-4">
                          {det.is_hazard ? (
                            <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 text-[10px] font-bold">
                              Hazard Violation
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-[10px] font-medium">
                              Non-violation detection
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-4 font-mono">
                          {(det.confidence * 100).toFixed(1)}% ({det.confidence.toFixed(4)})
                        </td>
                        <td className="py-2.5 px-4 font-mono">{x1}</td>
                        <td className="py-2.5 px-4 font-mono">{y1}</td>
                        <td className="py-2.5 px-4 font-mono">{x2}</td>
                        <td className="py-2.5 px-4 font-mono">{y2}</td>
                        <td className="py-2.5 px-4 font-mono text-slate-400">
                          {width} × {height} px
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
