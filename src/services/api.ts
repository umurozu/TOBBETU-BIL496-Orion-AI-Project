/**
 * API Service Layer — LLD §2.1.1
 * Handles all communication between frontend and backend REST API.
 *
 * Endpoints:
 *   POST /upload        → uploadImage()
 *   POST /process       → processImage()
 *   GET  /status/:id    → getStatus()
 *   GET  /download/:id  → downloadImage()
 *   POST /refine        → refineMask()
 *   POST /regenerate    → regenerateImage()
 */

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const DEFAULT_TIMEOUT = 30000; // 30 seconds for AI processing

/** Helper to fetch with a timeout */
async function fetchWithTimeout(resource: RequestInfo, options: RequestInit & { timeout?: number } = {}) {
    const { timeout = DEFAULT_TIMEOUT } = options;
    
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    
    try {
        return await fetch(resource, {
            ...options,
            signal: controller.signal
        });
    } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
            throw new APIError(
                'Request timed out. Backend may still be starting or overloaded.',
                'REQUEST_TIMEOUT',
                408
            );
        }
        throw error;
    } finally {
        clearTimeout(id);
    }
}

export interface APIResponse<T = Record<string, unknown>> {
    status: 'success' | 'error';
    message: string;
    data?: T;
    error_code?: string;
}

export interface UploadData {
    session_id: string;
    image_id: string;
    width: number;
    height: number;
    format: string;
    size: number;
}

export interface ProcessData {
    session_id: string;
    result_id: string;
    result_image: string; // base64
    format: string;
}

export interface StatusData {
    session_id: string;
    status: string;
    has_image: boolean;
    has_result: boolean;
    expires_at: string | null;
}

export interface DetectSignatureData {
    filename: string;
    has_signature: boolean;
    confidence: number;
    matched_bits: number;
    total_bits: number;
    average_strength?: number;
    reason: string;
}

export interface HairstylePreset {
    id: string;
    label: string;
    description: string;
    image_url: string;
}

export interface HairstyleColorOption {
    id: string;
    label: string;
    swatch: string;
}

/**
 * Uploads an image file to the backend.
 * Creates a new session and returns session info.
 */
export async function uploadImage(file: File): Promise<APIResponse<UploadData>> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetchWithTimeout(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData,
        timeout: 45000 // cold-start upload may include first model warmup
    });

    if (!response.ok) {
        try {
            const errorData = await response.json();
            throw new APIError(
                errorData.message || `Upload failed (${response.status})`,
                errorData.error_code || 'UPLOAD_ERROR',
                response.status
            );
        } catch (parseError) {
            if (parseError instanceof APIError) throw parseError;
            throw new APIError(
                `Server error (${response.status}). Check if backend is running.`,
                'SERVER_ERROR',
                response.status
            );
        }
    }

    return response.json();
}

/**
 * Applies an AI editing operation on the uploaded image.
 */
export async function processImage(
    sessionId: string,
    editingType: string,
    parameters: Record<string, unknown> = {}
): Promise<APIResponse<ProcessData>> {
    const response = await fetchWithTimeout(`${API_BASE_URL}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionId,
            editing_type: editingType,
            parameters,
        }),
        timeout: 45000 // 45s for potentially heavy AI model processing
    });

    if (!response.ok) {
        try {
            const errorData = await response.json();
            throw new APIError(
                errorData.message || `Processing failed (${response.status})`,
                errorData.error_code || 'PROCESS_ERROR',
                response.status
            );
        } catch (parseError) {
            if (parseError instanceof APIError) throw parseError;
            throw new APIError(`Server error (${response.status})`, 'SERVER_ERROR', response.status);
        }
    }

    return response.json();
}

/**
 * Retrieves the current session status.
 */
export async function getStatus(sessionId: string): Promise<APIResponse<StatusData>> {
    const response = await fetch(`${API_BASE_URL}/status/${sessionId}`);

    if (!response.ok) {
        const errorData = await response.json();
        throw new APIError(errorData.message, errorData.error_code, response.status);
    }

    return response.json();
}

/**
 * Downloads the processed image in the specified format.
 */
export async function downloadImage(
    sessionId: string,
    format: string = 'png'
): Promise<Blob> {
    const response = await fetch(
        `${API_BASE_URL}/download/${sessionId}?format=${format}`
    );

    if (!response.ok) {
        const errorData = await response.json();
        throw new APIError(errorData.message, errorData.error_code, response.status);
    }

    return response.blob();
}

/**
 * Uploads an image to verify whether it contains the Invisio export signature.
 */
export async function detectInvisioImage(
    file: File
): Promise<APIResponse<DetectSignatureData>> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetchWithTimeout(`${API_BASE_URL}/detect-invisio-image`, {
        method: 'POST',
        body: formData,
        timeout: 20000
    });

    if (!response.ok) {
        try {
            const errorData = await response.json();
            throw new APIError(
                errorData.message || `Detection failed (${response.status})`,
                errorData.error_code || 'SIGNATURE_DETECTION_ERROR',
                response.status
            );
        } catch (parseError) {
            if (parseError instanceof APIError) throw parseError;
            throw new APIError(`Server error (${response.status})`, 'SERVER_ERROR', response.status);
        }
    }

    return response.json();
}

export async function getHairstylePresets(): Promise<APIResponse<{ items: HairstylePreset[]; color_options: HairstyleColorOption[] }>> {
    const response = await fetchWithTimeout(`${API_BASE_URL}/hairstyle-presets`, {
        method: 'GET',
        timeout: 15000
    });

    if (!response.ok) {
        try {
            const errorData = await response.json();
            throw new APIError(
                errorData.message || `Preset fetch failed (${response.status})`,
                errorData.error_code || 'HAIRSTYLE_PRESET_ERROR',
                response.status
            );
        } catch (parseError) {
            if (parseError instanceof APIError) throw parseError;
            throw new APIError(`Server error (${response.status})`, 'SERVER_ERROR', response.status);
        }
    }

    return response.json();
}

export async function generateHairstyleTryOn(
    file: File,
    styleId: string = '',
    hairColor: string
): Promise<Blob> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('style_id', styleId);
    formData.append('hair_color', hairColor);

    const response = await fetchWithTimeout(`${API_BASE_URL}/hairstyle-tryon`, {
        method: 'POST',
        body: formData,
        timeout: 300000
    });

    if (!response.ok) {
        try {
            const errorData = await response.json();
            throw new APIError(
                errorData.message || `Hairstyle generation failed (${response.status})`,
                errorData.error_code || 'HAIRSTYLE_GENERATION_ERROR',
                response.status
            );
        } catch (parseError) {
            if (parseError instanceof APIError) throw parseError;
            throw new APIError(`Server error (${response.status})`, 'SERVER_ERROR', response.status);
        }
    }

    return response.blob();
}

export async function generateHairTransfer(
    sessionId: string,
    shapeReference: File,
    colorReference: File
): Promise<APIResponse<ProcessData>> {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('shape_reference', shapeReference);
    formData.append('color_reference', colorReference);

    const response = await fetchWithTimeout(`${API_BASE_URL}/hair-transfer`, {
        method: 'POST',
        body: formData,
        timeout: 180000
    });

    if (!response.ok) {
        try {
            const errorData = await response.json();
            throw new APIError(
                errorData.message || `Hair transfer failed (${response.status})`,
                errorData.error_code || 'HAIR_TRANSFER_ERROR',
                response.status
            );
        } catch (parseError) {
            if (parseError instanceof APIError) throw parseError;
            throw new APIError(`Server error (${response.status})`, 'SERVER_ERROR', response.status);
        }
    }

    return response.json();
}

/**
 * Submits mask refinement brush data.
 */
export async function refineMask(
    sessionId: string,
    maskData: string,
    brushSize: number = 10,
    brushStrength: number = 1.0
): Promise<APIResponse> {
    const response = await fetch(`${API_BASE_URL}/refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionId,
            mask_data: maskData,
            brush_size: brushSize,
            brush_strength: brushStrength,
        }),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new APIError(errorData.message, errorData.error_code, response.status);
    }

    return response.json();
}

/**
 * Regenerates image with refined mask.
 */
export async function regenerateImage(
    sessionId: string,
    refinedMask: string
): Promise<APIResponse<ProcessData>> {
    const response = await fetch(`${API_BASE_URL}/regenerate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionId,
            mask_data: refinedMask,
        }),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new APIError(errorData.message, errorData.error_code, response.status);
    }

    return response.json();
}

/**
 * Deletes a session and all associated data.
 */
export async function deleteSession(sessionId: string): Promise<APIResponse> {
    const response = await fetch(`${API_BASE_URL}/session/${sessionId}`, {
        method: 'DELETE',
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new APIError(errorData.message, errorData.error_code, response.status);
    }

    return response.json();
}

// ------------------------------------------------------------------
// Community Sharing API
// ------------------------------------------------------------------

export interface CommunityPostData {
    id: number;
    owner_id: number;
    owner_username: string;
    image_url: string;
    ai_operation?: string;
    caption?: string;
    likes: number;
    is_liked_by_me: boolean;
    comments_count: number;
    views: number;
    shared_at: string;
}

export interface CommunityCommentData {
    id: number;
    user_id: number;
    username: string;
    text: string;
    created_at: string;
}

export interface CommunityFeedData {
    items: CommunityPostData[];
    next_cursor: number | null;
    total: number;
}

/**
 * Shares the current session image to the public community feed.
 */
export async function shareToCommunity(
    sessionId: string,
    caption: string,
    token: string
): Promise<APIResponse<{ post_id: number; image_url: string; shared_at: string }>> {
    const response = await fetch(`${API_BASE_URL}/community/share`, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            session_id: sessionId,
            caption: caption,
        }),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new APIError(errorData.detail || errorData.message || 'Failed to share to community', errorData.error_code || 'SHARE_ERROR', response.status);
    }
    return response.json();
}

/**
 * Shares a base64 or blob image directly to the public community feed.
 */
export async function shareDirectToCommunity(
    imageBlob: Blob,
    caption: string,
    aiOperation: string,
    token: string
): Promise<APIResponse<{ post_id: number; image_url: string; shared_at: string }>> {
    const formData = new FormData();
    formData.append('image', imageBlob, 'shared_image.jpg');
    formData.append('caption', caption);
    formData.append('ai_operation', aiOperation);

    const response = await fetch(`${API_BASE_URL}/community/share-direct`, {
        method: 'POST',
        headers: { 
            'Authorization': `Bearer ${token}`
        },
        body: formData,
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new APIError(errorData.detail || errorData.message || 'Failed to share to community', errorData.error_code || 'SHARE_ERROR', response.status);
    }
    return response.json();
}

/**
 * Fetches the global community feed (Instagram-style).
 */
export async function getCommunityFeed(
    limit: number = 20,
    cursor?: number,
    token?: string
): Promise<APIResponse<CommunityFeedData>> {
    let url = `${API_BASE_URL}/community/feed?limit=${limit}`;
    if (cursor !== undefined && cursor !== null) {
        url += `&cursor=${cursor}`;
    }

    const headers: Record<string, string> = {};
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetchWithTimeout(url, { headers, timeout: 20000 });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new APIError(errorData.detail || errorData.message || 'Failed to fetch community feed', errorData.error_code || 'FEED_ERROR', response.status);
    }
    return response.json();
}

/**
 * Fetches all posts shared by a specific user.
 */
export async function getUserSharedPosts(
    userId: number,
    token?: string
): Promise<APIResponse<{ items: CommunityPostData[] }>> {
    const headers: Record<string, string> = {};
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}/users/${userId}/shared-images`, { headers });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new APIError(errorData.detail || errorData.message || 'Failed to fetch user posts', errorData.error_code || 'USER_POSTS_ERROR', response.status);
    }
    return response.json();
}

/**
 * Deletes a community post. Only allowed if the user owns the post.
 */
export async function deleteCommunityPost(
    postId: number,
    token: string
): Promise<APIResponse> {
    const response = await fetch(`${API_BASE_URL}/community/post/${postId}`, {
        method: 'DELETE',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new APIError(errorData.detail || errorData.message || 'Failed to delete post', errorData.error_code || 'DELETE_POST_ERROR', response.status);
    }
    return response.json();
}

/**
 * Toggles a like on a community post.
 */
export async function toggleCommunityPostLike(
    postId: number,
    token: string
): Promise<APIResponse<{ is_liked: boolean; likes: number }>> {
    const response = await fetch(`${API_BASE_URL}/community/post/${postId}/like`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new APIError(errorData.detail || errorData.message || 'Failed to toggle like', 'LIKE_ERROR', response.status);
    }
    return response.json();
}

/**
 * Fetches all comments for a community post.
 */
export async function getCommunityPostComments(
    postId: number
): Promise<APIResponse<{ items: CommunityCommentData[] }>> {
    const response = await fetch(`${API_BASE_URL}/community/post/${postId}/comments`);
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new APIError(errorData.detail || errorData.message || 'Failed to fetch comments', 'COMMENTS_ERROR', response.status);
    }
    return response.json();
}

/**
 * Adds a comment to a community post.
 */
export async function addCommunityPostComment(
    postId: number,
    text: string,
    token: string
): Promise<APIResponse<CommunityCommentData>> {
    const response = await fetch(`${API_BASE_URL}/community/post/${postId}/comments`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ text })
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new APIError(errorData.detail || errorData.message || 'Failed to add comment', 'ADD_COMMENT_ERROR', response.status);
    }
    return response.json();
}

/**
 * Custom error class for API errors.
 */
export class APIError extends Error {
    errorCode: string;
    statusCode: number;

    constructor(message: string, errorCode: string, statusCode: number) {
        super(message);
        this.name = 'APIError';
        this.errorCode = errorCode;
        this.statusCode = statusCode;
    }
}
