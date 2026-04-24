import React, { useState, useRef } from 'react';
import { Upload, Image as ImageIcon, Download, Loader2, Sparkles, X, Wand2, Share2 } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { API_BASE_URL } from '../services/api';
import { DirectShareModal } from '../components/community/DirectShareModal';

export const StyleTransferView: React.FC = () => {
    const { accessToken } = useAuthStore();
    
    // UI State
    const [contentImage, setContentImage] = useState<File | null>(null);
    const [contentPreview, setContentPreview] = useState<string | null>(null);
    
    const [styleImage, setStyleImage] = useState<File | null>(null);
    const [stylePreview, setStylePreview] = useState<string | null>(null);
    
    const [resultImage, setResultImage] = useState<string | null>(null);
    const [isShareModalOpen, setIsShareModalOpen] = useState<boolean>(false);
    
    const [alpha, setAlpha] = useState<number>(1.0);
    const [isProcessing, setIsProcessing] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const [isDraggingContent, setIsDraggingContent] = useState<boolean>(false);
    const [isDraggingStyle, setIsDraggingStyle] = useState<boolean>(false);

    // Refs for hidden inputs
    const contentInputRef = useRef<HTMLInputElement>(null);
    const styleInputRef = useRef<HTMLInputElement>(null);

    // Handlers for File Selection
    const handleContentSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setContentImage(file);
            setContentPreview(URL.createObjectURL(file));
            setResultImage(null);
            setError(null);
        }
    };

    const handleStyleSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setStyleImage(file);
            setStylePreview(URL.createObjectURL(file));
            setResultImage(null);
            setError(null);
        }
    };

    const handleContentDragOver = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDraggingContent(true);
    };

    const handleContentDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDraggingContent(false);
    };

    const handleContentDrop = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDraggingContent(false);
        const file = e.dataTransfer.files?.[0];
        if (file && file.type.startsWith('image/')) {
            setContentImage(file);
            setContentPreview(URL.createObjectURL(file));
            setResultImage(null);
            setError(null);
        }
    };

    const handleStyleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDraggingStyle(true);
    };

    const handleStyleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDraggingStyle(false);
    };

    const handleStyleDrop = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDraggingStyle(false);
        const file = e.dataTransfer.files?.[0];
        if (file && file.type.startsWith('image/')) {
            setStyleImage(file);
            setStylePreview(URL.createObjectURL(file));
            setResultImage(null);
            setError(null);
        }
    };

    const handleReset = () => {
        setContentImage(null);
        setContentPreview(null);
        setStyleImage(null);
        setStylePreview(null);
        setResultImage(null);
        setAlpha(1.0);
        setError(null);
        if (contentInputRef.current) contentInputRef.current.value = '';
        if (styleInputRef.current) styleInputRef.current.value = '';
    };

    const handleGenerate = async () => {
        if (!contentImage || !styleImage) {
            setError("Please upload both a content image and a style image first.");
            return;
        }

        setIsProcessing(true);
        setError(null);

        try {
            const formData = new FormData();
            formData.append('content_image', contentImage);
            formData.append('style_image', styleImage);
            formData.append('alpha', alpha.toString());

            const headers: Record<string, string> = {};
            if (accessToken) {
                headers['Authorization'] = `Bearer ${accessToken}`;
            }

            const response = await fetch(`${API_BASE_URL}/style-transfer`, {
                method: 'POST',
                headers,
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                const backendMsg = errorData?.message || errorData?.detail;
                
                if (errorData?.error_code === 'NSFW_DETECTED') {
                    alert(backendMsg || "NSFW content detected. This image cannot be processed for safety reasons.");
                    throw new Error(backendMsg || "NSFW content detected.");
                }
                
                throw new Error(backendMsg || `Server error: ${response.status}`);
            }

            const blob = await response.blob();
            setResultImage(URL.createObjectURL(blob));
            
        } catch (err: any) {
            console.error('Style transfer error:', err);
            setError(err.message || 'Failed to process image. Please check your connection and the backend server.');
        } finally {
            setIsProcessing(false);
        }
    };

    return (
        <div className="absolute inset-0 w-full h-full flex flex-col items-center justify-start py-8 px-4 md:px-8 overflow-y-auto custom-scrollbar">
            <div className="w-full max-w-5xl bg-white rounded-3xl shadow-lg border border-slate-200 flex flex-col my-auto shrink-0">
                
                {/* Header Section */}
                <div className="px-8 py-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <div>
                        <h2 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
                            <Sparkles className="w-6 h-6 text-purple-600" /> Style Transfer
                        </h2>
                    </div>
                    <div className="flex gap-3">
                        <button 
                            onClick={handleReset}
                            className="px-4 py-2 bg-slate-100 text-slate-600 font-bold rounded-xl hover:bg-slate-200 transition-colors flex items-center gap-2"
                        >
                            <X className="w-4 h-4" /> Clear All
                        </button>
                    </div>
                </div>

                <div className="p-8">
                    {/* Error Banner */}
                    {error && (
                        <div className="mb-6 p-4 bg-red-50 border border-red-100 text-red-600 rounded-xl font-medium">
                            {error}
                        </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
                        {/* Content Image Box */}
                        <div className="flex flex-col gap-3">
                            <label className="font-bold text-slate-700 flex items-center gap-2">
                                <span className="w-6 h-6 rounded bg-blue-100 text-blue-600 flex items-center justify-center text-xs">1</span> 
                                Content Image
                            </label>
                            
                            <div 
                                className={`relative w-full aspect-[4/3] rounded-2xl overflow-hidden border-2 flex flex-col items-center justify-center transition-colors cursor-pointer ${
                                    isDraggingContent 
                                        ? 'border-solid border-blue-500 bg-blue-50/50' 
                                        : 'border-dashed ' + (contentPreview ? 'border-transparent' : 'border-slate-300 hover:border-blue-400 bg-slate-50 hover:bg-blue-50/30')
                                }`}
                                onClick={() => !contentPreview && contentInputRef.current?.click()}
                                onDragOver={handleContentDragOver}
                                onDragLeave={handleContentDragLeave}
                                onDrop={handleContentDrop}
                            >
                                {contentPreview ? (
                                    <>
                                        <img src={contentPreview} alt="Content" className="w-full h-full object-cover" />
                                        <div className="absolute inset-0 bg-black/40 opacity-0 hover:opacity-100 transition-opacity flex items-center justify-center">
                                            <button 
                                                onClick={(e) => { e.stopPropagation(); contentInputRef.current?.click() }}
                                                className="px-4 py-2 bg-white text-slate-800 font-bold rounded-lg shadow-lg flex items-center gap-2"
                                            >
                                                <Upload className="w-4 h-4" /> Change Content
                                            </button>
                                        </div>
                                    </>
                                ) : (
                                    <>
                                        <div className="w-16 h-16 bg-white rounded-full shadow-sm border border-slate-100 flex items-center justify-center text-blue-500 mb-4">
                                            <Upload className="w-8 h-8" />
                                        </div>
                                        <span className="font-bold text-slate-600">Upload or drop Content</span>
                                        <span className="text-sm text-slate-400 mt-1 text-center px-6">The main photo you want to alter.</span>
                                    </>
                                )}
                            </div>
                            <input type="file" accept="image/*" className="hidden" ref={contentInputRef} onChange={handleContentSelect} />
                        </div>

                        {/* Style Image Box */}
                        <div className="flex flex-col gap-3">
                            <label className="font-bold text-slate-700 flex items-center gap-2">
                                <span className="w-6 h-6 rounded bg-purple-100 text-purple-600 flex items-center justify-center text-xs">2</span> 
                                Style Image
                            </label>
                            
                            <div 
                                className={`relative w-full aspect-[4/3] rounded-2xl overflow-hidden border-2 flex flex-col items-center justify-center transition-colors cursor-pointer ${
                                    isDraggingStyle
                                        ? 'border-solid border-purple-500 bg-purple-50/50'
                                        : 'border-dashed ' + (stylePreview ? 'border-transparent' : 'border-slate-300 hover:border-purple-400 bg-slate-50 hover:bg-purple-50/30')
                                }`}
                                onClick={() => !stylePreview && styleInputRef.current?.click()}
                                onDragOver={handleStyleDragOver}
                                onDragLeave={handleStyleDragLeave}
                                onDrop={handleStyleDrop}
                            >
                                {stylePreview ? (
                                    <>
                                        <img src={stylePreview} alt="Style" className="w-full h-full object-cover" />
                                        <div className="absolute inset-0 bg-black/40 opacity-0 hover:opacity-100 transition-opacity flex items-center justify-center">
                                            <button 
                                                onClick={(e) => { e.stopPropagation(); styleInputRef.current?.click() }}
                                                className="px-4 py-2 bg-white text-slate-800 font-bold rounded-lg shadow-lg flex items-center gap-2"
                                            >
                                                <Upload className="w-4 h-4" /> Change Style
                                            </button>
                                        </div>
                                    </>
                                ) : (
                                    <>
                                        <div className="w-16 h-16 bg-white rounded-full shadow-sm border border-slate-100 flex items-center justify-center text-purple-500 mb-4">
                                            <Upload className="w-8 h-8" />
                                        </div>
                                        <span className="font-bold text-slate-600">Upload or drop Style</span>
                                        <span className="text-sm text-slate-400 mt-1 text-center px-6">An artistic reference image (e.g. Van Gogh painting).</span>
                                    </>
                                )}
                            </div>
                            <input type="file" accept="image/*" className="hidden" ref={styleInputRef} onChange={handleStyleSelect} />
                        </div>
                    </div>

                    {/* Controls & Generate */}
                    <div className="bg-slate-50 rounded-2xl p-6 border border-slate-200">
                        <div className="flex flex-col md:flex-row items-center gap-8">
                            <div className="flex-1 w-full">
                                <label className="font-bold text-slate-700 flex items-center justify-between mb-3">
                                    <span>Style Strength (Alpha)</span>
                                    <span className="text-blue-600 bg-blue-100 px-2.5 py-0.5 rounded-full text-sm">{Math.round(alpha * 100)}%</span>
                                </label>
                                <input 
                                    type="range" 
                                    min="0" max="1" step="0.05" 
                                    value={alpha} 
                                    onChange={(e) => setAlpha(parseFloat(e.target.value))}
                                    className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-[#00a6ed]"
                                />
                                <div className="flex justify-between text-xs font-medium text-slate-400 mt-2 px-1">
                                    <span>Original</span>
                                    <span>Stylized</span>
                                </div>
                            </div>

                            <button 
                                onClick={handleGenerate}
                                disabled={isProcessing || !contentImage || !styleImage}
                                className={`w-full md:w-auto min-w-[200px] px-8 py-4 rounded-xl font-bold text-lg flex items-center justify-center gap-2 transition-all ${
                                    isProcessing || !contentImage || !styleImage 
                                        ? 'bg-slate-200 text-slate-400 cursor-not-allowed shadow-none' 
                                        : 'bg-gradient-to-r from-blue-600 to-purple-600 text-white hover:shadow-lg hover:shadow-purple-500/25 active:scale-95'
                                }`}
                            >
                                {isProcessing ? (
                                    <>
                                        <Loader2 className="w-6 h-6 animate-spin" /> Generating...
                                    </>
                                ) : (
                                    <>
                                        <Wand2 className="w-6 h-6" /> Generate Style
                                    </>
                                )}
                            </button>
                        </div>
                    </div>

                    {/* Result Preview Line */}
                    {resultImage && (
                        <div className="mt-8 pt-8 border-t border-slate-200">
                            <h3 className="text-xl font-bold text-slate-800 mb-6 flex items-center gap-2">
                                <ImageIcon className="w-6 h-6 text-slate-400" /> Result
                            </h3>
                            <div className="flex flex-col items-center w-full max-w-2xl mx-auto">
                                <div className="w-full rounded-2xl overflow-hidden shadow-xl border border-slate-200 bg-white p-2">
                                    <img src={resultImage} alt="Generated Style Transfer" className="w-full h-auto rounded-xl" />
                                </div>
                                <div className="flex items-center gap-4 mt-6">
                                    <button 
                                        onClick={() => setIsShareModalOpen(true)}
                                        className="px-8 py-3 bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 rounded-xl font-bold shadow-sm transition-all flex items-center gap-3"
                                    >
                                        <Share2 className="w-5 h-5 text-purple-600" /> Share to Feed
                                    </button>
                                    <a 
                                        href={resultImage} 
                                        download="stylized_result.jpg"
                                        className="px-8 py-3 bg-slate-900 text-white hover:bg-slate-800 rounded-xl font-bold shadow-lg shadow-slate-900/20 transition-all flex items-center gap-3"
                                    >
                                        <Download className="w-5 h-5" /> Download Result
                                    </a>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
            {isShareModalOpen && resultImage && (
                <DirectShareModal 
                    imageToShare={resultImage} 
                    aiOperation="Style Transfer" 
                    onClose={() => setIsShareModalOpen(false)} 
                />
            )}
        </div>
    );
};
