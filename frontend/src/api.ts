const API_BASE = 'http://localhost:8000/api';

export interface DashboardStats {
    total_images: number;
    processed_images: number;
    unprocessed_images: number;
    total_detections: number;
    total_animals: number;
    quoll_detections: number;
    total_individuals: number;
    total_cameras: number;
    total_collections: number;
    processing_percent: number;
}

export interface ImageData {
    id: number;
    filename: string;
    file_path: string;
    camera_id: number | null;
    collection_id: number | null;
    captured_at: string | null;
    width: number | null;
    height: number | null;
    processed: boolean;
    has_animal: boolean | null;
    thumbnail_path: string | null;
}

export interface Detection {
    id: number;
    image_id: number;
    bbox_x: number;
    bbox_y: number;
    bbox_w: number;
    bbox_h: number;
    detection_confidence: number;
    category: string | null;
    species: string | null;
    classification_confidence: number | null;
    model_version: string | null;
    crop_path: string | null;
    created_at: string | null;
}

export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    per_page: number;
    pages: number;
}

export interface IndividualData {
    individual_id: string;
    species: string;
    first_seen: string | null;
    last_seen: string | null;
    total_sightings: number;
}

export interface SpeciesCount {
    species: string;
    count: number;
}

export interface CameraStat {
    name: string;
    latitude: number | null;
    longitude: number | null;
    image_count: number;
}

export interface CollectionStat {
    name: string;
    image_count: number;
}

// --- API Functions ---

export async function fetchStats(): Promise<DashboardStats> {
    const res = await fetch(`${API_BASE}/stats/`);
    if (!res.ok) throw new Error('Failed to fetch stats');
    return res.json();
}

export async function fetchImages(params: {
    page?: number;
    per_page?: number;
    camera_id?: number;
    collection_id?: number;
    processed?: boolean;
    has_animal?: boolean;
}): Promise<PaginatedResponse<ImageData>> {
    const searchParams = new URLSearchParams();
    if (params.page) searchParams.set('page', String(params.page));
    if (params.per_page) searchParams.set('per_page', String(params.per_page));
    if (params.camera_id !== undefined) searchParams.set('camera_id', String(params.camera_id));
    if (params.collection_id !== undefined) searchParams.set('collection_id', String(params.collection_id));
    if (params.processed !== undefined) searchParams.set('processed', String(params.processed));
    if (params.has_animal !== undefined) searchParams.set('has_animal', String(params.has_animal));

    const res = await fetch(`${API_BASE}/images/?${searchParams}`);
    if (!res.ok) throw new Error('Failed to fetch images');
    return res.json();
}

export async function fetchDetections(params: {
    page?: number;
    per_page?: number;
    species?: string;
    min_confidence?: number;
    image_id?: number;
}): Promise<PaginatedResponse<Detection>> {
    const searchParams = new URLSearchParams();
    if (params.page) searchParams.set('page', String(params.page));
    if (params.per_page) searchParams.set('per_page', String(params.per_page));
    if (params.species) searchParams.set('species', params.species);
    if (params.min_confidence) searchParams.set('min_confidence', String(params.min_confidence));
    if (params.image_id) searchParams.set('image_id', String(params.image_id));

    const res = await fetch(`${API_BASE}/detections/?${searchParams}`);
    if (!res.ok) throw new Error('Failed to fetch detections');
    return res.json();
}

export async function fetchSpeciesCounts(): Promise<SpeciesCount[]> {
    const res = await fetch(`${API_BASE}/detections/species-counts`);
    if (!res.ok) throw new Error('Failed to fetch species counts');
    return res.json();
}

export async function fetchCameraStats(): Promise<CameraStat[]> {
    const res = await fetch(`${API_BASE}/stats/cameras`);
    if (!res.ok) throw new Error('Failed to fetch camera stats');
    return res.json();
}

export async function fetchCollectionStats(): Promise<CollectionStat[]> {
    const res = await fetch(`${API_BASE}/stats/collections`);
    if (!res.ok) throw new Error('Failed to fetch collection stats');
    return res.json();
}

export async function fetchIndividuals(): Promise<IndividualData[]> {
    const res = await fetch(`${API_BASE}/stats/individuals`);
    if (!res.ok) throw new Error('Failed to fetch individuals');
    return res.json();
}
