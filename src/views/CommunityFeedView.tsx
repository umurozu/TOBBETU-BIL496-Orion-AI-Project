import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getCommunityFeed, type CommunityPostData } from '../services/api';
import { CommunityPostCard } from '../components/community/CommunityPostCard';
import { FeedSkeleton, EmptyState } from '../components/community/FeedSkeleton';
import { Sparkles, RefreshCw } from 'lucide-react';
import { useAuthStore } from '../store/authStore';

const CommunityFeedView: React.FC = () => {
    const { accessToken } = useAuthStore();
    const [posts, setPosts] = useState<CommunityPostData[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isFetchingMore, setIsFetchingMore] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [nextCursor, setNextCursor] = useState<number | null>(null);
    const [hasMore, setHasMore] = useState(true);
    
    // Observer ref for infinite scroll
    const observer = useRef<IntersectionObserver | null>(null);
    const lastPostRef = useCallback((node: HTMLDivElement) => {
        if (isLoading || isFetchingMore) return;
        if (observer.current) observer.current.disconnect();
        
        observer.current = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting && hasMore) {
                fetchMoreLogs();
            }
        });
        
        if (node) observer.current.observe(node);
    }, [isLoading, isFetchingMore, hasMore]);

    const loadInitialFeed = async () => {
        try {
            setIsLoading(true);
            setError(null);
            const response = await getCommunityFeed(10, undefined, accessToken || undefined);
            if (response.data) {
                setPosts(response.data.items);
                setNextCursor(response.data.next_cursor);
                setHasMore(response.data.next_cursor !== null);
            }
        } catch (err: any) {
            setError(err.message || 'Failed to load community feed');
        } finally {
            setIsLoading(false);
        }
    };

    const fetchMoreLogs = async () => {
        if (!nextCursor || isFetchingMore) return;
        try {
            setIsFetchingMore(true);
            const response = await getCommunityFeed(10, nextCursor, accessToken || undefined);
            if (response.data) {
                setPosts(prev => {
                    // Filter duplicates in case of race conditions
                    const newItems = response.data!.items.filter(
                        newItem => !prev.some(p => p.id === newItem.id)
                    );
                    return [...prev, ...newItems];
                });
                setNextCursor(response.data.next_cursor);
                setHasMore(response.data.next_cursor !== null);
            }
        } catch (err) {
            console.error('Pagination error:', err);
        } finally {
            setIsFetchingMore(false);
        }
    };

    useEffect(() => {
        loadInitialFeed();
    }, []);

    const handleDelete = (postId: number) => {
        setPosts(prev => prev.filter(p => p.id !== postId));
    };

    return (
        <div className="w-full h-full flex flex-col bg-[#f4f6f8] overflow-hidden relative">
            {/* Minimal Header */}
            <div className="shrink-0 bg-white/80 backdrop-blur-md border-b border-slate-200 py-4 px-6 sticky top-0 z-10 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-500 to-indigo-500 flex items-center justify-center text-white shadow-sm">
                        <Sparkles size={16} />
                    </div>
                    <h1 className="text-xl font-bold text-slate-800 tracking-tight">Community</h1>
                </div>
                <button 
                    onClick={loadInitialFeed}
                    disabled={isLoading}
                    className="p-2 text-slate-400 hover:text-blue-500 hover:bg-blue-50 rounded-full transition-colors disabled:opacity-50"
                    title="Refresh Feed"
                >
                    <RefreshCw size={18} className={isLoading ? 'animate-spin' : ''} />
                </button>
            </div>

            {/* Scrollable Feed */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-4 sm:p-6 pb-24">
                <div className="max-w-xl mx-auto">
                    {error && (
                        <div className="bg-red-50 text-red-600 p-4 rounded-xl text-center font-medium border border-red-100 mb-6">
                            {error}
                            <button 
                                onClick={loadInitialFeed}
                                className="block mx-auto mt-2 text-sm underline hover:text-red-800"
                            >
                                Try again
                            </button>
                        </div>
                    )}

                    {isLoading ? (
                        <>
                            <FeedSkeleton />
                            <FeedSkeleton />
                        </>
                    ) : posts.length === 0 && !error ? (
                        <EmptyState />
                    ) : (
                        <div className="space-y-6">
                            {posts.map((post, index) => {
                                const isLast = index === posts.length - 1;
                                return (
                                    <div key={post.id} ref={isLast ? lastPostRef : null}>
                                        <CommunityPostCard post={post} onDelete={handleDelete} />
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {isFetchingMore && (
                        <div className="py-6 scale-95 opacity-70">
                            <FeedSkeleton />
                        </div>
                    )}
                    
                    {!hasMore && posts.length > 0 && !isLoading && (
                        <div className="text-center py-8 text-slate-400 text-sm font-medium">
                            You've caught up with the latest posts!
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default CommunityFeedView;
