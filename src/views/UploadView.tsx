/**
 * UploadView — LLD §3.1.3, Class: UploadView
 * 
 * Drag-and-drop image upload with format/size validation.
 * On successful upload, transitions to EditingView.
 */

import { useCallback, useState } from 'react';
import { motion } from 'framer-motion';
import { UploadCloud, Image, AlertCircle } from 'lucide-react';
import { useEditorStore } from '../store/editorStore';
import { uploadImage, deleteSession, APIError } from '../services/api';

const ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png'];
const MAX_SIZE = 10 * 1024 * 1024; // 10 MB

export default function UploadView() {
    const {
        sessionId,
        setUploadedImage,
        setSessionId,
        setImageId,
        setCurrentView,
        setProcessingStatus,
        resetForNewUpload,
    } = useEditorStore();

    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);

    const handleFile = useCallback(async (file: File) => {
        setUploadError(null);
        const previousSessionId = sessionId;

        // Client-side validation
        if (!ALLOWED_TYPES.includes(file.type)) {
            setUploadError('Unsupported format. Please use JPEG or PNG.');
            return;
        }
        if (file.size > MAX_SIZE) {
            setUploadError('File too large. Maximum size is 10 MB.');
            return;
        }

        setIsUploading(true);
        resetForNewUpload();
        setProcessingStatus('uploading');

        try {
            const response = await uploadImage(file);
            if (response.status === 'success' && response.data) {
                setSessionId(response.data.session_id);
                setImageId(response.data.image_id);

                const objectUrl = URL.createObjectURL(file);
                setUploadedImage(objectUrl);

                setProcessingStatus('idle');
                setCurrentView('editing');

                if (previousSessionId && previousSessionId !== response.data.session_id) {
                    void deleteSession(previousSessionId).catch(() => {});
                }
            } else {
                // Backend returned non-success status
                setUploadError(response.message || 'Upload returned an unexpected response.');
                setProcessingStatus('idle');
            }
        } catch (e: unknown) {
            console.error('Upload error:', e);
            if (e instanceof APIError) {
                if (e.errorCode === 'NSFW_DETECTED') {
                    alert(e.message || "NSFW content detected. This image cannot be processed for safety reasons.");
                }
                setUploadError(e.message);
            } else if (e instanceof TypeError && (e.message.includes('fetch') || e.message.includes('Failed'))) {
                // Network error — backend not reachable
                setUploadError('Cannot connect to server. Make sure the backend is running on port 8000.');
            } else if (e instanceof Error) {
                setUploadError(e.message);
            } else {
                setUploadError('Upload failed. Please try again.');
            }
            setProcessingStatus('idle');
        } finally {
            setIsUploading(false);
        }
    }, [resetForNewUpload, sessionId, setUploadedImage, setSessionId, setImageId, setCurrentView, setProcessingStatus]);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    }, [handleFile]);

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => setIsDragging(false);

    const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) handleFile(file);
    };

    return (
        <div className="flex items-center justify-center w-full h-full p-8">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className={`
          relative flex flex-col items-center justify-center
          w-full max-w-lg p-12 rounded-2xl border-2 border-dashed
          transition-all duration-300 cursor-pointer
          ${isDragging
                        ? 'border-blue-500 bg-blue-500/10'
                        : 'border-white/20 bg-white/5 hover:border-white/40 hover:bg-white/10'
                    }
        `}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => document.getElementById('file-input')?.click()}
            >
                <input
                    id="file-input"
                    type="file"
                    accept=".jpg,.jpeg,.png"
                    className="hidden"
                    onChange={handleFileInput}
                />

                {isUploading ? (
                    <div className="flex flex-col items-center gap-4">
                        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                        <p className="text-white/70 text-sm">Uploading...</p>
                    </div>
                ) : (
                    <>
                        <UploadCloud className="w-16 h-16 text-white/50 mb-4" />
                        <h3 className="text-white text-lg font-semibold mb-2">
                            Drop your image here
                        </h3>
                        <p className="text-white/50 text-sm text-center mb-4">
                            or click to browse
                        </p>
                        <div className="flex items-center gap-2 text-white/30 text-xs">
                            <Image className="w-4 h-4" />
                            <span>JPEG, PNG • Max 10 MB</span>
                        </div>
                    </>
                )}

                {uploadError && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mt-4 flex items-center gap-2 text-red-400 text-sm bg-red-500/10 rounded-lg px-4 py-2"
                    >
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        <span>{uploadError}</span>
                    </motion.div>
                )}
            </motion.div>
        </div>
    );
}
