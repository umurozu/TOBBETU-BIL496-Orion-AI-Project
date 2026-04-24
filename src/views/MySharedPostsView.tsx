import React, { useState, useEffect } from 'react';
import { getUserSharedPosts, type CommunityPostData } from '../services/api';
import { CommunityPostCard } from '../components/community/CommunityPostCard';
import { FeedSkeleton, EmptyState } from '../components/community/FeedSkeleton';
import { useAuthStore } from '../store/authStore';
import { LayoutGrid, ArrowLeft } from 'lucide-react';
import { useEditorStore } from '../store/editorStore';

const MySharedPostsView: React.FC = () => {
    const { user, accessToken } = useAuthStore();
    const { setCurrentView } = useEditorStore();
    const [posts, setPosts] = useState<CommunityPostData[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadMyPosts = async () => {
        if (!user) return;
        try {
            setIsLoading(true);
            setError(null);
            const response = await getUserSharedPosts(user.id, accessToken || undefined);
            if (response.data) {
                setPosts(response.data.items);
            }
        } catch (err: any) {
            setError(err.message || 'Failed to load your posts');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadMyPosts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user?.id]);

    const handleDelete = (postId: number) => {
        setPosts(prev => prev.filter(p => p.id !== postId));
    };

    if (!user) {
        return <EmptyState message="Please sign in" subMessage="You need to be signed in to view your posts." />;
    }

    return (
        <div className="w-full h-full flex flex-col bg-[#f4f6f8] overflow-hidden relative">
            {/* Header matching community style */}
            <div className="shrink-0 bg-white/80 backdrop-blur-md border-b border-slate-200 py-4 px-6 sticky top-0 z-10 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <button 
                        onClick={() => setCurrentView('community')}
                        className="p-1.5 text-slate-400 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                        title="Back to Community"
                    >
                        <ArrowLeft size={20} />
                    </button>
                    <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center text-blue-600 shadow-sm">
                        <LayoutGrid size={16} />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold text-slate-800 tracking-tight leading-none">My Profile</h1>
                        <span className="text-[12px] text-slate-500 font-medium">{user.username}</span>
                    </div>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
                <div className="max-w-xl mx-auto">
                    {/* User Stats Summary */}
                    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm mb-8 text-center flex items-center justify-around">
                        <div>
                            <div className="text-2xl font-bold text-slate-800">{posts.length}</div>
                            <div className="text-xs font-bold text-slate-400 uppercase tracking-widest mt-1">Posts</div>
                        </div>
                        <div className="w-px h-10 bg-slate-100"></div>
                        <div>
                            <div className="text-2xl font-bold text-slate-800">
                                {posts.reduce((total, p) => total + p.likes, 0).toLocaleString()}
                            </div>
                            <div className="text-xs font-bold text-slate-400 uppercase tracking-widest mt-1">Likes Given</div>
                        </div>
                    </div>

                    <h2 className="text-lg font-bold text-slate-800 mb-6">Shared Images</h2>

                    {error ? (
                        <div className="bg-red-50 text-red-600 p-4 rounded-xl text-center font-medium border border-red-100">
                            {error}
                        </div>
                    ) : isLoading ? (
                        <div className="space-y-6">
                            <FeedSkeleton />
                            <FeedSkeleton />
                        </div>
                    ) : posts.length === 0 ? (
                        <EmptyState 
                            message="No shared posts" 
                            subMessage="When you share images to the community, they will appear here." 
                        />
                    ) : (
                        <div className="space-y-6">
                            {posts.map((post) => (
                                <CommunityPostCard 
                                    key={post.id} 
                                    post={post} 
                                    onDelete={handleDelete} 
                                />
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default MySharedPostsView;
