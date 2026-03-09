import { useState, useEffect } from 'react';
import './index.css';
import {
    fetchStats,
    fetchImages,
    fetchIndividuals,
    fetchCollectionStats,
    fetchCameraStats,
    fetchSpeciesCounts,
    type DashboardStats,
    type ImageData,
    type IndividualData,
    type CollectionStat,
    type CameraStat,
    type SpeciesCount,
    type PaginatedResponse,
} from './api';

type Page = 'dashboard' | 'images' | 'detections' | 'individuals';

function App() {
    const [page, setPage] = useState<Page>('dashboard');

    return (
        <div className="app">
            <Sidebar currentPage={page} onNavigate={setPage} />
            <main className="main-content">
                {page === 'dashboard' && <Dashboard />}
                {page === 'images' && <ImageBrowser />}
                {page === 'detections' && <DetectionViewer />}
                {page === 'individuals' && <Individuals />}
            </main>
        </div>
    );
}

/* ============================================================
   SIDEBAR
   ============================================================ */
function Sidebar({ currentPage, onNavigate }: { currentPage: Page; onNavigate: (p: Page) => void }) {
    const navItems: { page: Page; icon: string; label: string }[] = [
        { page: 'dashboard', icon: '📊', label: 'Dashboard' },
        { page: 'images', icon: '📷', label: 'Image Browser' },
        { page: 'detections', icon: '🔍', label: 'Detections' },
        { page: 'individuals', icon: '🐾', label: 'Quoll Profiles' },
    ];

    return (
        <aside className="sidebar">
            <div className="sidebar-logo">
                <h1>🌿 <span>Wildlife AI</span></h1>
                <div className="subtitle">Morton NP — Quoll ID</div>
            </div>
            <nav className="sidebar-nav">
                {navItems.map((item) => (
                    <button
                        key={item.page}
                        className={`nav-item ${currentPage === item.page ? 'active' : ''}`}
                        onClick={() => onNavigate(item.page)}
                    >
                        <span className="icon">{item.icon}</span>
                        <span>{item.label}</span>
                    </button>
                ))}
            </nav>
            <div style={{ padding: '1rem 1.5rem', borderTop: '1px solid var(--border)' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    v1.0.0 — RTX 3080
                </div>
            </div>
        </aside>
    );
}

/* ============================================================
   DASHBOARD
   ============================================================ */
function Dashboard() {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [collections, setCollections] = useState<CollectionStat[]>([]);
    const [cameras, setCameras] = useState<CameraStat[]>([]);
    const [species, setSpecies] = useState<SpeciesCount[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function load() {
            try {
                const [s, c, cam, sp] = await Promise.all([
                    fetchStats(),
                    fetchCollectionStats(),
                    fetchCameraStats(),
                    fetchSpeciesCounts(),
                ]);
                setStats(s);
                setCollections(c);
                setCameras(cam);
                setSpecies(sp);
            } catch (e: any) {
                setError(e.message || 'Failed to load data. Is the backend running?');
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    if (loading) return <LoadingState />;
    if (error) return <ErrorState message={error} />;
    if (!stats) return null;

    return (
        <>
            <div className="page-header">
                <h2>Dashboard</h2>
                <p>Morton National Park — Camera Trap Processing Overview</p>
            </div>

            {/* Stats Grid */}
            <div className="stats-grid">
                <StatCard icon="📷" value={fmt(stats.total_images)} label="Total Images" />
                <StatCard icon="✅" value={fmt(stats.processed_images)} label="Processed" />
                <StatCard icon="⏳" value={fmt(stats.unprocessed_images)} label="Unprocessed" />
                <StatCard icon="🐾" value={fmt(stats.quoll_detections)} label="Quoll Detections" />
                <StatCard icon="🆔" value={fmt(stats.total_individuals)} label="Known Quolls" />
                <StatCard icon="📹" value={fmt(stats.total_cameras)} label="Camera Traps" />
                <StatCard icon="📁" value={fmt(stats.total_collections)} label="Collections" />
                <StatCard icon="🔍" value={fmt(stats.total_detections)} label="Total Detections" />
            </div>

            {/* Processing Progress */}
            <div className="card" style={{ marginBottom: '1.5rem' }}>
                <div className="card-header">
                    <h3>⚡ Processing Progress</h3>
                    <span style={{ color: 'var(--primary)', fontWeight: 700, fontSize: '0.9rem' }}>
                        {stats.processing_percent.toFixed(1)}%
                    </span>
                </div>
                <div className="card-body">
                    <div className="progress-bar-bg">
                        <div className="progress-bar-fill" style={{ width: `${stats.processing_percent}%` }} />
                    </div>
                    <div className="progress-label">
                        <span>{fmt(stats.processed_images)} processed</span>
                        <span>{fmt(stats.unprocessed_images)} remaining</span>
                    </div>
                </div>
            </div>

            {/* Collections & Species */}
            <div className="chart-grid">
                <div className="card">
                    <div className="card-header"><h3>📁 Collections</h3></div>
                    <div className="card-body">
                        {collections.length === 0 ? (
                            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '2rem' }}>
                                No collections imported yet. Run bulk_import.py first.
                            </div>
                        ) : (
                            <div className="table-container">
                                <table>
                                    <thead><tr><th>Collection</th><th style={{ textAlign: 'right' }}>Images</th></tr></thead>
                                    <tbody>
                                        {collections.map((c) => (
                                            <tr key={c.name}>
                                                <td>{c.name}</td>
                                                <td style={{ textAlign: 'right', fontWeight: 600 }}>{fmt(c.image_count)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </div>

                <div className="card">
                    <div className="card-header"><h3>🔬 Species Detections</h3></div>
                    <div className="card-body">
                        {species.length === 0 ? (
                            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '2rem' }}>
                                No detections yet. Run the ML pipeline first.
                            </div>
                        ) : (
                            <div className="table-container">
                                <table>
                                    <thead><tr><th>Species</th><th style={{ textAlign: 'right' }}>Count</th></tr></thead>
                                    <tbody>
                                        {species.map((s) => (
                                            <tr key={s.species}>
                                                <td>
                                                    {s.species.toLowerCase().includes('quoll') && '🐾 '}
                                                    {s.species}
                                                </td>
                                                <td style={{ textAlign: 'right', fontWeight: 600 }}>{fmt(s.count)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Camera Overview */}
            {cameras.length > 0 && (
                <div className="card">
                    <div className="card-header"><h3>📹 Camera Stations ({cameras.length})</h3></div>
                    <div className="card-body">
                        <div className="table-container">
                            <table>
                                <thead>
                                    <tr><th>Camera</th><th>Latitude</th><th>Longitude</th><th style={{ textAlign: 'right' }}>Images</th></tr>
                                </thead>
                                <tbody>
                                    {cameras.map((c) => (
                                        <tr key={c.name}>
                                            <td style={{ fontWeight: 600 }}>{c.name}</td>
                                            <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{c.latitude?.toFixed(4) || '—'}</td>
                                            <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{c.longitude?.toFixed(4) || '—'}</td>
                                            <td style={{ textAlign: 'right', fontWeight: 600 }}>{fmt(c.image_count)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

/* ============================================================
   IMAGE BROWSER
   ============================================================ */
function ImageBrowser() {
    const [images, setImages] = useState<PaginatedResponse<ImageData> | null>(null);
    const [page, setPage] = useState(1);
    const [filterProcessed, setFilterProcessed] = useState<string>('all');
    const [filterAnimal, setFilterAnimal] = useState<string>('all');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function load() {
            setLoading(true);
            try {
                const params: any = { page, per_page: 48 };
                if (filterProcessed !== 'all') params.processed = filterProcessed === 'yes';
                if (filterAnimal !== 'all') params.has_animal = filterAnimal === 'yes';
                const data = await fetchImages(params);
                setImages(data);
            } catch (e: any) {
                setError(e.message);
            } finally {
                setLoading(false);
            }
        }
        load();
    }, [page, filterProcessed, filterAnimal]);

    return (
        <>
            <div className="page-header">
                <h2>Image Browser</h2>
                <p>Browse and filter camera trap images</p>
            </div>

            <div className="filters-bar">
                <select className="filter-select" value={filterProcessed} onChange={(e) => { setFilterProcessed(e.target.value); setPage(1); }}>
                    <option value="all">All Images</option>
                    <option value="yes">Processed</option>
                    <option value="no">Unprocessed</option>
                </select>
                <select className="filter-select" value={filterAnimal} onChange={(e) => { setFilterAnimal(e.target.value); setPage(1); }}>
                    <option value="all">All Results</option>
                    <option value="yes">Has Animal</option>
                    <option value="no">Empty</option>
                </select>
                {images && (
                    <span className="tag tag-muted">{fmt(images.total)} images</span>
                )}
            </div>

            {loading ? (
                <LoadingState />
            ) : error ? (
                <ErrorState message={error} />
            ) : !images || images.items.length === 0 ? (
                <div className="empty-state">
                    <div className="icon">📷</div>
                    <h3>No images found</h3>
                    <p>Import your dataset first using <code>python -m scripts.bulk_import</code></p>
                </div>
            ) : (
                <>
                    <div className="image-grid">
                        {images.items.map((img) => (
                            <div key={img.id} className="image-card">
                                <div className="image-thumb">
                                    {img.thumbnail_path ? (
                                        <img src={`http://localhost:8000/storage/${img.thumbnail_path}`} alt={img.filename} />
                                    ) : (
                                        '📷'
                                    )}
                                    {img.has_animal && (
                                        <div style={{
                                            position: 'absolute', top: 8, right: 8,
                                            background: 'rgba(16,185,129,0.9)', borderRadius: '6px',
                                            padding: '2px 6px', fontSize: '0.65rem', fontWeight: 700, color: 'white'
                                        }}>
                                            ANIMAL
                                        </div>
                                    )}
                                </div>
                                <div className="image-info">
                                    <div className="image-filename">{img.filename}</div>
                                    <div className="image-meta">
                                        {img.processed ? (
                                            <span className="tag tag-primary">Processed</span>
                                        ) : (
                                            <span className="tag tag-muted">Pending</span>
                                        )}
                                        {img.camera_id && <span className="tag tag-info">Cam {img.camera_id}</span>}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>

                    {images.pages > 1 && (
                        <div className="pagination">
                            <button className="page-btn" onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}>
                                ← Prev
                            </button>
                            <span className="page-info">Page {page} of {images.pages}</span>
                            <button className="page-btn" onClick={() => setPage(Math.min(images.pages, page + 1))} disabled={page === images.pages}>
                                Next →
                            </button>
                        </div>
                    )}
                </>
            )}
        </>
    );
}

/* ============================================================
   DETECTION VIEWER
   ============================================================ */
function DetectionViewer() {
    const [species, setSpecies] = useState<SpeciesCount[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function load() {
            try {
                const data = await fetchSpeciesCounts();
                setSpecies(data);
            } catch (e: any) {
                setError(e.message);
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    if (loading) return <LoadingState />;
    if (error) return <ErrorState message={error} />;

    const totalDetections = species.reduce((sum, s) => sum + s.count, 0);

    return (
        <>
            <div className="page-header">
                <h2>Detections</h2>
                <p>Species classification results from MegaDetector + AWC135</p>
            </div>

            {species.length === 0 ? (
                <div className="empty-state">
                    <div className="icon">🔍</div>
                    <h3>No detections yet</h3>
                    <p>Run the ML pipeline: <code>python -m scripts.run_pipeline</code></p>
                </div>
            ) : (
                <>
                    <div className="stats-grid" style={{ marginBottom: '2rem' }}>
                        <StatCard icon="🔍" value={fmt(totalDetections)} label="Total Detections" />
                        <StatCard icon="🏷️" value={fmt(species.length)} label="Species Found" />
                        <StatCard
                            icon="🐾"
                            value={fmt(species.find((s) => s.species.toLowerCase().includes('quoll'))?.count || 0)}
                            label="Quoll Detections"
                        />
                    </div>

                    <div className="card">
                        <div className="card-header"><h3>Species Distribution</h3></div>
                        <div className="card-body">
                            {species.map((s) => {
                                const pct = totalDetections > 0 ? (s.count / totalDetections) * 100 : 0;
                                const isQuoll = s.species.toLowerCase().includes('quoll');
                                return (
                                    <div key={s.species} style={{ marginBottom: '1rem' }}>
                                        <div style={{
                                            display: 'flex', justifyContent: 'space-between',
                                            fontSize: '0.85rem', marginBottom: '0.35rem'
                                        }}>
                                            <span style={{ fontWeight: isQuoll ? 700 : 500, color: isQuoll ? 'var(--accent)' : 'var(--text-primary)' }}>
                                                {isQuoll && '🐾 '}{s.species}
                                            </span>
                                            <span style={{ color: 'var(--text-muted)' }}>
                                                {fmt(s.count)} ({pct.toFixed(1)}%)
                                            </span>
                                        </div>
                                        <div className="progress-bar-bg">
                                            <div
                                                className="progress-bar-fill"
                                                style={{
                                                    width: `${pct}%`,
                                                    background: isQuoll
                                                        ? 'linear-gradient(90deg, var(--accent), var(--accent-dark))'
                                                        : 'linear-gradient(90deg, var(--primary), var(--primary-light))',
                                                }}
                                            />
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </>
            )}
        </>
    );
}

/* ============================================================
   INDIVIDUAL QUOLLS
   ============================================================ */
function Individuals() {
    const [individuals, setIndividuals] = useState<IndividualData[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function load() {
            try {
                const data = await fetchIndividuals();
                setIndividuals(data);
            } catch (e: any) {
                setError(e.message);
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    if (loading) return <LoadingState />;
    if (error) return <ErrorState message={error} />;

    return (
        <>
            <div className="page-header">
                <h2>Quoll Profiles</h2>
                <p>Known individual Spotted-tailed Quolls from ground-truth data</p>
            </div>

            {individuals.length === 0 ? (
                <div className="empty-state">
                    <div className="icon">🐾</div>
                    <h3>No individuals imported yet</h3>
                    <p>Run the bulk import to load CSV ground truth: <code>python -m scripts.bulk_import</code></p>
                </div>
            ) : (
                <>
                    <div className="stats-grid" style={{ marginBottom: '2rem' }}>
                        <StatCard icon="🐾" value={fmt(individuals.length)} label="Known Individuals" />
                        <StatCard
                            icon="👁️"
                            value={fmt(individuals.reduce((sum, i) => sum + i.total_sightings, 0))}
                            label="Total Sightings"
                        />
                    </div>

                    <div className="quoll-grid">
                        {individuals.map((ind) => (
                            <div key={ind.individual_id} className="quoll-card">
                                <div className="quoll-id">🐾 {ind.individual_id}</div>
                                <div className="quoll-species">{ind.species}</div>
                                <div className="quoll-stats">
                                    <div className="quoll-stat">
                                        <div className="label">Sightings</div>
                                        <div className="value">{ind.total_sightings}</div>
                                    </div>
                                    <div className="quoll-stat">
                                        <div className="label">First Seen</div>
                                        <div className="value">{ind.first_seen ? new Date(ind.first_seen).toLocaleDateString() : '—'}</div>
                                    </div>
                                    <div className="quoll-stat">
                                        <div className="label">Last Seen</div>
                                        <div className="value">{ind.last_seen ? new Date(ind.last_seen).toLocaleDateString() : '—'}</div>
                                    </div>
                                    <div className="quoll-stat">
                                        <div className="label">Active Period</div>
                                        <div className="value">
                                            {ind.first_seen && ind.last_seen
                                                ? `${Math.ceil((new Date(ind.last_seen).getTime() - new Date(ind.first_seen).getTime()) / (1000 * 60 * 60 * 24))}d`
                                                : '—'}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </>
            )}
        </>
    );
}

/* ============================================================
   SHARED COMPONENTS
   ============================================================ */
function StatCard({ icon, value, label }: { icon: string; value: string; label: string }) {
    return (
        <div className="stat-card">
            <div className="stat-icon">{icon}</div>
            <div className="stat-value">{value}</div>
            <div className="stat-label">{label}</div>
        </div>
    );
}

function LoadingState() {
    return (
        <div className="loading-container">
            <div className="spinner" />
            <span>Loading...</span>
        </div>
    );
}

function ErrorState({ message }: { message: string }) {
    return (
        <div className="empty-state">
            <div className="icon">⚠️</div>
            <h3>Connection Error</h3>
            <p>{message}</p>
            <p style={{ marginTop: '0.5rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                Make sure the backend is running: <code>uvicorn backend.app.main:app --reload</code>
            </p>
        </div>
    );
}

function fmt(n: number): string {
    return n.toLocaleString();
}

export default App;
