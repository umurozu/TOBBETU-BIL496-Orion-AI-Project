import React, { useState } from 'react';
import { Heart, MessageCircle, Share2, Trash2, Send } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { 
    deleteCommunityPost, 
    toggleCommunityPostLike, 
    getCommunityPostComments, 
    addCommunityPostComment, 
    type CommunityPostData,
    type CommunityCommentData 
} from '../../services/api';

interface CommunityPostCardProps {
    post: CommunityPostData;
    onDelete?: (postId: number) => void;
}

export const CommunityPostCard: React.FC<CommunityPostCardProps> = ({ post, onDelete }) => {
    const { user, accessToken } = useAuthStore();
    const [isDeleting, setIsDeleting] = useState(false);

    // Social States
    const [isLiked, setIsLiked] = useState(post.is_liked_by_me || false);
    const [likesCount, setLikesCount] = useState(post.likes || 0);
    const [isLiking, setIsLiking] = useState(false);

    const [showComments, setShowComments] = useState(false);
    const [comments, setComments] = useState<CommunityCommentData[]>([]);
    const [commentsCount, setCommentsCount] = useState(post.comments_count || 0);
    const [loadingComments, setLoadingComments] = useState(false);
    const [commentText, setCommentText] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    // time ago format (e.g. 2h ago, 1d ago)
    const getTimeAgo = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
        
        if (diffInSeconds < 60) return 'Just now';
        
        const diffInMinutes = Math.floor(diffInSeconds / 60);
        if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
        
        const diffInHours = Math.floor(diffInMinutes / 60);
        if (diffInHours < 24) return `${diffInHours}h ago`;
        
        const diffInDays = Math.floor(diffInHours / 24);
        if (diffInDays < 7) return `${diffInDays}d ago`;
        
        return date.toLocaleDateString();
    };

    const isOwner = user?.username === post.owner_username;

    const handleDelete = async () => {
        if (!accessToken || !isOwner) return;
        if (!confirm('Are you sure you want to remove this post from the community?')) return;
        
        try {
            setIsDeleting(true);
            await deleteCommunityPost(post.id, accessToken);
            if (onDelete) onDelete(post.id);
        } catch (error) {
            console.error('Failed to delete post:', error);
            alert('Failed to delete the post. Please try again.');
        } finally {
            setIsDeleting(false);
        }
    };

    const handleLike = async () => {
        if (!accessToken) {
            alert('Please login to interact with posts.');
            return;
        }
        if (isLiking) return;
        
        try {
            setIsLiking(true);
            // Optimistic update
            setIsLiked(!isLiked);
            setLikesCount(prev => isLiked ? prev - 1 : prev + 1);
            
            const res = await toggleCommunityPostLike(post.id, accessToken);
            // Re-sync with server state
            if (res.data) {
                setIsLiked(res.data.is_liked);
                setLikesCount(res.data.likes);
            }
        } catch (error) {
            console.error(error);
            // Revert optimistic update
            setIsLiked(post.is_liked_by_me);
            setLikesCount(post.likes);
        } finally {
            setIsLiking(false);
        }
    };

    const handleToggleComments = async () => {
        if (showComments) {
            setShowComments(false);
            return;
        }
        setShowComments(true);
        if (comments.length === 0) {
            try {
                setLoadingComments(true);
                const res = await getCommunityPostComments(post.id);
                if (res.data) {
                    setComments(res.data.items);
                }
            } catch (error) {
                console.error(error);
            } finally {
                setLoadingComments(false);
            }
        }
    };

    const handleAddComment = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!accessToken) {
            alert('Please login to comment.');
            return;
        }
        if (!commentText.trim() || isSubmitting) return;

        try {
            setIsSubmitting(true);
            const res = await addCommunityPostComment(post.id, commentText, accessToken);
            if (res.data) {
                setComments(prev => [...prev, res.data!]);
                setCommentsCount(prev => prev + 1);
                setCommentText('');
            }
        } catch (error) {
            console.error(error);
            alert('Failed to post comment.');
        } finally {
            setIsSubmitting(false);
        }
    };

    // Replace backend URL with full URL if it's relative
    const imageUrl = post.image_url.startsWith('http') 
        ? post.image_url 
        : `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${post.image_url}`;

    return (
        <div className={`bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow duration-300 w-full max-w-lg mx-auto mb-6 ${isDeleting ? 'opacity-50 pointer-events-none' : ''}`}>
            {/* Header */}
            <div className="flex items-center justify-between p-4">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold text-lg shadow-sm">
                        {post.owner_username.charAt(0).toUpperCase()}
                    </div>
                    <div>
                        <div className="font-bold text-[14px] text-slate-800 tracking-tight leading-tight">
                            {post.owner_username}
                        </div>
                        <div className="text-[12px] text-slate-500 font-medium flex items-center gap-1.5">
                            {post.ai_operation && (
                                <>
                                    <span className="bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider">
                                        {post.ai_operation.replace('_', ' ')}
                                    </span>
                                    <span>•</span>
                                </>
                            )}
                            {getTimeAgo(post.shared_at)}
                        </div>
                    </div>
                </div>
                
                {isOwner && (
                    <button 
                        onClick={handleDelete}
                        disabled={isDeleting}
                        className="text-slate-400 hover:text-red-500 hover:bg-red-50 p-2 rounded-full transition-colors"
                        title="Remove from Community"
                    >
                        <Trash2 size={18} />
                    </button>
                )}
            </div>

            {/* Image */}
            <div className="w-full bg-slate-100 aspect-square sm:aspect-[4/5] relative group flex items-center justify-center overflow-hidden">
                <img 
                    src={imageUrl} 
                    alt={post.caption || 'Community Post'} 
                    className="w-full h-full object-cover"
                    loading="lazy"
                />
            </div>

            {/* Footer / Actions */}
            <div className="p-4">
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-4">
                        <button 
                            onClick={handleLike}
                            className={`transition-colors ${isLiked ? 'text-red-500' : 'text-slate-800 hover:text-slate-500'}`}
                        >
                            <Heart size={24} strokeWidth={2} className={isLiked ? 'fill-current' : ''} />
                        </button>
                        <button onClick={handleToggleComments} className="text-slate-800 hover:text-blue-500 transition-colors">
                            <MessageCircle size={24} strokeWidth={2} />
                        </button>
                        <button className="text-slate-800 hover:text-green-500 transition-colors">
                            <Share2 size={24} strokeWidth={2} />
                        </button>
                    </div>
                </div>

                {/* Likes count */}
                <div className="font-bold text-[14px] text-slate-900 mb-2">
                    {likesCount.toLocaleString()} likes
                </div>

                {/* Caption */}
                {post.caption && (
                    <div className="text-[14px] text-slate-800 leading-snug">
                        <span className="font-bold mr-2">{post.owner_username}</span>
                        {post.caption}
                    </div>
                )}
                
                {/* Comments shortcut */}
                {commentsCount > 0 && !showComments && (
                    <div onClick={handleToggleComments} className="text-[13px] text-slate-500 font-medium mt-2 cursor-pointer hover:text-slate-700">
                        View all {commentsCount} comments
                    </div>
                )}
                {commentsCount === 0 && !showComments && (
                    <div onClick={handleToggleComments} className="text-[13px] text-slate-500 font-medium mt-2 cursor-pointer hover:text-slate-700">
                        Add a comment...
                    </div>
                )}

                {/* Comments Section */}
                {showComments && (
                    <div className="mt-4 border-t border-slate-100 pt-3">
                        {loadingComments ? (
                            <div className="text-center text-slate-400 text-xs py-2">Loading comments...</div>
                        ) : comments.length > 0 ? (
                            <div className="max-h-48 overflow-y-auto space-y-2 mb-3 custom-scrollbar pr-2">
                                {comments.map(c => (
                                    <div key={c.id} className="text-[13px]">
                                        <span className="font-bold text-slate-800 mr-2">{c.username}</span>
                                        <span className="text-slate-700">{c.text}</span>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center text-slate-400 text-xs py-2 mb-2">No comments yet. Be the first!</div>
                        )}

                        <form onSubmit={handleAddComment} className="flex items-center mt-2 relative">
                            <input
                                type="text"
                                placeholder="Add a comment..."
                                value={commentText}
                                onChange={e => setCommentText(e.target.value)}
                                className="flex-1 bg-slate-50 border-none focus:ring-1 focus:ring-blue-100 text-[13px] py-2 px-3 rounded-full text-slate-800 placeholder-slate-400 pr-10 outline-none"
                            />
                            <button 
                                type="submit" 
                                disabled={!commentText.trim() || isSubmitting}
                                className="absolute right-2 text-blue-500 disabled:text-slate-300 p-1 hover:bg-blue-50 rounded-full transition-colors"
                            >
                                <Send size={16} />
                            </button>
                        </form>
                    </div>
                )}
            </div>
        </div>
    );
};
