import { useState, useEffect, useRef, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation, useParams, Navigate } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import L from 'leaflet';
import { AuthProvider, useAuth } from './auth';
import {
    fetchStats, fetchImages, fetchIndividuals, fetchCollectionStats, fetchCameraStats,
    fetchSpeciesCounts, fetchReport, fetchDetectionDetail, fetchAnnotations,
    createAnnotation, uploadBatch, fetchJobStatus, fetchUsers, changeUserRole,
    fetchSystemMetrics, register, getExportUrl, getQuollExportUrl, getMetadataExportUrl,
    storageUrl,
    type DashboardStats, type ImageData, type IndividualData, type CollectionStat,
    type CameraStat, type SpeciesCount, type PaginatedResponse, type ReportData,
    type DetectionDetail, type AnnotationData, type JobStatus, type UserData,
} from './api';
import './index.css';

/* Fix Leaflet default icon paths */
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const CHART_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

function App() {
    return (
        <BrowserRouter>
            <AuthProvider>
                <AppShell />
            </AuthProvider>
        </BrowserRouter>
    );
}

function AppShell() {
    const { user, loading } = useAuth();
    if (loading) return <LoadingState />;
    return (
        <div className="app">
            <Sidebar />
            <main className="main-content">
                <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/images" element={<ImageBrowser />} />
                    <Route path="/detections" element={<DetectionViewer />} />
                    <Route path="/individuals" element={<Individuals />} />
                    <Route path="/upload" element={<RequireAuth><BatchUpload /></RequireAuth>} />
                    <Route path="/reports" element={<Reports />} />
                    <Route path="/review/:detectionId" element={<RequireAuth><ImageReview /></RequireAuth>} />
                    <Route path="/admin" element={<RequireAuth role="admin"><AdminPanel /></RequireAuth>} />
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="*" element={<Navigate to="/" />} />
                </Routes>
            </main>
        </div>
    );
}

function RequireAuth({ children, role }: { children: React.ReactNode; role?: string }) {
    const { user } = useAuth();
    if (!user) return <Navigate to="/login" />;
    if (role && user.role !== role) return <div className="empty-state"><h3>Access denied</h3><p>Requires {role} role</p></div>;
    return <>{children}</>;
}

/* ============================================================
   SIDEBAR
   ============================================================ */
function Sidebar() {
    const loc = useLocation();
    const { user, logout } = useAuth();
    const navItems = [
        { path: '/', icon: '📊', label: 'Dashboard' },
        { path: '/images', icon: '📷', label: 'Image Browser' },
        { path: '/detections', icon: '🔍', label: 'Detections' },
        { path: '/individuals', icon: '🐾', label: 'Quoll Profiles' },
        { path: '/upload', icon: '📤', label: 'Batch Upload' },
        { path: '/reports', icon: '📋', label: 'Reports' },
        ...(user?.role === 'admin' ? [{ path: '/admin', icon: '⚙️', label: 'Admin' }] : []),
    ];

    return (
        <aside className="sidebar">
            <div className="sidebar-logo">
                <h1>🌿 <span>Wildlife AI</span></h1>
                <div className="subtitle">Morton NP — Quoll ID</div>
            </div>
            <nav className="sidebar-nav">
                {navItems.map((item) => (
                    <Link key={item.path} to={item.path} className={`nav-item ${loc.pathname === item.path ? 'active' : ''}`}>
                        <span className="icon">{item.icon}</span><span>{item.label}</span>
                    </Link>
                ))}
            </nav>
            <div style={{ padding: '1rem 1.5rem', borderTop: '1px solid var(--border)' }}>
                {user ? (
                    <div style={{ fontSize: '0.75rem' }}>
                        <div style={{ color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>{user.email}</div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span className="tag tag-primary">{user.role}</span>
                            <button onClick={logout} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.7rem' }}>Logout</button>
                        </div>
                    </div>
                ) : (
                    <Link to="/login" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', fontSize: '0.8rem' }}>Sign In</Link>
                )}
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
        Promise.all([fetchStats(), fetchCollectionStats(), fetchCameraStats(), fetchSpeciesCounts()])
            .then(([s, c, cam, sp]) => { setStats(s); setCollections(c); setCameras(cam); setSpecies(sp); })
            .catch((e) => setError(e.message)).finally(() => setLoading(false));
    }, []);

    if (loading) return <LoadingState />;
    if (error) return <ErrorState message={error} />;
    if (!stats) return null;

    const camsWithCoords = cameras.filter((c) => c.latitude && c.longitude);

    return (
        <>
            <div className="page-header"><h2>Dashboard</h2><p>Morton National Park — Camera Trap Processing Overview</p></div>
            <div className="stats-grid">
                <StatCard icon="📷" value={fmt(stats.total_images)} label="Total Images" />
                <StatCard icon="✅" value={fmt(stats.processed_images)} label="Processed" />
                <StatCard icon="⏳" value={fmt(stats.unprocessed_images)} label="Unprocessed" />
                <StatCard icon="🐾" value={fmt(stats.quoll_detections)} label="Quoll Detections" />
                <StatCard icon="🆔" value={fmt(stats.total_individuals)} label="Known Quolls" />
                <StatCard icon="📹" value={fmt(stats.total_cameras)} label="Camera Traps" />
                <StatCard icon="🔍" value={fmt(stats.total_detections)} label="Total Detections" />
                <StatCard icon="📝" value={fmt(stats.pending_review)} label="Pending Review" />
            </div>

            <div className="card" style={{ marginBottom: '1.5rem' }}>
                <div className="card-header"><h3>Processing Progress</h3><span style={{ color: 'var(--primary)', fontWeight: 700, fontSize: '0.9rem' }}>{stats.processing_percent.toFixed(1)}%</span></div>
                <div className="card-body">
                    <div className="progress-bar-bg"><div className="progress-bar-fill" style={{ width: `${stats.processing_percent}%` }} /></div>
                    <div className="progress-label"><span>{fmt(stats.processed_images)} processed</span><span>{fmt(stats.unprocessed_images)} remaining</span></div>
                </div>
            </div>

            {camsWithCoords.length > 0 && (
                <div className="card" style={{ marginBottom: '1.5rem' }}>
                    <div className="card-header"><h3>Camera Trap Map</h3></div>
                    <div className="card-body" style={{ padding: 0, height: 400 }}>
                        <MapContainer center={[camsWithCoords[0].latitude!, camsWithCoords[0].longitude!]} zoom={12} style={{ height: '100%', width: '100%', borderRadius: '0 0 12px 12px' }}>
                            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="OSM" />
                            {camsWithCoords.map((c) => (
                                <Marker key={c.id} position={[c.latitude!, c.longitude!]}>
                                    <Popup>
                                        <strong>{c.name}</strong><br />
                                        Images: {c.image_count}<br />
                                        Detections: {c.detection_count}<br />
                                        {c.last_upload && <>Last: {new Date(c.last_upload).toLocaleDateString()}</>}
                                    </Popup>
                                </Marker>
                            ))}
                        </MapContainer>
                    </div>
                </div>
            )}

            <div className="chart-grid">
                <div className="card">
                    <div className="card-header"><h3>Collections</h3></div>
                    <div className="card-body">
                        {collections.length === 0 ? <EmptyMsg text="No collections yet" /> : (
                            <div className="table-container"><table><thead><tr><th>Collection</th><th style={{ textAlign: 'right' }}>Images</th></tr></thead><tbody>
                                {collections.map((c) => <tr key={c.name}><td>{c.name}</td><td style={{ textAlign: 'right', fontWeight: 600 }}>{fmt(c.image_count)}</td></tr>)}
                            </tbody></table></div>
                        )}
                    </div>
                </div>
                <div className="card">
                    <div className="card-header"><h3>Species Detections</h3></div>
                    <div className="card-body">
                        {species.length === 0 ? <EmptyMsg text="No detections yet" /> : (
                            <div className="table-container"><table><thead><tr><th>Species</th><th style={{ textAlign: 'right' }}>Count</th></tr></thead><tbody>
                                {species.map((s) => <tr key={s.species}><td>{s.species.toLowerCase().includes('quoll') && '🐾 '}{s.species}</td><td style={{ textAlign: 'right', fontWeight: 600 }}>{fmt(s.count)}</td></tr>)}
                            </tbody></table></div>
                        )}
                    </div>
                </div>
            </div>
        </>
    );
}

/* ============================================================
   IMAGE BROWSER
   ============================================================ */
function ImageBrowser() {
    const [images, setImages] = useState<PaginatedResponse<ImageData> | null>(null);
    const [page, setPage] = useState(1);
    const [filterProcessed, setFilterProcessed] = useState('all');
    const [filterAnimal, setFilterAnimal] = useState('all');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setLoading(true);
        const params: any = { page, per_page: 48 };
        if (filterProcessed !== 'all') params.processed = filterProcessed === 'yes';
        if (filterAnimal !== 'all') params.has_animal = filterAnimal === 'yes';
        fetchImages(params).then(setImages).catch((e) => setError(e.message)).finally(() => setLoading(false));
    }, [page, filterProcessed, filterAnimal]);

    return (
        <>
            <div className="page-header"><h2>Image Browser</h2><p>Browse and filter camera trap images</p></div>
            <div className="filters-bar">
                <select className="filter-select" value={filterProcessed} onChange={(e) => { setFilterProcessed(e.target.value); setPage(1); }}>
                    <option value="all">All Images</option><option value="yes">Processed</option><option value="no">Unprocessed</option>
                </select>
                <select className="filter-select" value={filterAnimal} onChange={(e) => { setFilterAnimal(e.target.value); setPage(1); }}>
                    <option value="all">All Results</option><option value="yes">Has Animal</option><option value="no">Empty</option>
                </select>
                {images && <span className="tag tag-muted">{fmt(images.total)} images</span>}
            </div>
            {loading ? <LoadingState /> : error ? <ErrorState message={error} /> : !images || images.items.length === 0 ? (
                <div className="empty-state"><div className="icon">📷</div><h3>No images found</h3></div>
            ) : (
                <>
                    <div className="image-grid">
                        {images.items.map((img) => (
                            <div key={img.id} className="image-card">
                                <div className="image-thumb">
                                    {img.thumbnail_path ? <img src={storageUrl(img.thumbnail_path)} alt={img.filename} /> : '📷'}
                                    {img.has_animal && <div style={{ position: 'absolute', top: 8, right: 8, background: 'rgba(16,185,129,0.9)', borderRadius: '6px', padding: '2px 6px', fontSize: '0.65rem', fontWeight: 700, color: 'white' }}>ANIMAL</div>}
                                </div>
                                <div className="image-info">
                                    <div className="image-filename">{img.filename}</div>
                                    <div className="image-meta">
                                        {img.processed ? <span className="tag tag-primary">Processed</span> : <span className="tag tag-muted">Pending</span>}
                                        {img.camera_id && <span className="tag tag-info">Cam {img.camera_id}</span>}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                    {images.pages > 1 && (
                        <div className="pagination">
                            <button className="page-btn" onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}>Prev</button>
                            <span className="page-info">Page {page} of {images.pages}</span>
                            <button className="page-btn" onClick={() => setPage(Math.min(images.pages, page + 1))} disabled={page === images.pages}>Next</button>
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

    useEffect(() => { fetchSpeciesCounts().then(setSpecies).catch((e) => setError(e.message)).finally(() => setLoading(false)); }, []);
    if (loading) return <LoadingState />;
    if (error) return <ErrorState message={error} />;
    const total = species.reduce((s, x) => s + x.count, 0);

    return (
        <>
            <div className="page-header"><h2>Detections</h2><p>Species classification results from MegaDetector + AWC135</p></div>
            {species.length === 0 ? <div className="empty-state"><div className="icon">🔍</div><h3>No detections yet</h3></div> : (
                <>
                    <div className="stats-grid" style={{ marginBottom: '2rem' }}>
                        <StatCard icon="🔍" value={fmt(total)} label="Total Detections" />
                        <StatCard icon="🏷️" value={fmt(species.length)} label="Species Found" />
                        <StatCard icon="🐾" value={fmt(species.find((s) => s.species.toLowerCase().includes('quoll'))?.count || 0)} label="Quoll Detections" />
                    </div>
                    <div className="card">
                        <div className="card-header"><h3>Species Distribution</h3></div>
                        <div className="card-body">
                            {species.map((s) => {
                                const pct = total > 0 ? (s.count / total) * 100 : 0;
                                const isQ = s.species.toLowerCase().includes('quoll');
                                return (
                                    <div key={s.species} style={{ marginBottom: '1rem' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.35rem' }}>
                                            <span style={{ fontWeight: isQ ? 700 : 500, color: isQ ? 'var(--accent)' : 'var(--text-primary)' }}>{isQ && '🐾 '}{s.species}</span>
                                            <span style={{ color: 'var(--text-muted)' }}>{fmt(s.count)} ({pct.toFixed(1)}%)</span>
                                        </div>
                                        <div className="progress-bar-bg"><div className="progress-bar-fill" style={{ width: `${pct}%`, background: isQ ? 'linear-gradient(90deg,var(--accent),var(--accent-dark))' : undefined }} /></div>
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

    useEffect(() => { fetchIndividuals().then(setIndividuals).catch((e) => setError(e.message)).finally(() => setLoading(false)); }, []);
    if (loading) return <LoadingState />;
    if (error) return <ErrorState message={error} />;

    return (
        <>
            <div className="page-header"><h2>Quoll Profiles</h2><p>Known individual Spotted-tailed Quolls</p></div>
            {individuals.length === 0 ? <div className="empty-state"><div className="icon">🐾</div><h3>No individuals imported yet</h3></div> : (
                <>
                    <div className="stats-grid" style={{ marginBottom: '2rem' }}>
                        <StatCard icon="🐾" value={fmt(individuals.length)} label="Known Individuals" />
                        <StatCard icon="👁️" value={fmt(individuals.reduce((s, i) => s + i.total_sightings, 0))} label="Total Sightings" />
                    </div>
                    <div className="quoll-grid">
                        {individuals.map((ind) => (
                            <div key={ind.individual_id} className="quoll-card">
                                <div className="quoll-id">🐾 {ind.individual_id}</div>
                                <div className="quoll-species">{ind.species}</div>
                                <div className="quoll-stats">
                                    <div className="quoll-stat"><div className="label">Sightings</div><div className="value">{ind.total_sightings}</div></div>
                                    <div className="quoll-stat"><div className="label">First Seen</div><div className="value">{ind.first_seen ? new Date(ind.first_seen).toLocaleDateString() : '—'}</div></div>
                                    <div className="quoll-stat"><div className="label">Last Seen</div><div className="value">{ind.last_seen ? new Date(ind.last_seen).toLocaleDateString() : '—'}</div></div>
                                    <div className="quoll-stat"><div className="label">Active</div><div className="value">{ind.first_seen && ind.last_seen ? `${Math.ceil((new Date(ind.last_seen).getTime() - new Date(ind.first_seen).getTime()) / 86400000)}d` : '—'}</div></div>
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
   BATCH UPLOAD
   ============================================================ */
function BatchUpload() {
    const [job, setJob] = useState<JobStatus | null>(null);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const fileRef = useRef<HTMLInputElement>(null);

    const handleUpload = async () => {
        const files = fileRef.current?.files;
        if (!files || files.length === 0) return;
        setUploading(true); setError(null);
        try {
            const res = await uploadBatch(files);
            pollJob(res.job_id);
        } catch (e: any) { setError(e.message); setUploading(false); }
    };

    const pollJob = useCallback(async (jobId: number) => {
        try {
            const s = await fetchJobStatus(jobId);
            setJob(s); setUploading(false);
            if (s.status === 'queued' || s.status === 'processing') {
                setTimeout(() => pollJob(jobId), 2000);
            }
        } catch { setUploading(false); }
    }, []);

    return (
        <>
            <div className="page-header"><h2>Batch Upload</h2><p>Upload camera trap images for ML processing</p></div>
            <div className="card" style={{ marginBottom: '1.5rem' }}>
                <div className="card-body">
                    <input ref={fileRef} type="file" multiple accept=".jpg,.jpeg,.png" style={{ marginBottom: '1rem' }} />
                    <br />
                    <button className="btn btn-primary" onClick={handleUpload} disabled={uploading}>{uploading ? 'Uploading...' : 'Upload & Process'}</button>
                    {error && <p style={{ color: 'var(--danger)', marginTop: '0.5rem' }}>{error}</p>}
                </div>
            </div>
            {job && (
                <div className="card">
                    <div className="card-header"><h3>Job #{job.id} — {job.status}</h3></div>
                    <div className="card-body">
                        <div className="progress-bar-bg"><div className="progress-bar-fill" style={{ width: `${job.percent}%` }} /></div>
                        <div className="progress-label"><span>{job.processed_images} / {job.total_images} processed</span><span>{job.percent.toFixed(1)}%</span></div>
                        {job.failed_images > 0 && <p style={{ color: 'var(--danger)', marginTop: '0.5rem' }}>{job.failed_images} failed</p>}
                    </div>
                </div>
            )}
        </>
    );
}

/* ============================================================
   REPORTS
   ============================================================ */
function Reports() {
    const [report, setReport] = useState<ReportData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => { fetchReport().then(setReport).catch((e) => setError(e.message)).finally(() => setLoading(false)); }, []);
    if (loading) return <LoadingState />;
    if (error) return <ErrorState message={error} />;
    if (!report) return null;

    return (
        <>
            <div className="page-header"><h2>Reports</h2><p>Batch processing results and data visualizations</p></div>
            <div className="stats-grid">
                <StatCard icon="📷" value={fmt(report.total_images)} label="Total Images" />
                <StatCard icon="✅" value={fmt(report.processed_images)} label="Processed" />
                <StatCard icon="🔲" value={fmt(report.empty_images)} label="Empty" />
                <StatCard icon="🔍" value={fmt(report.total_detections)} label="Detections" />
                <StatCard icon="🏷️" value={fmt(report.total_species)} label="Species" />
                <StatCard icon="🐾" value={fmt(report.quoll_detections)} label="Quolls" />
            </div>

            {report.mean_detection_confidence != null && (
                <div className="card" style={{ marginBottom: '1.5rem' }}>
                    <div className="card-header"><h3>Confidence Statistics</h3></div>
                    <div className="card-body" style={{ display: 'flex', gap: '2rem' }}>
                        <div>Detection avg: <strong>{report.mean_detection_confidence.toFixed(3)}</strong></div>
                        <div>Classification avg: <strong>{(report.mean_classification_confidence ?? 0).toFixed(3)}</strong></div>
                    </div>
                </div>
            )}

            <div className="chart-grid">
                {report.species_distribution.length > 0 && (
                    <div className="card">
                        <div className="card-header"><h3>Species Distribution</h3></div>
                        <div className="card-body" style={{ height: 300 }}>
                            <ResponsiveContainer>
                                <PieChart>
                                    <Pie data={report.species_distribution} dataKey="count" nameKey="species" cx="50%" cy="50%" outerRadius={100} label={({ species, percent }) => `${species.split('|').pop()?.trim()} ${(percent * 100).toFixed(0)}%`}>
                                        {report.species_distribution.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                                    </Pie>
                                    <Tooltip />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                )}
                {report.hourly_activity.length > 0 && (
                    <div className="card">
                        <div className="card-header"><h3>Hourly Activity</h3></div>
                        <div className="card-body" style={{ height: 300 }}>
                            <ResponsiveContainer>
                                <BarChart data={report.hourly_activity}>
                                    <XAxis dataKey="hour" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                                    <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} />
                                    <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid rgba(255,255,255,0.1)' }} />
                                    <Bar dataKey="detections" fill="#10b981" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                )}
                {report.camera_counts.length > 0 && (
                    <div className="card">
                        <div className="card-header"><h3>Detections by Camera</h3></div>
                        <div className="card-body" style={{ height: 300 }}>
                            <ResponsiveContainer>
                                <BarChart data={report.camera_counts} layout="vertical">
                                    <XAxis type="number" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                                    <YAxis dataKey="camera" type="category" tick={{ fill: '#9ca3af', fontSize: 11 }} width={50} />
                                    <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid rgba(255,255,255,0.1)' }} />
                                    <Bar dataKey="detections" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                )}
            </div>

            <div className="card">
                <div className="card-header"><h3>Export</h3></div>
                <div className="card-body" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                    <a href={getExportUrl('csv')} className="btn btn-outline" download>Report CSV</a>
                    <a href={getExportUrl('json')} className="btn btn-outline" download>Report JSON</a>
                    <a href={getQuollExportUrl('csv')} className="btn btn-primary" download>Quoll Detections CSV</a>
                    <a href={getMetadataExportUrl('csv')} className="btn btn-outline" download>Full Metadata CSV</a>
                </div>
            </div>
        </>
    );
}

/* ============================================================
   IMAGE REVIEW (annotation workflow)
   ============================================================ */
function ImageReview() {
    const params = useParams();
    const id = parseInt(params.detectionId || '0');
    const [det, setDet] = useState<DetectionDetail | null>(null);
    const [anns, setAnns] = useState<AnnotationData[]>([]);
    const [form, setForm] = useState({ is_correct: true, corrected_species: '', notes: '', individual_id: '', flag_for_retraining: false });
    const [saving, setSaving] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!id) return;
        Promise.all([fetchDetectionDetail(id), fetchAnnotations(id)])
            .then(([d, a]) => { setDet(d); setAnns(a); }).finally(() => setLoading(false));
    }, [id]);

    const submit = async () => {
        if (!det) return;
        setSaving(true);
        try {
            const ann = await createAnnotation({
                detection_id: det.id,
                is_correct: form.is_correct,
                corrected_species: form.corrected_species || undefined,
                notes: form.notes || undefined,
                individual_id: form.individual_id || undefined,
                flag_for_retraining: form.flag_for_retraining,
            });
            setAnns([ann, ...anns]);
            setForm({ is_correct: true, corrected_species: '', notes: '', individual_id: '', flag_for_retraining: false });
        } catch { }
        setSaving(false);
    };

    if (loading) return <LoadingState />;
    if (!det) return <div className="empty-state"><h3>Detection not found</h3></div>;

    return (
        <>
            <div className="page-header"><h2>Review Detection #{det.id}</h2><p>{det.image?.filename} — {det.species}</p></div>
            <div className="chart-grid">
                <div className="card">
                    <div className="card-header"><h3>Image</h3></div>
                    <div className="card-body" style={{ textAlign: 'center' }}>
                        {det.crop_path && <img src={storageUrl(det.crop_path)} alt="crop" style={{ maxWidth: '100%', borderRadius: 8 }} />}
                        <div style={{ marginTop: '1rem', fontSize: '0.85rem' }}>
                            <div><strong>Species:</strong> {det.species || 'Unknown'}</div>
                            <div><strong>Confidence:</strong> {det.classification_confidence?.toFixed(3)}</div>
                            <div><strong>Detection conf:</strong> {det.detection_confidence.toFixed(3)}</div>
                            <div><strong>Model:</strong> {det.model_version}</div>
                            <div><strong>Camera:</strong> {det.camera?.name || '—'}</div>
                            <div><strong>Timestamp:</strong> {det.image?.captured_at || '—'}</div>
                            <div><strong>Bbox:</strong> [{det.bbox_x.toFixed(3)}, {det.bbox_y.toFixed(3)}, {det.bbox_w.toFixed(3)}, {det.bbox_h.toFixed(3)}]</div>
                        </div>
                    </div>
                </div>
                <div className="card">
                    <div className="card-header"><h3>Annotate</h3></div>
                    <div className="card-body">
                        <div style={{ marginBottom: '1rem' }}>
                            <label style={{ fontSize: '0.8rem', display: 'block', marginBottom: '0.25rem' }}>ML prediction correct?</label>
                            <select className="filter-select" value={String(form.is_correct)} onChange={(e) => setForm({ ...form, is_correct: e.target.value === 'true' })}>
                                <option value="true">Yes, correct</option><option value="false">No, incorrect</option>
                            </select>
                        </div>
                        {!form.is_correct && (
                            <div style={{ marginBottom: '1rem' }}>
                                <label style={{ fontSize: '0.8rem', display: 'block', marginBottom: '0.25rem' }}>Corrected species</label>
                                <input className="filter-select" style={{ width: '100%' }} value={form.corrected_species} onChange={(e) => setForm({ ...form, corrected_species: e.target.value })} placeholder="e.g. Trichosurus sp | Brushtail Possum sp" />
                            </div>
                        )}
                        <div style={{ marginBottom: '1rem' }}>
                            <label style={{ fontSize: '0.8rem', display: 'block', marginBottom: '0.25rem' }}>Individual ID (e.g. 02Q2)</label>
                            <input className="filter-select" style={{ width: '100%' }} value={form.individual_id} onChange={(e) => setForm({ ...form, individual_id: e.target.value })} />
                        </div>
                        <div style={{ marginBottom: '1rem' }}>
                            <label style={{ fontSize: '0.8rem', display: 'block', marginBottom: '0.25rem' }}>Notes</label>
                            <textarea className="filter-select" style={{ width: '100%', minHeight: 60, resize: 'vertical' }} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
                        </div>
                        <div style={{ marginBottom: '1rem' }}>
                            <label style={{ fontSize: '0.8rem', cursor: 'pointer' }}>
                                <input type="checkbox" checked={form.flag_for_retraining} onChange={(e) => setForm({ ...form, flag_for_retraining: e.target.checked })} style={{ marginRight: '0.5rem' }} />
                                Flag for retraining dataset
                            </label>
                        </div>
                        <button className="btn btn-primary" onClick={submit} disabled={saving}>{saving ? 'Saving...' : 'Save Annotation'}</button>

                        {anns.length > 0 && (
                            <div style={{ marginTop: '1.5rem' }}>
                                <h4 style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>Previous Annotations</h4>
                                {anns.map((a) => (
                                    <div key={a.id} style={{ background: 'var(--bg-primary)', borderRadius: 8, padding: '0.75rem', marginBottom: '0.5rem', fontSize: '0.8rem' }}>
                                        <div>{a.is_correct ? '✅ Correct' : '❌ Incorrect'}{a.corrected_species && ` → ${a.corrected_species}`}</div>
                                        {a.notes && <div style={{ color: 'var(--text-muted)' }}>{a.notes}</div>}
                                        <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>{a.annotator} — {a.created_at}</div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </>
    );
}

/* ============================================================
   ADMIN PANEL
   ============================================================ */
function AdminPanel() {
    const [users, setUsers] = useState<UserData[]>([]);
    const [metrics, setMetrics] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([fetchUsers(), fetchSystemMetrics()])
            .then(([u, m]) => { setUsers(u); setMetrics(m); })
            .catch(() => {}).finally(() => setLoading(false));
    }, []);

    const onRoleChange = async (userId: number, role: string) => {
        const updated = await changeUserRole(userId, role);
        setUsers(users.map((u) => (u.id === userId ? updated : u)));
    };

    if (loading) return <LoadingState />;

    return (
        <>
            <div className="page-header"><h2>Admin Panel</h2><p>System management and user administration</p></div>
            {metrics && (
                <div className="stats-grid">
                    <StatCard icon="📷" value={fmt(metrics.total_images)} label="Images" />
                    <StatCard icon="🔍" value={fmt(metrics.total_detections)} label="Detections" />
                    <StatCard icon="👤" value={fmt(metrics.total_users)} label="Users" />
                    <StatCard icon="⏳" value={fmt(metrics.pending_jobs)} label="Pending Jobs" />
                    <StatCard icon="💾" value={`${metrics.db_size_mb} MB`} label="DB Size" />
                    <StatCard icon="📁" value={`${metrics.storage_size_mb} MB`} label="Storage" />
                </div>
            )}
            <div className="card">
                <div className="card-header"><h3>Users</h3></div>
                <div className="card-body">
                    <div className="table-container">
                        <table>
                            <thead><tr><th>Email</th><th>Name</th><th>Role</th><th>Active</th><th>Action</th></tr></thead>
                            <tbody>
                                {users.map((u) => (
                                    <tr key={u.id}>
                                        <td>{u.email}</td>
                                        <td>{u.full_name || '—'}</td>
                                        <td><span className="tag tag-primary">{u.role}</span></td>
                                        <td>{u.is_active ? '✅' : '❌'}</td>
                                        <td>
                                            <select className="filter-select" value={u.role} onChange={(e) => onRoleChange(u.id, e.target.value)} style={{ fontSize: '0.75rem' }}>
                                                <option value="admin">admin</option><option value="researcher">researcher</option><option value="reviewer">reviewer</option>
                                            </select>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div className="card" style={{ marginTop: '1.5rem' }}>
                <div className="card-header"><h3>Dataset Exports</h3></div>
                <div className="card-body" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                    <a href={getQuollExportUrl('csv')} className="btn btn-primary" download>Export Quoll Detections</a>
                    <a href={getMetadataExportUrl('csv')} className="btn btn-outline" download>Export Full Metadata</a>
                    <a href={getExportUrl('json')} className="btn btn-outline" download>Export Report JSON</a>
                </div>
            </div>
        </>
    );
}

/* ============================================================
   LOGIN PAGE
   ============================================================ */
function LoginPage() {
    const { user, login } = useAuth();
    const [tab, setTab] = useState<'login' | 'register'>('login');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('');
    const [role, setRole] = useState('reviewer');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    if (user) return <Navigate to="/" />;

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault(); setError(''); setLoading(true);
        try { await login(email, password); } catch { setError('Invalid credentials'); }
        setLoading(false);
    };

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault(); setError(''); setLoading(true);
        try {
            await register(email, password, fullName, role);
            await login(email, password);
        } catch (err: any) { setError(err.message); }
        setLoading(false);
    };

    return (
        <div style={{ maxWidth: 400, margin: '4rem auto' }}>
            <div className="page-header" style={{ textAlign: 'center' }}><h2>🌿 Wildlife AI Platform</h2><p>Sign in to continue</p></div>
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
                <button className={`btn ${tab === 'login' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setTab('login')} style={{ flex: 1 }}>Login</button>
                <button className={`btn ${tab === 'register' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setTab('register')} style={{ flex: 1 }}>Register</button>
            </div>
            <div className="card">
                <div className="card-body">
                    <form onSubmit={tab === 'login' ? handleLogin : handleRegister}>
                        {tab === 'register' && (
                            <div style={{ marginBottom: '1rem' }}>
                                <label style={{ fontSize: '0.8rem', display: 'block', marginBottom: '0.25rem' }}>Full Name</label>
                                <input className="filter-select" style={{ width: '100%' }} value={fullName} onChange={(e) => setFullName(e.target.value)} />
                            </div>
                        )}
                        <div style={{ marginBottom: '1rem' }}>
                            <label style={{ fontSize: '0.8rem', display: 'block', marginBottom: '0.25rem' }}>Email</label>
                            <input className="filter-select" style={{ width: '100%' }} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
                        </div>
                        <div style={{ marginBottom: '1rem' }}>
                            <label style={{ fontSize: '0.8rem', display: 'block', marginBottom: '0.25rem' }}>Password</label>
                            <input className="filter-select" style={{ width: '100%' }} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
                        </div>
                        {tab === 'register' && (
                            <div style={{ marginBottom: '1rem' }}>
                                <label style={{ fontSize: '0.8rem', display: 'block', marginBottom: '0.25rem' }}>Role</label>
                                <select className="filter-select" value={role} onChange={(e) => setRole(e.target.value)}>
                                    <option value="reviewer">Reviewer</option><option value="researcher">Researcher</option><option value="admin">Admin</option>
                                </select>
                            </div>
                        )}
                        {error && <p style={{ color: 'var(--danger)', fontSize: '0.85rem', marginBottom: '0.5rem' }}>{error}</p>}
                        <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: '100%', justifyContent: 'center' }}>
                            {loading ? 'Please wait...' : tab === 'login' ? 'Sign In' : 'Create Account'}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}

/* ============================================================
   SHARED COMPONENTS
   ============================================================ */
function StatCard({ icon, value, label }: { icon: string; value: string; label: string }) {
    return <div className="stat-card"><div className="stat-icon">{icon}</div><div className="stat-value">{value}</div><div className="stat-label">{label}</div></div>;
}

function LoadingState() {
    return <div className="loading-container"><div className="spinner" /><span>Loading...</span></div>;
}

function ErrorState({ message }: { message: string }) {
    return <div className="empty-state"><div className="icon">⚠️</div><h3>Connection Error</h3><p>{message}</p></div>;
}

function EmptyMsg({ text }: { text: string }) {
    return <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '2rem' }}>{text}</div>;
}

function fmt(n: number): string {
    return n.toLocaleString();
}

export default App;
