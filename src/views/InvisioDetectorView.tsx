import React, { useEffect, useRef, useState } from 'react';
import {
    AlertTriangle,
    CheckCircle2,
    Fingerprint,
    Image as ImageIcon,
    Loader2,
    Shield,
    Upload,
    X,
} from 'lucide-react';
import {
    APIError,
    detectInvisioImage,
    type DetectSignatureData,
} from '../services/api';

export const InvisioDetectorView: React.FC = () => {
    const [selectedImage, setSelectedImage] = useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [result, setResult] = useState<DetectSignatureData | null>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        return () => {
            if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
            }
        };
    }, [previewUrl]);

    const applySelectedFile = (file: File | null) => {
        if (!file) return;
        if (!file.type.startsWith('image/')) {
            setError('Please upload a valid image file.');
            return;
        }

        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
        }

        setSelectedImage(file);
        setPreviewUrl(URL.createObjectURL(file));
        setResult(null);
        setError(null);
    };

    const handleReset = () => {
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
        }
        setSelectedImage(null);
        setPreviewUrl(null);
        setResult(null);
        setError(null);
        if (inputRef.current) {
            inputRef.current.value = '';
        }
    };

    const handleAnalyze = async () => {
        if (!selectedImage) {
            setError('Select an image to analyze first.');
            return;
        }

        setIsAnalyzing(true);
        setError(null);

        try {
            const response = await detectInvisioImage(selectedImage);
            if (response.status === 'success' && response.data) {
                setResult(response.data);
            }
        } catch (err: unknown) {
            if (err instanceof APIError) {
                setError(err.message);
            } else {
                setError('Detection failed. Please try again.');
            }
            setResult(null);
        } finally {
            setIsAnalyzing(false);
        }
    };

    const statusTone = result?.has_signature
        ? {
            badge: 'bg-emerald-50 text-emerald-700 border-emerald-200',
            icon: <CheckCircle2 className="w-5 h-5 text-emerald-600" />,
            title: 'Invisio signature detected',
            description: 'This image likely came from our protected export pipeline.',
        }
        : {
            badge: 'bg-amber-50 text-amber-700 border-amber-200',
            icon: <AlertTriangle className="w-5 h-5 text-amber-600" />,
            title: 'No Invisio signature found',
            description: 'We could not verify this file as an Invisio-protected export.',
        };

    return (
        <div className="absolute inset-0 w-full h-full flex flex-col items-center justify-start py-8 px-4 md:px-8 overflow-y-auto custom-scrollbar">
            <div className="w-full max-w-5xl bg-white rounded-3xl shadow-lg border border-slate-200 flex flex-col my-auto shrink-0">
                <div className="px-8 py-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <div>
                        <h2 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
                            <Shield className="w-6 h-6 text-[#00a6ed]" /> Detect Invisio Image
                        </h2>
                        <p className="text-sm text-slate-500 mt-1">
                            Upload any image and verify whether it contains our export watermark signature.
                        </p>
                    </div>
                    <button
                        onClick={handleReset}
                        className="px-4 py-2 bg-slate-100 text-slate-600 font-bold rounded-xl hover:bg-slate-200 transition-colors flex items-center gap-2"
                    >
                        <X className="w-4 h-4" /> Clear
                    </button>
                </div>

                <div className="p-8">
                    {error && (
                        <div className="mb-6 p-4 bg-red-50 border border-red-100 text-red-600 rounded-xl font-medium">
                            {error}
                        </div>
                    )}

                    <div className="grid grid-cols-1 xl:grid-cols-[1.05fr_0.95fr] gap-8">
                        <div className="space-y-6">
                            <div
                                className={`relative w-full aspect-[4/3] rounded-3xl overflow-hidden border-2 flex flex-col items-center justify-center transition-colors cursor-pointer ${
                                    isDragging
                                        ? 'border-solid border-[#00a6ed] bg-blue-50/60'
                                        : 'border-dashed ' + (previewUrl ? 'border-transparent bg-slate-950' : 'border-slate-300 hover:border-[#00a6ed] bg-slate-50 hover:bg-blue-50/30')
                                }`}
                                onClick={() => !previewUrl && inputRef.current?.click()}
                                onDragOver={(e) => {
                                    e.preventDefault();
                                    setIsDragging(true);
                                }}
                                onDragLeave={(e) => {
                                    e.preventDefault();
                                    setIsDragging(false);
                                }}
                                onDrop={(e) => {
                                    e.preventDefault();
                                    setIsDragging(false);
                                    applySelectedFile(e.dataTransfer.files?.[0] || null);
                                }}
                            >
                                {previewUrl ? (
                                    <>
                                        <img src={previewUrl} alt="Candidate image" className="w-full h-full object-contain bg-slate-950" />
                                        <div className="absolute top-4 left-4 flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/90 text-slate-700 text-xs font-bold shadow-sm">
                                            <ImageIcon className="w-4 h-4 text-[#00a6ed]" />
                                            {selectedImage?.name || 'Selected image'}
                                        </div>
                                        <div className="absolute inset-0 bg-black/30 opacity-0 hover:opacity-100 transition-opacity flex items-center justify-center">
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    inputRef.current?.click();
                                                }}
                                                className="px-4 py-2 bg-white text-slate-800 font-bold rounded-lg shadow-lg flex items-center gap-2"
                                            >
                                                <Upload className="w-4 h-4" /> Change Image
                                            </button>
                                        </div>
                                    </>
                                ) : (
                                    <>
                                        <div className="w-16 h-16 bg-white rounded-full shadow-sm border border-slate-100 flex items-center justify-center text-[#00a6ed] mb-4">
                                            <Upload className="w-8 h-8" />
                                        </div>
                                        <span className="font-bold text-slate-700">Upload or drop an image</span>
                                        <span className="text-sm text-slate-400 mt-1 text-center px-6">
                                            We will check the final pixels for Invisio&apos;s hidden export signature.
                                        </span>
                                    </>
                                )}
                            </div>

                            <input
                                ref={inputRef}
                                type="file"
                                accept="image/*"
                                className="hidden"
                                onChange={(e) => applySelectedFile(e.target.files?.[0] || null)}
                            />

                            <div className="bg-slate-50 rounded-2xl p-6 border border-slate-200 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                                <div>
                                    <p className="text-sm font-bold text-slate-700">Signature Scan</p>
                                    <p className="text-sm text-slate-500 mt-1">
                                        Works best on final exported PNG or high-quality JPG files.
                                    </p>
                                </div>

                                <button
                                    onClick={handleAnalyze}
                                    disabled={!selectedImage || isAnalyzing}
                                    className={`min-w-[220px] px-6 py-3 rounded-xl font-bold text-base flex items-center justify-center gap-2 transition-all ${
                                        !selectedImage || isAnalyzing
                                            ? 'bg-slate-200 text-slate-400 cursor-not-allowed shadow-none'
                                            : 'bg-gradient-to-r from-[#00a6ed] to-sky-600 text-white hover:shadow-lg hover:shadow-sky-500/20 active:scale-95'
                                    }`}
                                >
                                    {isAnalyzing ? (
                                        <>
                                            <Loader2 className="w-5 h-5 animate-spin" /> Scanning...
                                        </>
                                    ) : (
                                        <>
                                            <Fingerprint className="w-5 h-5" /> Analyze Image
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>

                        <div className="space-y-6">
                            <div className="rounded-3xl border border-slate-200 bg-white shadow-sm overflow-hidden">
                                <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
                                    <div>
                                        <h3 className="text-lg font-bold text-slate-800">Detection Result</h3>
                                        <p className="text-sm text-slate-500 mt-1">
                                            The scanner checks our hidden fingerprint tied to the export watermark.
                                        </p>
                                    </div>
                                    <div className="w-12 h-12 rounded-2xl bg-blue-50 text-[#00a6ed] flex items-center justify-center">
                                        <Shield className="w-6 h-6" />
                                    </div>
                                </div>

                                <div className="p-6">
                                    {result ? (
                                        <div className="space-y-5">
                                            <div className={`rounded-2xl border px-4 py-4 ${statusTone.badge}`}>
                                                <div className="flex items-start gap-3">
                                                    {statusTone.icon}
                                                    <div>
                                                        <p className="font-bold">{statusTone.title}</p>
                                                        <p className="text-sm mt-1 opacity-90">{statusTone.description}</p>
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                                <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
                                                    <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Confidence</p>
                                                    <p className="text-2xl font-bold text-slate-800 mt-1">
                                                        {Math.round(result.confidence * 100)}%
                                                    </p>
                                                </div>
                                                <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
                                                    <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Matched Bits</p>
                                                    <p className="text-2xl font-bold text-slate-800 mt-1">
                                                        {result.matched_bits}/{result.total_bits}
                                                    </p>
                                                </div>
                                            </div>

                                            <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
                                                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Analysis</p>
                                                <p className="text-sm text-slate-600 mt-2 leading-relaxed">{result.reason}</p>
                                                {typeof result.average_strength === 'number' && (
                                                    <p className="text-xs text-slate-400 mt-3">
                                                        Signal strength: {result.average_strength.toFixed(2)}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
                                            <div className="w-14 h-14 mx-auto rounded-2xl bg-white border border-slate-200 flex items-center justify-center text-slate-400">
                                                <Fingerprint className="w-7 h-7" />
                                            </div>
                                            <p className="text-base font-bold text-slate-700 mt-4">No scan yet</p>
                                            <p className="text-sm text-slate-500 mt-2 max-w-sm mx-auto">
                                                Pick an image, run the detector, and we will tell you whether the Invisio export signature is present.
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
