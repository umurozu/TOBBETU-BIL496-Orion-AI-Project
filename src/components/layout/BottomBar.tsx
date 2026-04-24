import React from 'react';
import { useEditorStore } from '../../store/editorStore';
import { ZoomIn, ZoomOut, RotateCcw, Columns, Download, Share2, Trash2 } from 'lucide-react';
import { ShareModal } from '../community/ShareModal';
import { downloadImage, APIError } from '../../services/api';

export const BottomBar: React.FC = () => {
    const { zoom, setZoom, compareMode, setCompareMode, processedImage, sessionId, setError, uploadedImage, resetSession } = useEditorStore();
    const [isShareModalOpen, setIsShareModalOpen] = React.useState(false);
    const [isDownloading, setIsDownloading] = React.useState(false);

    const handleZoomOut = () => setZoom(Math.max(10, zoom - 10));
    const handleZoomIn = () => setZoom(Math.min(200, zoom + 10));
    const handleResetImage = () => {
        if (uploadedImage?.startsWith('blob:')) {
            try {
                URL.revokeObjectURL(uploadedImage);
            } catch {
                // no-op
            }
        }

        setZoom(100);
        resetSession();
    };

    const handleDownload = async () => {
        if (!processedImage || !sessionId) return;

        setIsDownloading(true);
        try {
            const blob = await downloadImage(sessionId, 'png');
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'invisio_result.png';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        } catch (error: unknown) {
            if (error instanceof APIError) {
                setError(error.message, error.errorCode);
            } else {
                setError('Download failed. Please try again.');
            }
        } finally {
            setIsDownloading(false);
        }
    };

    return (
        <div className="h-16 bg-white border-t border-slate-200 flex items-center justify-between px-6 shrink-0 z-10 shadow-sm">
            <div className="flex items-center gap-4">
                <button 
                    title="Revert to Original" 
                    onClick={() => useEditorStore.getState().revertToOriginal()}
                    disabled={!processedImage}
                    className="p-2 hover:bg-slate-100 rounded-lg text-slate-600 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                    <RotateCcw className="w-5 h-5" />
                </button>
                {processedImage && (
                    <button
                        onClick={() => setCompareMode(!compareMode)}
                        className={`p-2 rounded-lg transition-colors flex items-center gap-2 text-sm font-medium ${compareMode ? 'bg-blue-50 text-blue-600' : 'hover:bg-slate-100 text-slate-600'}`}
                    >
                        <Columns className="w-5 h-5" />
                        <span>Compare</span>
                    </button>
                )}
            </div>

            <div className="flex items-center gap-4">
                <button onClick={handleZoomOut} className="p-1 hover:bg-slate-100 rounded text-slate-500">
                    <ZoomOut className="w-5 h-5" />
                </button>
                <div className="w-48">
                    <input
                        type="range"
                        min="10"
                        max="200"
                        value={zoom}
                        onChange={(e) => setZoom(Number(e.target.value))}
                        className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                    />
                </div>
                <button
                    title="Reset / Remove Image"
                    onClick={handleResetImage}
                    disabled={!uploadedImage}
                    className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-700 text-sm font-bold shadow-sm hover:bg-slate-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                    <Trash2 className="w-4 h-4" />
                    Reset
                </button>
                <span className="text-sm font-medium text-slate-600 w-12 text-center">{zoom}%</span>
                <button onClick={handleZoomIn} className="p-1 hover:bg-slate-100 rounded text-slate-500">
                    <ZoomIn className="w-5 h-5" />
                </button>
            </div>

            <div className="flex items-center gap-3">
                <button
                    onClick={() => setIsShareModalOpen(true)}
                    disabled={!sessionId}
                    className="bg-white border border-slate-200 text-slate-700 px-5 py-2 rounded-lg font-bold text-sm shadow-sm hover:bg-slate-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                    <Share2 size={16} className="text-purple-500" />
                    Share
                </button>

                <button
                    onClick={handleDownload}
                    disabled={!processedImage || !sessionId || isDownloading}
                    className="bg-[#00a6ed] text-white px-5 py-2 rounded-lg font-bold text-sm shadow-sm hover:bg-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                    <Download size={16} />
                    {isDownloading ? 'Exporting...' : 'Download'}
                </button>
            </div>

            {isShareModalOpen && (
                <ShareModal onClose={() => setIsShareModalOpen(false)} />
            )}
        </div>
    );
};
