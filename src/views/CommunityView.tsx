/**
 * CommunityView — LLD §3.2.1, Class: CommunityView
 *
 * Displays shared community images and allows interaction
 * such as viewing and liking. Communicates with backend via API.
 */

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
    Heart,
    Eye,
    RefreshCw,
    ArrowLeft,
    Loader2,
    Image as ImageIcon,
} from 'lucide-react';
import { useEditorStore } from '../store/editorStore';

interface CommunityImage {
    imageId: string;
    thumbnailUrl: string;
    likeCount: number;
    viewCount: number;
    ownerId: string;
    sharedAt: string;
}

export default function CommunityView() {
    const { setCurrentView } = useEditorStore();

    const [communityImages, setCommunityImages] = useState<CommunityImage[]>([]);
    const [selectedImageId, setSelectedImageId] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

    /** Fetches community gallery data */
    const refreshGallery = useCallback(async () => {
        setLoading(true);
        try {
            const response = await fetch(`${API_BASE_URL}/community`);
            if (response.ok) {
                const data = await response.json();
                if (data.status === 'success' && data.data) {
                    setCommunityImages(data.data.images || []);
                }
            }
        } catch {
            // Community feature is optional; silently handle errors
        } finally {
            setLoading(false);
        }
    }, [API_BASE_URL]);

    useEffect(() => {
        refreshGallery();
    }, [refreshGallery]);

    /** Handles viewing a community image */
    const viewImage = (imageId: string) => {
        setSelectedImageId(imageId);
        // Increment view count on backend
        fetch(`${API_BASE_URL}/community/${imageId}/view`, { method: 'POST' }).catch(() => { });
    };

    /** Handles liking a community image */
    const likeImage = async (imageId: string) => {
        try {
            await fetch(`${API_BASE_URL}/community/${imageId}/like`, { method: 'POST' });
            // Optimistic update
            setCommunityImages((prev) =>
                prev.map((img) =>
                    img.imageId === imageId
                        ? { ...img, likeCount: img.likeCount + 1 }
                        : img
                )
            );
        } catch {
            // Silently handle
        }
    };

    const selectedImage = communityImages.find((img) => img.imageId === selectedImageId);

    return (
        <div className="flex flex-col gap-4 p-4 w-full">
            <div className="flex items-center justify-between">
                <h3 className="text-white/70 text-xs font-semibold uppercase tracking-wider">
                    Community Gallery
                </h3>
                <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={refreshGallery}
                    disabled={loading}
                    className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 transition-colors disabled:opacity-50"
                >
                    <RefreshCw className={`w-4 h-4 text-white/50 ${loading ? 'animate-spin' : ''}`} />
                </motion.button>
            </div>

            {/* Loading State */}
            {loading && communityImages.length === 0 && (
                <div className="flex flex-col items-center gap-3 py-8">
                    <Loader2 className="w-8 h-8 text-white/30 animate-spin" />
                    <p className="text-white/40 text-xs">Loading gallery...</p>
                </div>
            )}

            {/* Empty State */}
            {!loading && communityImages.length === 0 && (
                <div className="flex flex-col items-center gap-3 py-8">
                    <ImageIcon className="w-10 h-10 text-white/20" />
                    <p className="text-white/40 text-xs text-center">
                        No community images yet.<br />
                        Share your creations to get started!
                    </p>
                </div>
            )}

            {/* Image detail view */}
            {selectedImage && (
                <motion.div
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="bg-white/5 rounded-xl p-3 border border-white/10"
                >
                    <img
                        src={selectedImage.thumbnailUrl}
                        alt="Community"
                        className="w-full rounded-lg mb-3 object-cover aspect-square"
                    />
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="flex items-center gap-1 text-white/50 text-xs">
                                <Eye className="w-3 h-3" />
                                <span>{selectedImage.viewCount}</span>
                            </div>
                            <div className="flex items-center gap-1 text-white/50 text-xs">
                                <Heart className="w-3 h-3" />
                                <span>{selectedImage.likeCount}</span>
                            </div>
                        </div>
                        <motion.button
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                            onClick={() => likeImage(selectedImage.imageId)}
                            className="p-1.5 rounded-full bg-pink-500/20 hover:bg-pink-500/30 transition-colors"
                        >
                            <Heart className="w-4 h-4 text-pink-400" />
                        </motion.button>
                    </div>
                    <button
                        onClick={() => setSelectedImageId(null)}
                        className="text-white/40 text-xs mt-2 hover:text-white/60 transition-colors"
                    >
                        ← Back to gallery
                    </button>
                </motion.div>
            )}

            {/* Gallery Grid */}
            {!selectedImage && communityImages.length > 0 && (
                <div className="grid grid-cols-2 gap-2">
                    {communityImages.map((img) => (
                        <motion.button
                            key={img.imageId}
                            whileHover={{ scale: 1.03 }}
                            whileTap={{ scale: 0.97 }}
                            onClick={() => viewImage(img.imageId)}
                            className="relative group rounded-lg overflow-hidden bg-white/5 aspect-square"
                        >
                            <img
                                src={img.thumbnailUrl}
                                alt="Community"
                                className="w-full h-full object-cover"
                            />
                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-end p-2 opacity-0 group-hover:opacity-100">
                                <div className="flex items-center gap-2 text-white text-[10px]">
                                    <span className="flex items-center gap-0.5">
                                        <Heart className="w-3 h-3" /> {img.likeCount}
                                    </span>
                                    <span className="flex items-center gap-0.5">
                                        <Eye className="w-3 h-3" /> {img.viewCount}
                                    </span>
                                </div>
                            </div>
                        </motion.button>
                    ))}
                </div>
            )}

            {/* Back to Home */}
            <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setCurrentView('upload')}
                className="flex items-center gap-2 p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-all mt-2"
            >
                <ArrowLeft className="w-4 h-4 text-white/50" />
                <span className="text-white/50 text-sm">Back to Editor</span>
            </motion.button>
        </div>
    );
}
