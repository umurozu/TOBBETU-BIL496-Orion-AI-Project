/**
 * DownloadView — LLD §3.1.3, Class: DownloadView
 * 
 * Format selection and download interface.
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Download, ArrowLeft, Check } from 'lucide-react';
import { useEditorStore } from '../store/editorStore';
import { downloadImage, APIError } from '../services/api';

const FORMATS = [
    { id: 'png', label: 'PNG', description: 'Lossless, transparent support' },
    { id: 'jpeg', label: 'JPEG', description: 'Smallest file size' },
    { id: 'webp', label: 'WebP', description: 'Modern, efficient' },
];

export default function DownloadView() {
    const { sessionId, setCurrentView, setError } = useEditorStore();
    const [selectedFormat, setSelectedFormat] = useState('png');
    const [isDownloading, setIsDownloading] = useState(false);
    const [downloadComplete, setDownloadComplete] = useState(false);

    const handleDownload = async () => {
        if (!sessionId) return;

        setIsDownloading(true);
        try {
            const blob = await downloadImage(sessionId, selectedFormat);

            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `invisio_result.${selectedFormat === 'jpeg' ? 'jpg' : selectedFormat}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            setDownloadComplete(true);
        } catch (e: unknown) {
            if (e instanceof APIError) {
                setError(e.message, e.errorCode);
            } else {
                setError('Download failed. Please try again.');
            }
        } finally {
            setIsDownloading(false);
        }
    };

    return (
        <div className="flex flex-col gap-4 p-4 w-full">
            <h3 className="text-white/70 text-xs font-semibold uppercase tracking-wider mb-1">
                Export
            </h3>

            {FORMATS.map((fmt) => (
                <motion.button
                    key={fmt.id}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setSelectedFormat(fmt.id)}
                    className={`
            flex items-center gap-3 p-3 rounded-xl transition-all
            ${selectedFormat === fmt.id
                            ? 'bg-blue-500/20 border border-blue-500/50'
                            : 'bg-white/5 hover:bg-white/10 border border-transparent'
                        }
          `}
                >
                    <div className={`
            w-5 h-5 rounded-full border-2 flex items-center justify-center
            ${selectedFormat === fmt.id ? 'border-blue-400 bg-blue-500' : 'border-white/30'}
          `}>
                        {selectedFormat === fmt.id && <Check className="w-3 h-3 text-white" />}
                    </div>
                    <div className="text-left">
                        <p className="text-white text-sm font-medium">{fmt.label}</p>
                        <p className="text-white/40 text-xs">{fmt.description}</p>
                    </div>
                </motion.button>
            ))}

            <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleDownload}
                disabled={isDownloading}
                className="flex items-center justify-center gap-2 p-3 mt-2 rounded-xl bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 transition-all disabled:opacity-50"
            >
                {isDownloading ? (
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : downloadComplete ? (
                    <>
                        <Check className="w-5 h-5 text-white" />
                        <span className="text-white text-sm font-semibold">Downloaded!</span>
                    </>
                ) : (
                    <>
                        <Download className="w-5 h-5 text-white" />
                        <span className="text-white text-sm font-semibold">Download</span>
                    </>
                )}
            </motion.button>

            <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setCurrentView('preview')}
                className="flex items-center gap-2 p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-all"
            >
                <ArrowLeft className="w-4 h-4 text-white/50" />
                <span className="text-white/50 text-sm">Back to Preview</span>
            </motion.button>
        </div>
    );
}
