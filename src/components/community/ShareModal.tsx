import React, { useState } from 'react';
import { X, Sparkles, Loader2, Image as ImageIcon } from 'lucide-react';
import { createPortal } from 'react-dom';
import { shareToCommunity } from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useEditorStore } from '../../store/editorStore';

interface ShareModalProps {
    onClose: () => void;
}

export const ShareModal: React.FC<ShareModalProps> = ({ onClose }) => {
    const { accessToken } = useAuthStore();
    const { sessionId, processedImage, uploadedImage, setCurrentView } = useEditorStore();
    
    const [caption, setCaption] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    const imageToShare = processedImage || uploadedImage;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!accessToken || !sessionId) return;

        try {
            setIsSubmitting(true);
            setError('');
            await shareToCommunity(sessionId, caption, accessToken);
            
            // On success, redirect to community feed right away
            onClose();
            setCurrentView('community');
        } catch (err: any) {
            const msg = err.message || '';
            if (msg.toLowerCase().includes('expire') || msg.toLowerCase().includes('unauthorized') || err.statusCode === 401) {
                setError('Your session has expired. Please log out, log back in, and try again.');
            } else {
                setError(msg || 'Failed to share image. Please try again.');
            }
            setIsSubmitting(false);
        }
    };

    if (!imageToShare) return null;

    const modalContent = (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-in fade-in duration-200" style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh' }}>
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md max-h-[95vh] flex flex-col overflow-hidden relative animate-in zoom-in-95 duration-200">
                {/* Header */}
                <div className="flex items-center justify-between p-5 border-b border-slate-100 shrink-0">
                    <div className="flex items-center gap-2 text-slate-900">
                        <Sparkles size={20} className="text-blue-500" />
                        <h2 className="text-lg font-bold tracking-tight">Share to Community</h2>
                    </div>
                    <button 
                        onClick={onClose}
                        className="text-slate-400 hover:text-slate-700 hover:bg-slate-100 p-2 rounded-full transition-colors"
                    >
                        <X size={20} />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="flex flex-col overflow-hidden flex-1">
                    <div className="p-6 overflow-y-auto custom-scrollbar">
                        {error && (
                            <div className="bg-red-50 text-red-600 p-3 rounded-xl text-sm font-medium mb-4 border border-red-100">
                                {error}
                            </div>
                        )}

                        {/* Image Preview */}
                        <div className="w-full h-48 bg-slate-100 rounded-xl overflow-hidden mb-5 border border-slate-200 shadow-inner flex flex-col items-center justify-center relative shrink-0">
                            {imageToShare ? (
                                <img src={imageToShare} alt="Preview" className="w-full h-full object-contain" />
                            ) : (
                                <ImageIcon size={48} className="text-slate-300" />
                            )}
                        </div>

                        {/* Caption Input */}
                        <div>
                            <label className="block text-[13px] font-bold text-slate-700 mb-1.5 px-1">
                                Caption (Optional)
                            </label>
                            <textarea
                                value={caption}
                                onChange={(e) => setCaption(e.target.value)}
                                placeholder="What inspired this edit?..."
                                rows={3}
                                className="w-full bg-slate-50 border border-slate-200 text-slate-900 text-sm rounded-xl p-3 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all font-medium placeholder:text-slate-400 resize-none"
                                maxLength={500}
                            />
                        </div>
                    </div>

                    {/* Footer Actions */}
                    <div className="p-5 border-t border-slate-100 bg-slate-50 flex items-center gap-3 shrink-0">
                        <button
                            type="button"
                            onClick={onClose}
                            className="flex-1 px-4 py-3 text-slate-600 font-bold bg-white border border-slate-200 hover:bg-slate-50 rounded-xl transition-colors text-sm"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmitting || !sessionId}
                            className="flex-1 px-4 py-3 text-white font-bold bg-gradient-to-r from-blue-600 to-purple-600 hover:shadow-lg hover:shadow-blue-600/20 rounded-xl transition-all disabled:opacity-50 flex items-center justify-center gap-2 text-sm"
                        >
                            {isSubmitting ? (
                                <>
                                    <Loader2 size={18} className="animate-spin" />
                                    Sharing...
                                </>
                            ) : (
                                'Share Now'
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );

    return createPortal(modalContent, document.body);
};
