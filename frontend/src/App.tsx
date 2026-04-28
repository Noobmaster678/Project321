import { useState, useEffect, useRef, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation, useParams, Navigate } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from 'recharts';
import L from 'leaflet';
import { AuthProvider, useAuth } from './auth';
import {
    fetchStats, fetchImages, fetchIndividuals, fetchCollectionStats, fetchCameraStats,
    fetchSpeciesCounts, fetchReport, fetchDetectionDetail, fetchAnnotations, fetchDetections,
    createAnnotation, uploadBatch, fetchJobStatus, fetchUsers, changeUserRole,
    fetchSystemMetrics, register, getExportUrl, getQuollExportUrl, getMetadataExportUrl, fetchImagesBySpecies, fetchImageDetail,
    storageUrl, createMissedDetection, fetchReviewQueue, fetchIndividualGallery, fetchReidInfo, createIndividual,
    type DashboardStats, type ImageData, type IndividualData, type CollectionStat,
    type CameraStat, type SpeciesCount, type PaginatedResponse, type ReportData,
    type DetectionDetail, type AnnotationData, type JobStatus, type UserData, type Detection,
    type ReviewQueueCounts, type IndividualGalleryItem,
} from './api';
import './index.css';
import AdminPage from './AdminPage';

/* Fix Leaflet default icon paths */
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const CHART_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

const WT_GREEN = '#2e7d32';

const SPOTTED_QUOLL_OVERVIEW =
    'The spotted-tailed quoll (Dasyurus maculatus) is mainland Australia’s largest native marsupial carnivore. ' +
    'It occupies forest and woodland habitats, is largely nocturnal, and is listed as vulnerable in parts of its range. ' +
    'Camera traps help monitor individuals using natural spot patterns and repeated captures across sites.';

/** Align with SpeciesExplorer: URL slug decodes to e.g. "dasyurus sp | quoll sp" while DB may say "Spotted-tailed Quoll". */
function individualMatchesSpeciesPage(ind: IndividualData, speciesKeyDecoded: string): boolean {
    const d = speciesKeyDecoded.toLowerCase().trim();
    const sp = ind.species.toLowerCase();
    if (!d) return true;
    if (sp.includes(d) || d.includes(sp)) return true;
    if (/\bquoll\b/.test(d) && /\bquoll\b/.test(sp)) return true;
    if (d.includes('dasyurus') && (sp.includes('quoll') || sp.includes('dasyurus'))) return true;
    return false;
}

/** Show Camera / Filename instead of just filename to disambiguate Reconyx images */
function displayImageName(img: { filename: string; file_path: string }): string {
    if (!img.file_path) return img.filename;
    const parts = img.file_path.replace(/\\/g, '/').split('/');
    if (parts.length >= 3) return parts.slice(-2).join(' / ');
    if (parts.length === 2) return parts.join(' / ');
    return img.filename;
}

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
            <HomeHeader />
            <main className="main-content">
                <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/images" element={<ImageBrowser />} />
                    <Route path="/detections" element={<DetectionViewer />} />
                    <Route path="/individuals" element={<SpeciesExplorer />} />
                    <Route path="/individuals/species/:speciesKey" element={<SpeciesDetail />} />
                    <Route path="/individuals/species/:speciesKey/images" element={<SpeciesImages />} />
                    <Route path="/individuals/species/:speciesKey/individuals" element={<SpeciesByIndividual />} />
                    <Route path="/individuals/species/:speciesKey/individuals/:individualId" element={<IndividualImages />} />
                    <Route path="/upload" element={<RequireAuth><BatchUpload /></RequireAuth>} />
                    <Route path="/reports" element={<Reports />} />
                    <Route path="/pending-review" element={<RequireAuth><PendingReviewPage /></RequireAuth>} />
                    <Route path="/help" element={<HelpPage />} />
                    <Route path="/review/:detectionId" element={<RequireAuth><ImageReview /></RequireAuth>} />
                    <Route path="/review-empty/:imageId" element={<RequireAuth><ReviewEmptyImage /></RequireAuth>} />
                    <Route path="/review-image/:imageId" element={<RequireAuth><ReviewImage /></RequireAuth>} />
                    <Route path="/admin" element={<RequireAuth role="admin"><AdminPanel /></RequireAuth>} />
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="*" element={<Navigate to="/" />} />
                </Routes>
            </main>
            <Footer />
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
   HEADER (WildlifeTracker approved design)
   ============================================================ */
function HomeHeader() {
    const loc = useLocation();
    const { user, logout } = useAuth();
    const navItems = [
        { path: '/', label: 'Home' },
        { path: '/upload', label: 'Upload' },
        { path: '/individuals', label: 'Profiles' },
        { path: '/pending-review', label: 'Pending Review' },
        { path: '/reports', label: 'Reports' },
        { path: '/help', label: 'Help' },
        ...(user?.role === 'admin' ? [{ path: '/admin', label: 'Admin' } as const] : []),
    ];

    return (
        <header className="site-header">
            <Link to="/" className="logo">
                <LeafLogo />
                <span>WildlifeTracker</span>
            </Link>
            <nav className="nav-center">
                {navItems.map((item) => (
                    <Link
                        key={item.path}
                        to={item.path}
                        className={`nav-link ${loc.pathname === item.path || (item.path === '/pending-review' && loc.pathname.startsWith('/review')) || (item.path === '/admin' && loc.pathname.startsWith('/admin')) ? 'active' : ''}`}
                    >
                        {item.label}
                    </Link>
                ))}
            </nav>
            <div className="nav-icons">
                <button type="button" className="nav-icon-btn" aria-label="Notifications">🔔</button>
                <button type="button" className="nav-icon-btn" aria-label="Help">❓</button>
                {user ? (
                    <button
                        type="button"
                        className="nav-icon-btn"
                        onClick={logout}
                        aria-label="User"
                        title={user.email}
                    >
                        👤
                    </button>
                ) : (
                    <Link to="/login" className="nav-icon-btn" aria-label="Sign in">👤</Link>
                )}
            </div>
        </header>
    );
}

function LeafLogo() {
    return (
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden>
            <path d="M17 8C8 10 5.9 16.17 3.82 21.34L5.71 22L6.66 19.7C7.14 18.66 7.5 17.59 7.77 16.5C8.5 18 9.5 19.5 10.5 20.5C11.5 21.5 13 22 15 22C19 22 22 19 22 15C22 12 20.5 9.5 18 8C17 8 17 8 17 8Z" />
        </svg>
    );
}

/* ============================================================
   FOOTER (WildlifeTracker approved design)
   ============================================================ */
function Footer() {
    return (
        <footer className="site-footer">
            <div className="footer-inner">
                <div className="footer-brand">
                    <Link to="/" className="logo"><LeafLogo /><span>WildlifeTracker</span></Link>
                    <p className="footer-tagline">Advanced wildlife monitoring and conservation technology</p>
                </div>
                <div className="footer-col">
                    <h4>Features</h4>
                    <Link to="/detections">AI Recognition</Link>
                    <Link to="/individuals">Movement Tracking</Link>
                    <Link to="/reports">Data Analytics</Link>
                </div>
                <div className="footer-col">
                    <h4>Support</h4>
                    <a href="#docs">Documentation</a>
                    <Link to="/help">Help Center</Link>
                    <a href="#contact">Contact Us</a>
                </div>
                <div className="footer-col">
                    <h4>Connect</h4>
                    <div className="footer-connect">
                        <a href="#twitter" aria-label="Twitter">𝕏</a>
                        <a href="#youtube" aria-label="YouTube">▶</a>
                        <a href="#linkedin" aria-label="LinkedIn">in</a>
                    </div>
                </div>
            </div>
            <div className="footer-bottom">© 2025 WildlifeTracker. All rights reserved.</div>
        </footer>
    );
}

/* ============================================================
   HELP (placeholder)
   ============================================================ */
function HelpPage() {
    return (
        <div className="page-header">
            <h2>Help</h2>
            <p>Documentation and support — coming soon.</p>
        </div>
    );
}

/* ============================================================
   PENDING REVIEW (design: metrics, category cards, review list)
   ============================================================ */
function PendingReviewPage() {
    const [queue, setQueue] = useState<ReviewQueueCounts | null>(null);
    const [cameras, setCameras] = useState<CameraStat[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [filter, setFilter] = useState<string | null>(null);
    const [filterDetections, setFilterDetections] = useState<Detection[]>([]);
    const [filterImages, setFilterImages] = useState<PaginatedResponse<ImageData> | null>(null);
    const [filterLoading, setFilterLoading] = useState(false);
    const [filterPage, setFilterPage] = useState(1);
    const [reviewIdx, setReviewIdx] = useState(0);
    const [sessionStart] = useState(Date.now());
    const [reviewed, setReviewed] = useState(0);
    const [cameraFilter, setCameraFilter] = useState<number | undefined>(undefined);
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');

    useEffect(() => {
        Promise.all([fetchReviewQueue(), fetchCameraStats()])
            .then(([q, c]) => { setQueue(q); setCameras(c); })
            .catch((e: any) => setError(e.message))
            .finally(() => setLoading(false));
    }, [reviewed]);

    const loadCategory = async (cat: string, page = 1) => {
        setFilterLoading(true);
        setFilterPage(page);
        setReviewIdx(0);
        try {
            if (cat === 'verify-quolls') {
                const res = await fetchDetections({ species: 'quoll', review_status: 'unreviewed', per_page: 50, page, camera_id: cameraFilter, date_from: dateFrom || undefined, date_to: dateTo || undefined });
                setFilterDetections(res.items);
            } else if (cat === 'low-confidence') {
                const res = await fetchDetections({ max_confidence: 0.5, review_status: 'unreviewed', per_page: 50, page, category: 'animal', camera_id: cameraFilter, date_from: dateFrom || undefined, date_to: dateTo || undefined });
                setFilterDetections(res.items);
            } else if (cat === 'empty-check') {
                const res = await fetchImages({ has_animal: false, per_page: 50, page, camera_id: cameraFilter });
                setFilterImages(res);
            } else if (cat === 'assign-individual') {
                const res = await fetchDetections({ species: 'quoll', review_status: 'verified', per_page: 50, page, camera_id: cameraFilter });
                setFilterDetections(res.items);
            }
        } catch { }
        setFilterLoading(false);
    };

    const openCategory = (cat: string) => {
        setFilter(cat);
        setFilterDetections([]);
        setFilterImages(null);
        loadCategory(cat);
    };

    // Keyboard shortcuts for review mode
    useEffect(() => {
        if (!filter || filter === 'empty-check') return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'ArrowRight' || e.key === 's') setReviewIdx((i) => Math.min(i + 1, filterDetections.length - 1));
            if (e.key === 'ArrowLeft') setReviewIdx((i) => Math.max(i - 1, 0));
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    });

    const sessionMinutes = Math.floor((Date.now() - sessionStart) / 60000);

    if (loading) return <LoadingState />;
    if (error) return <ErrorState message={error} />;

    return (
        <div className="pending-review-page">
            <nav className="breadcrumb">
                <Link to="/">Home</Link>
                <span className="sep">›</span>
                <span>Pending Review</span>
            </nav>
            <div className="page-header">
                <h1 className="pending-review-title">Pending Reviews for Verification</h1>
                <p className="pending-review-subtitle">Review and verify AI-detected images. Keyboard: arrow keys to navigate, Y/N for quick review.</p>
            </div>

            <div className="review-metrics">
                <div className="review-metric-card success" style={{ cursor: 'pointer' }} onClick={() => openCategory('verify-quolls')}>
                    <span className="dot green" /><span className="icon">Q</span>
                    <div><strong>{fmt(queue?.verify_quolls ?? 0)}</strong> Verify Quoll Detections</div>
                </div>
                <div className="review-metric-card warning" style={{ cursor: 'pointer' }} onClick={() => openCategory('low-confidence')}>
                    <span className="dot yellow" /><span className="icon">?</span>
                    <div><strong>{fmt(queue?.low_confidence ?? 0)}</strong> Low Confidence</div>
                </div>
                <div className="review-metric-card muted" style={{ cursor: 'pointer' }} onClick={() => openCategory('empty-check')}>
                    <span className="dot gray" /><span className="icon">~</span>
                    <div><strong>{fmt(queue?.empty_check ?? 0)}</strong> Check Empty Images</div>
                </div>
                <div className="review-metric-card" style={{ cursor: 'pointer', borderLeft: '4px solid var(--accent)' }} onClick={() => openCategory('assign-individual')}>
                    <span className="dot" style={{ background: 'var(--accent)' }} /><span className="icon">ID</span>
                    <div><strong>{fmt(queue?.assign_individual ?? 0)}</strong> Assign Individual IDs</div>
                </div>
            </div>

            {/* Session progress bar */}
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '1rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                <span>Reviewed: <strong>{reviewed}</strong></span>
                <span>Session: <strong>{sessionMinutes}min</strong></span>
                <span>Pending: <strong>{fmt(queue?.total_pending ?? 0)}</strong></span>
            </div>

            {/* Filter toolbar */}
            <div className="review-toolbar">
                <select className="filter-select" value={cameraFilter ?? ''} onChange={(e) => { setCameraFilter(e.target.value ? Number(e.target.value) : undefined); }}>
                    <option value="">All Cameras</option>
                    {cameras.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <input type="date" className="filter-select" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} title="Date from" />
                <input type="date" className="filter-select" value={dateTo} onChange={(e) => setDateTo(e.target.value)} title="Date to" />
                {filter && <button className="btn btn-outline" onClick={() => loadCategory(filter)}>Apply filters</button>}
            </div>

            {!filter ? (
                <div className="review-category-grid">
                    <ReviewCategoryCard title="Verify Quoll Detections" description="Confirm or correct quoll identifications" tagClass="success" imageCount={queue?.verify_quolls ?? 0} onReview={() => openCategory('verify-quolls')} />
                    <ReviewCategoryCard title="Low Confidence" description="Detections where the model was uncertain" tagClass="warning" imageCount={queue?.low_confidence ?? 0} onReview={() => openCategory('low-confidence')} />
                    <ReviewCategoryCard title="Check Empty Images" description="Spot-check images marked as empty for missed animals" tagClass="muted" imageCount={queue?.empty_check ?? 0} onReview={() => openCategory('empty-check')} />
                    <ReviewCategoryCard title="Assign Individual IDs" description="Assign quoll IDs to verified detections" tagClass="accent" imageCount={queue?.assign_individual ?? 0} onReview={() => openCategory('assign-individual')} />
                </div>
            ) : (
                <div className="review-list-view">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
                        <button type="button" className="btn btn-outline" onClick={() => { setFilter(null); setFilterDetections([]); setFilterImages(null); }}>← Back to categories</button>
                        {filter !== 'empty-check' && filterDetections.length > 0 && (
                            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                                Detection {reviewIdx + 1} of {filterDetections.length} — Use arrow keys / Y / N
                            </span>
                        )}
                    </div>

                    {filterLoading && <LoadingState />}

                    {/* Verify Quolls / Low Confidence / Assign Individual — detection-based review */}
                    {!filterLoading && filter !== 'empty-check' && filterDetections.length > 0 && (
                        <ReviewDetectionInline
                            detections={filterDetections}
                            currentIdx={reviewIdx}
                            onNavigate={setReviewIdx}
                            onReviewed={() => setReviewed((r) => r + 1)}
                            mode={filter === 'assign-individual' ? 'assign-id' : 'verify'}
                        />
                    )}
                    {!filterLoading && filter !== 'empty-check' && filterDetections.length === 0 && (
                        <div className="empty-state"><h3>All caught up</h3><p>No detections in this category need review.</p></div>
                    )}

                    {/* Empty check — image-based review */}
                    {!filterLoading && filter === 'empty-check' && filterImages && (
                        <div className="review-item-grid">
                            {filterImages.items.map((img) => {
                                const displayName = img.file_path ? img.file_path.split('/').slice(-2).join(' / ') : img.filename;
                                return (
                                    <div key={img.id} className="review-item-card">
                                        <div className="review-item-thumb" style={{ height: 120, overflow: 'hidden', borderRadius: 6, marginBottom: '0.5rem' }}>
                                            {(img.thumbnail_path || img.file_path) && <img src={storageUrl(img.thumbnail_path || img.file_path)} alt={img.filename} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
                                        </div>
                                        <div className="review-item-tags"><span className="tag tag-muted">Empty</span></div>
                                        <div style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>{displayName}</div>
                                        <Link to={`/review-image/${img.id}`} className="btn btn-primary" style={{ marginTop: '0.75rem' }}>Check Image</Link>
                                    </div>
                                );
                            })}
                            {filterImages.pages > 1 && (
                                <div className="pagination" style={{ gridColumn: '1/-1' }}>
                                    <button className="page-btn" onClick={() => loadCategory('empty-check', filterPage - 1)} disabled={filterPage <= 1}>Prev</button>
                                    <span className="page-info">Page {filterPage} of {filterImages.pages}</span>
                                    <button className="page-btn" onClick={() => loadCategory('empty-check', filterPage + 1)} disabled={filterPage >= filterImages.pages}>Next</button>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

/** Inline detection review with auto-advance and keyboard shortcuts */
function ReviewDetectionInline({ detections, currentIdx, onNavigate, onReviewed, mode }: {
    detections: Detection[];
    currentIdx: number;
    onNavigate: (idx: number) => void;
    onReviewed: () => void;
    mode: 'verify' | 'assign-id';
}) {
    const det = detections[currentIdx];
    const [detail, setDetail] = useState<DetectionDetail | null>(null);
    const [saving, setSaving] = useState(false);
    const [correctedSpecies, setCorrectedSpecies] = useState('');
    const [individualId, setIndividualId] = useState('');
    const [notes, setNotes] = useState('');
    const [lastAction, setLastAction] = useState<string | null>(null);

    useEffect(() => {
        if (!det) return;
        setDetail(null);
        setCorrectedSpecies('');
        setIndividualId('');
        setNotes('');
        setLastAction(null);
        fetchDetectionDetail(det.id).then(setDetail).catch(() => {});
    }, [det?.id]);

    const advance = () => {
        onReviewed();
        if (currentIdx < detections.length - 1) onNavigate(currentIdx + 1);
    };

    const submitVerdict = async (isCorrect: boolean) => {
        if (!det) return;
        setSaving(true);
        try {
            await createAnnotation({
                detection_id: det.id,
                is_correct: isCorrect,
                corrected_species: !isCorrect && correctedSpecies ? correctedSpecies : undefined,
                notes: notes || undefined,
                flag_for_retraining: !isCorrect,
            });
            setLastAction(isCorrect ? 'Confirmed correct' : 'Marked incorrect');
            setTimeout(advance, 400);
        } catch { }
        setSaving(false);
    };

    const submitIndividualId = async () => {
        if (!det || !individualId) return;
        setSaving(true);
        try {
            await createAnnotation({
                detection_id: det.id,
                is_correct: true,
                individual_id: individualId,
                notes: notes || undefined,
            });
            setLastAction(`Assigned: ${individualId}`);
            setTimeout(advance, 400);
        } catch { }
        setSaving(false);
    };

    // Keyboard shortcuts
    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;
            if (mode === 'verify') {
                if (e.key === 'y' || e.key === 'Y') submitVerdict(true);
                if (e.key === 'n' || e.key === 'N') submitVerdict(false);
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    });

    if (!det) return <div className="empty-state">No detection selected.</div>;

    return (
        <div className="chart-grid" style={{ gridTemplateColumns: '1.5fr 1fr' }}>
            <div className="card">
                <div className="card-header" style={{ justifyContent: 'space-between' }}>
                    <h3>Detection #{det.id} — {det.species || 'Unknown'}</h3>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        <button className="btn btn-outline" onClick={() => onNavigate(Math.max(0, currentIdx - 1))} disabled={currentIdx <= 0}>Prev</button>
                        <span style={{ fontSize: '0.8rem' }}>{currentIdx + 1}/{detections.length}</span>
                        <button className="btn btn-outline" onClick={() => onNavigate(Math.min(detections.length - 1, currentIdx + 1))} disabled={currentIdx >= detections.length - 1}>Next</button>
                    </div>
                </div>
                <div className="card-body" style={{ textAlign: 'center' }}>
                    {det.crop_path && <img src={storageUrl(det.crop_path)} alt="crop" style={{ maxWidth: '100%', maxHeight: '50vh', borderRadius: 8 }} />}
                    <div style={{ marginTop: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem', justifyContent: 'center' }}>
                        <span className="tag tag-primary">{det.species || 'Unknown'}</span>
                        <span className={`tag ${(det.classification_confidence ?? 0) >= 0.5 ? 'tag-primary' : 'tag-accent'}`}>
                            Cls: {det.classification_confidence != null ? (det.classification_confidence * 100).toFixed(1) + '%' : 'N/A'}
                        </span>
                        <span className="tag tag-muted">Det: {(det.detection_confidence * 100).toFixed(1)}%</span>
                        {detail?.camera && <span className="tag tag-info">Cam: {detail.camera.name}</span>}
                        {detail?.image?.captured_at && <span className="tag tag-muted">{new Date(detail.image.captured_at).toLocaleString()}</span>}
                    </div>
                    {lastAction && <div style={{ marginTop: '0.5rem', color: 'var(--primary)', fontWeight: 600, fontSize: '0.85rem' }}>{lastAction}</div>}
                </div>
            </div>
            <div className="card">
                <div className="card-header"><h3>{mode === 'assign-id' ? 'Assign Individual' : 'Quick Review'}</h3></div>
                <div className="card-body">
                    {mode === 'verify' && (
                        <>
                            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                                <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => submitVerdict(true)} disabled={saving}>
                                    Correct (Y)
                                </button>
                                <button className="btn btn-outline" style={{ flex: 1, borderColor: '#ef4444', color: '#ef4444' }} onClick={() => submitVerdict(false)} disabled={saving}>
                                    Incorrect (N)
                                </button>
                            </div>
                            <div style={{ marginBottom: '0.75rem' }}>
                                <label style={{ fontSize: '0.8rem', display: 'block', marginBottom: '0.25rem' }}>Corrected species (if incorrect)</label>
                                <select className="filter-select" style={{ width: '100%' }} value={correctedSpecies} onChange={(e) => setCorrectedSpecies(e.target.value)}>
                                    <option value="">-- select --</option>
                                    <option>Spotted-tailed Quoll</option>
                                    <option>Common Brushtail Possum</option>
                                    <option>Red Fox</option>
                                    <option>Feral Cat</option>
                                    <option>Common Wombat</option>
                                    <option>Short-beaked Echidna</option>
                                    <option>Unknown</option>
                                    <option>Not an animal</option>
                                </select>
                            </div>
                        </>
                    )}
                    {mode === 'assign-id' && (
                        <>
                            <div style={{ marginBottom: '0.75rem' }}>
                                <label style={{ fontSize: '0.8rem', display: 'block', marginBottom: '0.25rem' }}>Individual ID (e.g. 02Q2)</label>
                                <input className="filter-select" style={{ width: '100%' }} value={individualId} onChange={(e) => setIndividualId(e.target.value)} placeholder="Enter ID or 'new'" />
                            </div>
                            <button className="btn btn-primary" style={{ width: '100%' }} onClick={submitIndividualId} disabled={saving || !individualId}>
                                {saving ? 'Saving...' : 'Assign ID'}
                            </button>
                        </>
                    )}
                    <div style={{ marginTop: '0.75rem' }}>
                        <label style={{ fontSize: '0.8rem', display: 'block', marginBottom: '0.25rem' }}>Notes</label>
                        <textarea className="filter-select" style={{ width: '100%', minHeight: 50, resize: 'vertical' }} value={notes} onChange={(e) => setNotes(e.target.value)} />
                    </div>
                    <div style={{ marginTop: '0.75rem' }}>
                        <button className="btn btn-outline" style={{ fontSize: '0.8rem' }} onClick={advance}>Skip (S)</button>
                    </div>
                    <div style={{ marginTop: '1rem', fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                        <strong>Shortcuts:</strong> Y = correct, N = incorrect, S = skip, arrows = navigate
                    </div>
                </div>
            </div>
        </div>
    );
}

function ReviewCategoryCard({ title, description, tagClass, imageCount, onReview }: { title: string; description: string; tagClass: string; imageCount: number; onReview: () => void }) {
    return (
        <div className="review-category-card card" style={{ cursor: 'pointer' }} onClick={onReview}>
            <div className="review-category-title">{title}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '0.25rem 0 0.5rem' }}>{description}</div>
            <div className="review-category-meta"><span className={`tag tag-${tagClass}`}>{fmt(imageCount)} items</span></div>
            <button type="button" className="btn btn-primary" style={{ marginTop: '0.75rem' }} onClick={(e) => { e.stopPropagation(); onReview(); }}>Start Review</button>
        </div>
    );
}

/* ============================================================
   DASHBOARD (Home — WildlifeTracker approved design)
   ============================================================ */
function Dashboard() {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [report, setReport] = useState<ReportData | null>(null);
    const [cameras, setCameras] = useState<CameraStat[]>([]);
    const [species, setSpecies] = useState<SpeciesCount[]>([]);
    const [recentDetections, setRecentDetections] = useState<Detection[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [mapView, setMapView] = useState<'cluster' | 'region'>('region');

    useEffect(() => {
        let alive = true;
        const loadAll = async (showSpinner = false) => {
            if (showSpinner) setLoading(true);
            try {
                const [s, r, cam, sp, det] = await Promise.all([
                    fetchStats(),
                    fetchReport(),
                    fetchCameraStats(),
                    fetchSpeciesCounts(),
                    fetchDetections({ per_page: 5 }),
                ]);
                if (!alive) return;
                setStats(s);
                setReport(r);
                setCameras(cam);
                setSpecies(sp);
                setRecentDetections(det.items || []);
                setError(null);
            } catch (e: any) {
                if (!alive) return;
                setError(e.message);
            } finally {
                if (alive) setLoading(false);
            }
        };
        loadAll(true);
        const pollId = window.setInterval(() => loadAll(false), 5000);
        return () => { alive = false; window.clearInterval(pollId); };
    }, []);

    if (loading) return <LoadingState />;
    if (error) return <ErrorState message={error} />;
    if (!stats) return null;

    const camsWithCoords = cameras.filter((c) => c.latitude && c.longitude);
    const mapCenter: [number, number] = camsWithCoords.length > 0
        ? [camsWithCoords[0].latitude!, camsWithCoords[0].longitude!]
        : [-34.4, 150.3];

    // Activity by time of day: group hourly_activity into Dawn/Morning/Afternoon/Evening/Night
    const hourGroups = [
        { name: 'Dawn', hours: [5, 6, 7] },
        { name: 'Morning', hours: [8, 9, 10, 11] },
        { name: 'Afternoon', hours: [12, 13, 14, 15, 16] },
        { name: 'Evening', hours: [17, 18, 19, 20] },
        { name: 'Night', hours: [21, 22, 23, 0, 1, 2, 3, 4] },
    ];
    const hourlyMap = new Map<number, number>();
    if (report?.hourly_activity) {
        report.hourly_activity.forEach(({ hour, detections }) => hourlyMap.set(hour, detections));
    }
    const activityByTimeOfDay = hourGroups.map((g) => ({
        name: g.name,
        count: g.hours.reduce((sum, h) => sum + (hourlyMap.get(h) || 0), 0),
    }));

    // Observation trends: 6 months (use report total or mock)
    const totalDet = report?.total_detections ?? stats.total_detections;
    const observationTrends = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'].map((name, i) => ({
        name,
        count: Math.round(totalDet * (0.6 + (i * 0.1)) + Math.random() * 20),
    }));

    // Species abundance: Species, Individuals, Density, Trend (design uses Koala/Quoll/Kangaroo; we use API species + mock density/trend)
    const speciesAbundance = species.slice(0, 8).map((s, i) => ({
        species: s.species,
        individuals: s.count,
        density: (s.count / (i + 2)).toFixed(1),
        trend: (i % 3 === 0 ? -5 : i % 3 === 1 ? 15 : 8),
    }));

    return (
        <>
            <div className="home-stats">
                <div className="home-stat-card">
                    <div className="stat-icon-wrap green">📷</div>
                    <div>
                        <div className="stat-value">{fmt(stats.total_detections || stats.total_images)}</div>
                        <div className="stat-label">Total Observations</div>
                    </div>
                </div>
                <div className="home-stat-card">
                    <div className="stat-icon-wrap blue">🐾</div>
                    <div>
                        <div className="stat-value">{species.length}</div>
                        <div className="stat-label">Active Species</div>
                    </div>
                </div>
                <div className="home-stat-card">
                    <div className="stat-icon-wrap green">✓</div>
                    <div>
                        <div className="stat-value">{fmt(stats.total_individuals)}</div>
                        <div className="stat-label">Identified Individuals</div>
                    </div>
                </div>
                <div className="home-stat-card">
                    <div className="stat-icon-wrap orange">📋</div>
                    <div>
                        <div className="stat-value">{fmt(stats.pending_review)}</div>
                        <div className="stat-label">Pending Review</div>
                    </div>
                </div>
            </div>

            <div className="home-map-section">
                <div className="section-header">
                    <h3>CameraTrap Locations</h3>
                    <div className="view-toggle">
                        <button type="button" className={mapView === 'cluster' ? 'active' : ''} onClick={() => setMapView('cluster')}>Cluster View</button>
                        <span style={{ color: 'var(--border)' }}>|</span>
                        <button type="button" className={mapView === 'region' ? 'active' : ''} onClick={() => setMapView('region')}>Region View ▾</button>
                    </div>
                </div>
                <div className="map-wrap">
                    <MapContainer center={mapCenter} zoom={camsWithCoords.length ? 12 : 10} style={{ height: '100%', width: '100%' }}>
                        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="OSM" />
                        {camsWithCoords.map((c) => (
                            <Marker key={c.id} position={[c.latitude!, c.longitude!]}>
                                <Popup>
                                    <strong>{c.name}</strong><br />
                                    Images: {c.image_count} · Detections: {c.detection_count}
                                    {c.last_upload && <><br />Last: {new Date(c.last_upload).toLocaleDateString()}</>}
                                </Popup>
                            </Marker>
                        ))}
                    </MapContainer>
                </div>
            </div>

            <div className="home-charts">
                <div className="home-chart-card">
                    <div className="card-header"><h3>Activity by Time of Day</h3></div>
                    <div className="card-body">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={activityByTimeOfDay} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                                <YAxis tick={{ fontSize: 11 }} />
                                <Tooltip />
                                <Bar dataKey="count" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
                <div className="home-chart-card">
                    <div className="card-header"><h3>Observation Trends</h3></div>
                    <div className="card-body">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={observationTrends} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                                <YAxis tick={{ fontSize: 11 }} />
                                <Tooltip />
                                <Line type="monotone" dataKey="count" stroke="var(--info)" strokeWidth={2} dot={{ r: 4 }} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            <div className="species-abundance-section">
                <div className="section-header"><h3>Species Abundance</h3></div>
                <div className="table-container">
                    <table>
                        <thead>
                            <tr><th>Species</th><th>Individuals</th><th>Density (/km²)</th><th>Trend</th></tr>
                        </thead>
                        <tbody>
                            {speciesAbundance.length === 0 ? (
                                <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No species data yet</td></tr>
                            ) : (
                                speciesAbundance.map((row) => (
                                    <tr key={row.species}>
                                        <td>{row.species}</td>
                                        <td>{row.individuals}</td>
                                        <td>{row.density}</td>
                                        <td className={row.trend >= 0 ? 'trend-up' : 'trend-down'}>
                                            {row.trend >= 0 ? '+' : ''}{row.trend}%
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="recent-activity-section">
                <div className="section-header"><h3>Recent Activity</h3></div>
                <div className="recent-activity-list">
                    {recentDetections.length === 0 ? (
                        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No recent activity</div>
                    ) : (
                        recentDetections.map((d) => (
                            <Link key={d.id} to={`/review/${d.id}`} className="recent-activity-item">
                                <div className="thumb">
                                    {d.crop_path ? <img src={storageUrl(d.crop_path)} alt="" /> : '📷'}
                                </div>
                                <div className="content">
                                    <div className="title">{d.species || 'Unknown'} — {d.id}</div>
                                    <div className="subtitle">Detection #{d.id} · {d.created_at ? new Date(d.created_at).toLocaleString() : 'Recent'}</div>
                                </div>
                                <span className={`badge ${(d.detection_confidence || 0) >= 0.7 ? 'confirmed' : 'low-confidence'}`}>
                                    {(d.detection_confidence || 0) >= 0.7 ? 'Confirmed' : 'Low Confidence'}
                                </span>
                            </Link>
                        ))
                    )}
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
    const [filterSpecies, setFilterSpecies] = useState('all');
    const [selectedImage, setSelectedImage] = useState<ImageData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const sortedItems = images
        ? [...images.items].sort((a, b) => a.filename.localeCompare(b.filename, undefined, { numeric: true, sensitivity: 'base' }))
        : [];

    useEffect(() => {
        setLoading(true);
        setError(null);
        const params: any = { page, per_page: 48 };
        if (filterProcessed !== 'all') params.processed = filterProcessed === 'yes';
        if (filterAnimal !== 'all') params.has_animal = filterAnimal === 'yes';
        const request = filterSpecies === 'quoll' ? fetchImagesBySpecies('quoll', params) : fetchImages(params);
        request.then(setImages).catch((e) => setError(e.message)).finally(() => setLoading(false));
    }, [page, filterProcessed, filterAnimal, filterSpecies]);

    const selectedIndex = selectedImage
        ? sortedItems.findIndex((img) => img.id === selectedImage.id)
        : -1;

    const showPrevImage = useCallback(() => {
        if (selectedIndex <= 0) return;
        setSelectedImage(sortedItems[selectedIndex - 1]);
    }, [selectedIndex, sortedItems]);

    const showNextImage = useCallback(() => {
        if (selectedIndex < 0 || selectedIndex >= sortedItems.length - 1) return;
        setSelectedImage(sortedItems[selectedIndex + 1]);
    }, [selectedIndex, sortedItems]);

    useEffect(() => {
        if (!selectedImage) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'ArrowLeft') showPrevImage();
            if (e.key === 'ArrowRight') showNextImage();
            if (e.key === 'Escape') setSelectedImage(null);
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [selectedImage, showPrevImage, showNextImage]);

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
                <select className="filter-select" value={filterSpecies} onChange={(e) => { setFilterSpecies(e.target.value); setPage(1); }}>
                    <option value="all">All Species</option><option value="quoll">Quoll Only</option>
                </select>
                {images && <span className="tag tag-muted">{fmt(images.total)} images</span>}
            </div>
            {loading ? <LoadingState /> : error ? <ErrorState message={error} /> : !images || images.items.length === 0 ? (
                <div className="empty-state"><div className="icon">📷</div><h3>No images found</h3></div>
            ) : (
                <>
                    <div className="image-grid">
                        {sortedItems.map((img) => (
                            <div key={img.id} className="image-card" onClick={() => setSelectedImage(img)} style={{ cursor: 'pointer' }}>
                                <div className="image-thumb">
                                    {(img.thumbnail_path || img.file_path) ? <img src={storageUrl(img.thumbnail_path || img.file_path)} alt={img.filename} /> : '📷'}
                                    {img.has_animal && <div style={{ position: 'absolute', top: 8, right: 8, background: 'rgba(16,185,129,0.9)', borderRadius: '6px', padding: '2px 6px', fontSize: '0.65rem', fontWeight: 700, color: 'white' }}>ANIMAL</div>}
                                </div>
                                <div className="image-info">
                                    <div className="image-filename">{displayImageName(img)}</div>
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
            {selectedImage && (
                <div onClick={() => setSelectedImage(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'grid', placeItems: 'center', zIndex: 1000, padding: '1rem' }}>
                    <div className="card" onClick={(e) => e.stopPropagation()} style={{ width: 'min(900px, 100%)', maxHeight: '90vh', overflow: 'auto' }}>
                        <div className="card-header" style={{ justifyContent: 'space-between' }}>
                            <h3>{selectedImage.filename}</h3>
                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                                <button className="btn btn-outline" onClick={showPrevImage} disabled={selectedIndex <= 0}>← Prev</button>
                                <button className="btn btn-outline" onClick={showNextImage} disabled={selectedIndex >= sortedItems.length - 1}>Next →</button>
                                <button className="btn btn-outline" onClick={() => setSelectedImage(null)}>Close</button>
                            </div>
                        </div>
                        <div className="card-body">
                            <div style={{ textAlign: 'center', marginBottom: '1rem' }}>
                                <img
                                    src={storageUrl(selectedImage.file_path)}
                                    alt={selectedImage.filename}
                                    style={{ maxWidth: '100%', maxHeight: '70vh', borderRadius: 8 }}
                                />
                            </div>
                            <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginBottom: '0.75rem' }}>
                                Use keyboard: Left/Right arrows to navigate, Esc to close
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                <span className="tag tag-muted">Image #{selectedImage.id}</span>
                                {selectedImage.processed ? <span className="tag tag-primary">Processed</span> : <span className="tag tag-muted">Pending</span>}
                                {selectedImage.has_animal === true && <span className="tag tag-info">Has Animal</span>}
                                {selectedImage.has_animal === false && <span className="tag tag-muted">Empty</span>}
                                {selectedImage.camera_id && <span className="tag tag-info">Cam {selectedImage.camera_id}</span>}
                            </div>
                        </div>
                    </div>
                </div>
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
function parseFolderStructure(files: File[]) {
    const cameras = new Map<string, number>();
    let collectionName = '';
    for (const f of files) {
        const relPath = (f as any).webkitRelativePath || '';
        const parts = relPath.split('/').filter(Boolean);
        if (parts.length >= 2 && !collectionName) collectionName = parts[0];
        if (parts.length >= 3) {
            const cam = parts[1];
            cameras.set(cam, (cameras.get(cam) || 0) + 1);
        }
    }
    return { collectionName, cameras };
}

type CameraCoordinateInput = {
    latitude: string;
    longitude: string;
};

function BatchUpload() {
    const [job, setJob] = useState<JobStatus | null>(null);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [dragOver, setDragOver] = useState(false);
    const [collectionName, setCollectionName] = useState('');
    const [cameraCoordinates, setCameraCoordinates] = useState<Record<string, CameraCoordinateInput>>({});
    const folderRef = useRef<HTMLInputElement>(null);

    const folderInfo = selectedFiles.length > 0 ? parseFolderStructure(selectedFiles) : null;

    useEffect(() => {
        if (folderInfo?.collectionName && !collectionName) setCollectionName(folderInfo.collectionName);
    }, [folderInfo?.collectionName]);

    useEffect(() => {
        if (!folderInfo) {
            setCameraCoordinates({});
            return;
        }
        setCameraCoordinates((prev) => {
            const next: Record<string, CameraCoordinateInput> = {};
            for (const cam of folderInfo.cameras.keys()) {
                next[cam] = prev[cam] || { latitude: '', longitude: '' };
            }
            return next;
        });
    }, [folderInfo?.cameras, selectedFiles.length]);

    const addFiles = (files: FileList | File[]) => {
        const arr = Array.from(files).filter((f) => /\.(jpe?g|png)$/i.test(f.name));
        setSelectedFiles(arr);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
        if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
    };

    const handleUpload = async () => {
        if (selectedFiles.length === 0) return;
        const cameraPayload: Record<string, { latitude: number; longitude: number }> = {};
        if (folderInfo && folderInfo.cameras.size > 0) {
            for (const cam of folderInfo.cameras.keys()) {
                const latRaw = cameraCoordinates[cam]?.latitude?.trim();
                const lonRaw = cameraCoordinates[cam]?.longitude?.trim();
                if (!latRaw || !lonRaw) {
                    setError(`Enter latitude and longitude for camera folder "${cam}".`);
                    return;
                }
                const latitude = Number(latRaw);
                const longitude = Number(lonRaw);
                if (Number.isNaN(latitude) || latitude < -90 || latitude > 90) {
                    setError(`Latitude for "${cam}" must be a number between -90 and 90.`);
                    return;
                }
                if (Number.isNaN(longitude) || longitude < -180 || longitude > 180) {
                    setError(`Longitude for "${cam}" must be a number between -180 and 180.`);
                    return;
                }
                cameraPayload[cam] = { latitude, longitude };
            }
        }
        setUploading(true);
        setError(null);
        try {
            const res = await uploadBatch(
                selectedFiles,
                collectionName || undefined,
                Object.keys(cameraPayload).length ? cameraPayload : undefined,
            );
            pollJob(res.job_id);
        } catch (e: any) {
            const msg = e?.message?.includes('fetch')
                ? 'Upload connection dropped. Try smaller batches or retry.'
                : e.message;
            setError(msg);
            setUploading(false);
        }
    };

    const pollJob = useCallback(async (jobId: number) => {
        try {
            const s = await fetchJobStatus(jobId);
            setJob(s);
            setUploading(false);
            if (s.status === 'queued' || s.status === 'processing') {
                setTimeout(() => pollJob(jobId), 2000);
            }
        } catch {
            setUploading(false);
        }
    }, []);

    return (
        <>
            <div className="page-header"><h2>Upload Images</h2><p>Select a collection folder containing camera trap subfolders.</p></div>

            <div
                className={`dropzone ${dragOver ? 'dragover' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => folderRef.current?.click()}
            >
                <input
                    ref={folderRef}
                    type="file"
                    multiple
                    accept=".jpg,.jpeg,.png"
                    style={{ display: 'none' }}
                    {...({ webkitdirectory: '', directory: '' } as any)}
                    onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = ''; }}
                />
                <div className="dropzone-icon">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                </div>
                <p className="dropzone-text">Drop folder here or click to browse</p>
                <p className="dropzone-hint">Select the collection folder (e.g. MortonNP_June2025/) containing camera subfolders</p>
                <div className="dropzone-buttons">
                    <button type="button" className="btn btn-primary" onClick={(e) => { e.stopPropagation(); folderRef.current?.click(); }}>Choose Folder</button>
                </div>
            </div>

            {/* Folder summary: collection + cameras detected */}
            {folderInfo && selectedFiles.length > 0 && !job && (
                <div className="upload-summary card">
                    <div className="card-header"><h3>Folder Summary</h3></div>
                    <div className="card-body">
                        <div className="upload-summary-field">
                            <label>Collection Name</label>
                            <input className="filter-select" style={{ width: '100%' }} value={collectionName} onChange={(e) => setCollectionName(e.target.value)} placeholder="e.g. MortonNP_June2025" />
                        </div>
                        <div className="upload-summary-stats">
                            <div className="upload-summary-stat">
                                <span className="num">{selectedFiles.length}</span>
                                <span className="label">Total Images</span>
                            </div>
                            <div className="upload-summary-stat">
                                <span className="num">{folderInfo.cameras.size}</span>
                                <span className="label">Camera Traps Detected</span>
                            </div>
                        </div>
                        {folderInfo.cameras.size > 0 && (
                            <div className="upload-camera-list">
                                <h4>Cameras</h4>
                                <div className="upload-coord-hint">Image metadata has no GPS. Enter coordinates for each camera folder.</div>
                                <div className="upload-camera-grid">
                                    {Array.from(folderInfo.cameras.entries()).sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true })).map(([cam, count]) => (
                                        <div key={cam} className="upload-camera-chip">
                                            <span className="cam-name">{cam}</span>
                                            <span className="cam-count">{count} images</span>
                                            <input
                                                className="upload-coord-input"
                                                type="number"
                                                step="any"
                                                placeholder="Latitude"
                                                value={cameraCoordinates[cam]?.latitude || ''}
                                                onChange={(e) => setCameraCoordinates((prev) => ({
                                                    ...prev,
                                                    [cam]: { ...(prev[cam] || { latitude: '', longitude: '' }), latitude: e.target.value },
                                                }))}
                                            />
                                            <input
                                                className="upload-coord-input"
                                                type="number"
                                                step="any"
                                                placeholder="Longitude"
                                                value={cameraCoordinates[cam]?.longitude || ''}
                                                onChange={(e) => setCameraCoordinates((prev) => ({
                                                    ...prev,
                                                    [cam]: { ...(prev[cam] || { latitude: '', longitude: '' }), longitude: e.target.value },
                                                }))}
                                            />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        {folderInfo.cameras.size === 0 && (
                            <p style={{ color: 'var(--warning)', fontSize: '0.85rem', marginTop: '0.75rem' }}>
                                No camera subfolders detected. Images will be uploaded without camera assignment. Expected structure: Collection/CameraName/image.jpg
                            </p>
                        )}
                        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
                            <button className="btn btn-primary" onClick={handleUpload} disabled={uploading}>{uploading ? 'Uploading...' : `Upload & Process (${selectedFiles.length} images)`}</button>
                            <button className="btn btn-outline" onClick={() => { setSelectedFiles([]); setCollectionName(''); setCameraCoordinates({}); }}>Clear</button>
                        </div>
                        {error && <p style={{ color: 'var(--danger)', marginTop: '0.5rem', fontSize: '0.85rem' }}>{error}</p>}
                    </div>
                </div>
            )}

            {/* Batch processing progress */}
            {job && (
                <div className="upload-batch-progress card">
                    <div className="card-header">
                        <h3>Batch Processing — {job.batch_name || `Job #${job.id}`}</h3>
                        <span className={`tag ${job.status === 'completed' ? 'tag-primary' : job.status === 'failed' ? 'tag-danger' : 'tag-accent'}`}>{job.status}</span>
                    </div>
                    <div className="card-body">
                        <div className="progress-bar-bg"><div className="progress-bar-fill" style={{ width: `${job.percent}%` }} /></div>
                        <div className="progress-label"><span>{job.processed_images} / {job.total_images} processed</span><span>{job.percent.toFixed(1)}%</span></div>
                        {job.failed_images > 0 && <p style={{ color: 'var(--danger)', marginTop: '0.5rem', fontSize: '0.85rem' }}>{job.failed_images} failed</p>}
                        {job.status === 'failed' && job.error_message && <p style={{ color: 'var(--danger)', marginTop: '0.5rem', fontSize: '0.85rem' }}>{job.error_message}</p>}
                        {job.status === 'completed' && <p style={{ color: 'var(--success)', marginTop: '0.5rem', fontSize: '0.85rem' }}>All images processed successfully.</p>}
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

    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [location, setLocation] = useState('All Locations');
    const [individual, setIndividual] = useState('');
    const [exportFormat, setExportFormat] = useState<'pdf' | 'csv'>('pdf');
    
    const [incTimestamps, setIncTimestamps] = useState(true);
    const [incGPS, setIncGPS] = useState(true);
    const [incConfidence, setIncConfidence] = useState(true);
    const [incEnv, setIncEnv] = useState(false);
    const [incCamera, setIncCamera] = useState(false);

    useEffect(() => { 
        fetchReport().then(setReport).catch((e) => setError(e.message)).finally(() => setLoading(false)); 
    }, []);

    if (loading) return <LoadingState />;
    if (error) return <ErrorState message={error} />;
    if (!report) return null;

    const downloadFile = async (url: string, filename: string) => {
        try {
            const res = await fetch(url);
            if (!res.ok) throw new Error(`Download failed (${res.status})`);
            const blob = await res.blob();
            const objectUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = objectUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(objectUrl);
        } catch (e: any) {
            setError(e.message || 'Download failed');
        }
    };

    const handleExport = () => {
        if (exportFormat === 'csv') {
            downloadFile(getExportUrl('csv'), 'custom_wildlife_report.csv');
        } else {
            alert("PDF generation is currently being implemented on the server. Downloading raw JSON data instead.");
            downloadFile(getExportUrl('json'), 'wildlife_report_data.json');
        }
    };

    return (
        <div className="reports-page-wrapper">
            <div className="reports-container">
                
                {/* Header */}
                <div className="reports-header">
                    <div>
                        <h1 className="reports-title">Report Generation</h1>
                        <p className="reports-subtitle">Generate and export reports for your sightings data</p>
                    </div>
                    <button onClick={handleExport} className="btn-export">
                        <img src="https://api.iconify.design/heroicons:arrow-down-tray-20-solid.svg?color=white" alt="download" />
                        Export Report
                    </button>
                </div>

                {/* Customisation UI */}
                <section className="report-section">
                    <h2 className="section-label">Customise Your Report</h2>
                    
                    <div className="form-grid">
                        <div className="form-col-span-2">
                            <div className="date-row">
                                <div>
                                    <label className="form-label">Date Range</label>
                                    <div className="date-flex">
                                        <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="form-input" />
                                        <span className="date-sep">to</span>
                                        <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="form-input" />
                                    </div>
                                </div>
                                <div>
                                    <label className="form-label">Location</label>
                                    <select value={location} onChange={(e) => setLocation(e.target.value)} className="form-input">
                                        <option>All Locations</option>
                                        {report.camera_counts.map(c => (
                                            <option key={c.camera} value={c.camera}>{c.camera}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                            <div style={{ marginTop: '1.5rem' }}>
                                <label className="form-label">Individual</label>
                                <input type="text" value={individual} onChange={(e) => setIndividual(e.target.value)} placeholder="e.g. #STQ_12A, #STQ_13A" className="form-input" />
                            </div>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%' }}>
                            <div>
                                <label className="form-label">Report Format</label>
                                <div className="format-group">
                                    <label className={`format-card ${exportFormat === 'pdf' ? 'active' : ''}`} onClick={() => setExportFormat('pdf')}>
                                        <img src="https://api.iconify.design/bi:file-earmark-pdf-fill.svg" alt="pdf" />
                                        <span>PDF Report</span>
                                    </label>
                                    <label className={`format-card ${exportFormat === 'csv' ? 'active' : ''}`} onClick={() => setExportFormat('csv')}>
                                        <img src="https://api.iconify.design/bi:file-earmark-spreadsheet-fill.svg" alt="csv" />
                                        <span>CSV Data</span>
                                    </label>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div className="checkbox-section">
                        <label className="form-label" style={{ marginBottom: '1rem' }}>Data To Include</label>
                        <div className="checkbox-grid">
                            <label className="checkbox-label">
                                <input type="checkbox" checked={incTimestamps} onChange={(e) => setIncTimestamps(e.target.checked)} className="custom-checkbox" />
                                <span>Sighting Timestamps</span>
                            </label>
                            <label className="checkbox-label">
                                <input type="checkbox" checked={incGPS} onChange={(e) => setIncGPS(e.target.checked)} className="custom-checkbox" />
                                <span>GPS Coordinates</span>
                            </label>
                            <label className="checkbox-label">
                                <input type="checkbox" checked={incConfidence} onChange={(e) => setIncConfidence(e.target.checked)} className="custom-checkbox" />
                                <span>AI Confidence Score</span>
                            </label>
                            <label className="checkbox-label">
                                <input type="checkbox" checked={incEnv} onChange={(e) => setIncEnv(e.target.checked)} className="custom-checkbox" />
                                <span>Environment Data</span>
                            </label>
                            <label className="checkbox-label">
                                <input type="checkbox" checked={incCamera} onChange={(e) => setIncCamera(e.target.checked)} className="custom-checkbox" />
                                <span>Camera Trap ID</span>
                            </label>
                        </div>
                    </div>
                </section>

                {/* Report Preview */}
                <section className="preview-section">
                    <div className="preview-header">
                        <span className="preview-header-title">Report Preview</span>
                        <span className="preview-header-meta">Showing Sample Sightings</span>
                    </div>

                    <div className="table-wrapper">
                        <table className="report-table">
                            <thead>
                                <tr>
                                    <th>Sighting ID</th>
                                    {incTimestamps && <th>Timestamp</th>}
                                    <th>Species</th>
                                    {incConfidence && <th>Confidence</th>}
                                    {incGPS && <th>Coordinates</th>}
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td className="text-strong">S-001</td>
                                    {incTimestamps && <td style={{ color: '#4b5563' }}>2025-09-13 23:12:04</td>}
                                    <td className="text-italic">Spotted-tail Quoll</td>
                                    {incConfidence && <td><span className="conf-high">96%</span></td>}
                                    {incGPS && <td className="text-mono">-35.123, 150.456</td>}
                                </tr>
                                <tr>
                                    <td className="text-strong">S-005</td>
                                    {incTimestamps && <td style={{ color: '#4b5563' }}>2025-09-13 15:22:56</td>}
                                    <td className="text-italic">Spotted-tail Quoll</td>
                                    {incConfidence && <td><span className="conf-low">46%</span></td>}
                                    {incGPS && <td className="text-mono">-35.120, 150.450</td>}
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <div className="viz-area">
                        <h4 className="section-label" style={{ marginBottom: '2.5rem' }}>Additional Data Visualizations</h4>
                        <div className="viz-grid">
                            {report.species_distribution.length > 0 && (
                                <div className="viz-card">
                                    <div style={{ height: 300 }}>
                                        <ResponsiveContainer>
                                            <PieChart>
                                                <Pie data={report.species_distribution} dataKey="count" nameKey="species" cx="50%" cy="50%" outerRadius={100} label={({ species, percent }) => `${species.split('|').pop()?.trim()} ${(percent * 100).toFixed(0)}%`}>
                                                    {report.species_distribution.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                                                </Pie>
                                                <Tooltip />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    </div>
                                    <p className="viz-caption">Fig 1. Species Distribution</p>
                                </div>
                            )}
                            
                            {report.hourly_activity.length > 0 && (
                                <div className="viz-card">
                                    <div style={{ height: 300 }}>
                                        <ResponsiveContainer>
                                            <BarChart data={report.hourly_activity}>
                                                <XAxis dataKey="hour" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                                                <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} />
                                                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '8px' }} />
                                                <Bar dataKey="detections" fill="#16a34a" radius={[4, 4, 0, 0]} />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                    <p className="viz-caption">Fig 2. Quoll Activity Pattern (24h)</p>
                                </div>
                            )}
                        </div>
                    </div>
                </section>
            </div>
        </div>
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
    const [form, setForm] = useState<{ is_correct: boolean; corrected_species: string; notes: string; individual_id: string; flag_for_retraining: boolean; bbox?: { x: number; y: number; w: number; h: number } }>({ is_correct: true, corrected_species: '', notes: '', individual_id: '', flag_for_retraining: false });
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
            const notes = form.bbox ? JSON.stringify({ bbox: form.bbox, type: 'user_drawn' }) : form.notes;
            const ann = await createAnnotation({
                detection_id: det.id,
                is_correct: form.is_correct,
                corrected_species: form.corrected_species || undefined,
                notes: notes || undefined,
                individual_id: form.individual_id || undefined,
                flag_for_retraining: form.flag_for_retraining,
            });
            setAnns([ann, ...anns]);
            setForm({ is_correct: true, corrected_species: '', notes: '', individual_id: '', flag_for_retraining: false, bbox: undefined });
        } catch { }
        setSaving(false);
    };

    if (loading) return <LoadingState />;
    if (!det) return <div className="empty-state"><h3>Detection not found</h3></div>;

    return (
        <>
            <div className="page-header"><h2>Review Detection #{det.id}</h2><p>{det.image ? displayImageName(det.image) : 'Unknown'} — {det.species}</p></div>
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
                        {!form.is_correct && (
                            <div style={{ marginBottom: '1rem' }}>
                                <label style={{ fontSize: '0.8rem', display: 'block', marginBottom: '0.25rem' }}>Draw box around animal (feedback for model)</label>
                                {det.image?.file_path && (
                                    <BboxDrawer
                                        imageUrl={storageUrl(det.image.file_path)}
                                        onDraw={(bbox) => setForm((f) => ({ ...f, bbox }))}
                                    />
                                )}
                            </div>
                        )}
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

/* Draw bbox on image for annotation / missed-detection feedback */
function BboxDrawer({ imageUrl, onDraw }: { imageUrl: string; onDraw: (bbox: { x: number; y: number; w: number; h: number }) => void }) {
    const imgRef = useRef<HTMLImageElement>(null);
    const drawingRef = useRef(false);
    const startRef = useRef<{ x: number; y: number } | null>(null);
    const [liveBox, setLiveBox] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
    const [savedBox, setSavedBox] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

    const toRelative = useCallback((clientX: number, clientY: number) => {
        const img = imgRef.current;
        if (!img) return { x: 0, y: 0 };
        const rect = img.getBoundingClientRect();
        return {
            x: Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)),
            y: Math.max(0, Math.min(1, (clientY - rect.top) / rect.height)),
        };
    }, []);

    const handlePointerDown = useCallback((e: React.PointerEvent) => {
        e.preventDefault();
        (e.target as HTMLElement).setPointerCapture(e.pointerId);
        const pt = toRelative(e.clientX, e.clientY);
        startRef.current = pt;
        drawingRef.current = true;
        setLiveBox({ x: pt.x, y: pt.y, w: 0, h: 0 });
        setSavedBox(null);
    }, [toRelative]);

    const handlePointerMove = useCallback((e: React.PointerEvent) => {
        if (!drawingRef.current || !startRef.current) return;
        const pt = toRelative(e.clientX, e.clientY);
        const s = startRef.current;
        setLiveBox({
            x: Math.min(s.x, pt.x),
            y: Math.min(s.y, pt.y),
            w: Math.abs(pt.x - s.x),
            h: Math.abs(pt.y - s.y),
        });
    }, [toRelative]);

    const handlePointerUp = useCallback((e: React.PointerEvent) => {
        if (!drawingRef.current || !startRef.current) return;
        drawingRef.current = false;
        const pt = toRelative(e.clientX, e.clientY);
        const s = startRef.current;
        const box = {
            x: Math.min(s.x, pt.x),
            y: Math.min(s.y, pt.y),
            w: Math.max(Math.abs(pt.x - s.x), 0.02),
            h: Math.max(Math.abs(pt.y - s.y), 0.02),
        };
        startRef.current = null;
        setLiveBox(null);
        setSavedBox(box);
        onDraw(box);
    }, [toRelative, onDraw]);

    const box = liveBox || savedBox;

    return (
        <div style={{ userSelect: 'none' }}>
            <div
                style={{ position: 'relative', display: 'inline-block', cursor: 'crosshair', maxWidth: '100%', touchAction: 'none' }}
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
            >
                <img ref={imgRef} src={imageUrl} alt="Draw box" draggable={false} style={{ maxWidth: '100%', height: 'auto', display: 'block', borderRadius: 8 }} />
                {box && box.w > 0.005 && box.h > 0.005 && (
                    <div
                        style={{
                            position: 'absolute',
                            left: `${box.x * 100}%`,
                            top: `${box.y * 100}%`,
                            width: `${box.w * 100}%`,
                            height: `${box.h * 100}%`,
                            border: '3px solid #10b981',
                            background: 'rgba(16, 185, 129, 0.15)',
                            borderRadius: 4,
                            pointerEvents: 'none',
                        }}
                    />
                )}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 6 }}>
                {savedBox ? '✓ Box drawn — drag again to redraw' : 'Click and drag on the image to draw a box around the animal'}
            </div>
        </div>
    );
}

/* ============================================================
   REVIEW IMAGE — step-based review from any image context
   Step 1: What action?  (Confirm empty / Has animal)
   Step 2 (if has animal): Species? → Draw bbox → Save
   ============================================================ */
function ReviewImage() {
    const { imageId } = useParams();
    const id = parseInt(imageId || '0');
    const [image, setImage] = useState<ImageData | null>(null);
    const [loading, setLoading] = useState(true);
    const [step, setStep] = useState<'choose' | 'annotate' | 'done'>('choose');
    const [bbox, setBbox] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
    const [species, setSpecies] = useState('Spotted-tailed Quoll');
    const [individualId, setIndividualId] = useState('');
    const [notes, setNotes] = useState('');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (!id) return;
        fetchImageDetail(id).then((data: any) => setImage(data)).catch(() => {}).finally(() => setLoading(false));
    }, [id]);

    const confirmEmpty = async () => {
        if (!image) return;
        setSaving(true);
        try {
            await createMissedDetection(image.id, { bbox_x: 0, bbox_y: 0, bbox_w: 0, bbox_h: 0, species: '__confirmed_empty__', flag_for_retraining: false });
            setStep('done');
        } catch { }
        setSaving(false);
    };

    const submitAnimal = async () => {
        if (!image || !bbox) return;
        setSaving(true);
        try {
            await createMissedDetection(image.id, { bbox_x: bbox.x, bbox_y: bbox.y, bbox_w: bbox.w, bbox_h: bbox.h, species, flag_for_retraining: true });
            setStep('done');
        } catch { }
        setSaving(false);
    };

    if (loading) return <LoadingState />;
    if (!image) return <div className="empty-state"><h3>Image not found</h3></div>;

    if (step === 'done') return (
        <div className="review-done">
            <div className="review-done-icon">✓</div>
            <h2>Review saved</h2>
            <p>Thank you — this feedback will help improve the model.</p>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', marginTop: '1rem' }}>
                <Link to="/pending-review" className="btn btn-primary">Back to Pending Review</Link>
                <button type="button" className="btn btn-outline" onClick={() => window.history.back()}>Go Back</button>
            </div>
        </div>
    );

    return (
        <div>
            <nav className="breadcrumb"><Link to="/">Home</Link><span className="sep">›</span><span>Review Image</span></nav>
            <div className="page-header"><h2>Review — {displayImageName(image)}</h2><p>Decide how to classify this image.</p></div>

            <div className="review-image-layout">
                <div className="review-image-left card">
                    <div className="card-body" style={{ textAlign: 'center' }}>
                        {step === 'choose' && <img src={storageUrl(image.file_path)} alt={image.filename} style={{ maxWidth: '100%', maxHeight: '65vh', borderRadius: 8 }} />}
                        {step === 'annotate' && (
                            <BboxDrawer imageUrl={storageUrl(image.file_path)} onDraw={setBbox} />
                        )}
                    </div>
                    <div className="card-body" style={{ paddingTop: 0, display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <span className="tag tag-muted">Image #{image.id}</span>
                        {image.processed ? <span className="tag tag-primary">Processed</span> : <span className="tag tag-muted">Pending</span>}
                        {image.has_animal === true && <span className="tag tag-info">Has Animal</span>}
                        {image.has_animal === false && <span className="tag tag-muted">Marked Empty</span>}
                        {image.camera_id && <span className="tag tag-info">Cam {image.camera_id}</span>}
                    </div>
                </div>

                <div className="review-image-right">
                    {step === 'choose' && (
                        <div className="card">
                            <div className="card-header"><h3>What do you see?</h3></div>
                            <div className="card-body review-action-choices">
                                <button type="button" className="review-action-btn empty" onClick={confirmEmpty} disabled={saving}>
                                    <span className="review-action-icon">⬜</span>
                                    <span>Image is empty</span>
                                    <span className="review-action-hint">Confirm no animal present</span>
                                </button>
                                <button type="button" className="review-action-btn has-animal" onClick={() => setStep('annotate')}>
                                    <span className="review-action-icon">🐾</span>
                                    <span>Has animal</span>
                                    <span className="review-action-hint">Draw a box around the animal</span>
                                </button>
                            </div>
                        </div>
                    )}

                    {step === 'annotate' && (
                        <div className="card">
                            <div className="card-header"><h3>Annotate Animal</h3></div>
                            <div className="card-body">
                                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>Draw a box around the animal on the image, then fill in the details below.</p>
                                {bbox && <div className="tag tag-primary" style={{ marginBottom: '1rem' }}>Box drawn ✓</div>}
                                <div className="review-field">
                                    <label>Species</label>
                                    <select className="filter-select" value={species} onChange={(e) => setSpecies(e.target.value)}>
                                        <option>Spotted-tailed Quoll</option>
                                        <option>Quoll (unknown sp)</option>
                                        <option>Red Kangaroo</option>
                                        <option>Common Wombat</option>
                                        <option>Short-beaked Echidna</option>
                                        <option>Tasmanian Devil</option>
                                        <option>Bennett's Wallaby</option>
                                        <option>Common Brushtail Possum</option>
                                        <option>Unknown</option>
                                        <option>Other</option>
                                    </select>
                                </div>
                                <div className="review-field">
                                    <label>Individual ID (optional, e.g. 02Q2)</label>
                                    <input className="filter-select" style={{ width: '100%' }} value={individualId} onChange={(e) => setIndividualId(e.target.value)} placeholder="Leave blank if unknown" />
                                </div>
                                <div className="review-field">
                                    <label>Notes (optional)</label>
                                    <textarea className="filter-select" style={{ width: '100%', minHeight: 50, resize: 'vertical' }} value={notes} onChange={(e) => setNotes(e.target.value)} />
                                </div>
                                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
                                    <button className="btn btn-primary" onClick={submitAnimal} disabled={!bbox || saving}>{saving ? 'Saving...' : 'Save Annotation'}</button>
                                    <button className="btn btn-outline" onClick={() => setStep('choose')}>Back</button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function ReviewEmptyImage() {
    const { imageId } = useParams();
    return <Navigate to={`/review-image/${imageId}`} replace />;
}

/* ============================================================
   PROFILES — Species & Individuals Explorer (hierarchy)
   ============================================================ */
function SpeciesExplorer() {
    const [species, setSpecies] = useState<SpeciesCount[]>([]);
    const [individuals, setIndividuals] = useState<IndividualData[]>([]);
    const [thumbs, setThumbs] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [view, setView] = useState<'grid' | 'list'>('grid');
    const [search, setSearch] = useState('');

    useEffect(() => {
        Promise.all([fetchSpeciesCounts(), fetchIndividuals()]).then(([s, i]) => { setSpecies(s); setIndividuals(i); }).catch((e) => setError(e.message)).finally(() => setLoading(false));
    }, []);

    useEffect(() => {
        if (species.length === 0) return;
        const pending: Record<string, string> = {};
        Promise.all(
            species.map((s) =>
                fetchImagesBySpecies(s.species, { per_page: 1 })
                    .then((res) => {
                        const img = res.items[0];
                        if (img) pending[s.species] = storageUrl(img.thumbnail_path || img.file_path);
                    })
                    .catch(() => {})
            )
        ).then(() => setThumbs(pending));
    }, [species]);

    const slug = (name: string) => encodeURIComponent(name.toLowerCase().replace(/\s+/g, '-'));
    const bySpecies = species.map((s) => {
        const inds = individuals.filter((i) => i.species.toLowerCase().includes(s.species.toLowerCase()) || s.species.toLowerCase().includes(i.species.toLowerCase()));
        return { ...s, individuals: inds.length, individualList: inds };
    }).filter((s) => !search || s.species.toLowerCase().includes(search.toLowerCase()));

    if (loading) return <LoadingState />;
    if (error) return <ErrorState message={error} />;

    return (
        <div className="species-explorer-page">
            <nav className="breadcrumb"><Link to="/">Home</Link><span className="sep">›</span><span className="active">Profiles</span><span className="sep">›</span><span>Species Overview</span></nav>
            <div className="page-header">
                <h1 className="species-explorer-title">Species & Individuals Explorer</h1>
                <p className="species-explorer-subtitle">Explore and manage all species and individual animals recorded in the system.</p>
            </div>
            <div className="species-toolbar">
                <input type="search" className="review-search" placeholder="Search species..." value={search} onChange={(e) => setSearch(e.target.value)} />
                <select className="filter-select"><option>Sort by: Alphabetical</option></select>
                <div className="view-toggle">
                    <button type="button" className={view === 'grid' ? 'active' : ''} onClick={() => setView('grid')} aria-label="Grid">▦</button>
                    <button type="button" className={view === 'list' ? 'active' : ''} onClick={() => setView('list')} aria-label="List">≡</button>
                </div>
            </div>
            <div className={view === 'grid' ? 'species-card-grid' : 'species-list'}>
                {bySpecies.map((s) => (
                    <Link key={s.species} to={`/individuals/species/${slug(s.species)}`} className="species-card card">
                        <div className="species-card-image">
                            {thumbs[s.species] ? <img src={thumbs[s.species]} alt={s.species} style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : '🐾'}
                        </div>
                        <span className="species-card-status">Common</span>
                        <div className="species-card-name">{s.species}</div>
                        <div className="species-card-scientific">{s.species}</div>
                        <div className="species-card-stats">🐾 {s.individuals} individuals · 👁 {fmt(s.count)} obs.</div>
                    </Link>
                ))}
            </div>
            <div className="system-overview">
                <div className="system-overview-stat"><span className="num green">{species.length}</span> Total Species</div>
                <div className="system-overview-stat"><span className="num blue">{individuals.length}</span> Individual Animals</div>
                <div className="system-overview-stat"><span className="num orange">{fmt(species.reduce((a, b) => a + b.count, 0))}</span> Total Observations</div>
            </div>
        </div>
    );
}

function SpeciesDetail() {
    const { speciesKey } = useParams();
    const decoded = speciesKey ? decodeURIComponent(speciesKey).replace(/-/g, ' ') : '';
    const isQuoll = /quoll/i.test(decoded);

    return (
        <div>
            <nav className="breadcrumb"><Link to="/">Home</Link><span className="sep">›</span><Link to="/individuals">Profiles</Link><span className="sep">›</span><span>Species: {decoded}</span></nav>
            <div className="page-header">
                <h2>{decoded}</h2>
                <p>View images or browse by individual.</p>
            </div>
            <div className="species-choice-cards">
                <Link to={`/individuals/species/${speciesKey}/images`} className="card species-choice-card">
                    <h3>View all images</h3>
                    <p>All images containing this species</p>
                </Link>
                {isQuoll && (
                    <Link to={`/individuals/species/${speciesKey}/individuals`} className="card species-choice-card">
                        <h3>View by individual (ID)</h3>
                        <p>Browse quoll folders by individual ID</p>
                    </Link>
                )}
            </div>
        </div>
    );
}

function SpeciesImages() {
    const { speciesKey } = useParams();
    const decoded = speciesKey ? decodeURIComponent(speciesKey).replace(/-/g, ' ') : '';
    const isQuoll = /quoll/i.test(decoded);
    const { user } = useAuth();
    const [images, setImages] = useState<PaginatedResponse<ImageData> | null>(null);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState<ImageData | null>(null);
    const [detections, setDetections] = useState<Detection[]>([]);
    const [showBoxes, setShowBoxes] = useState(true);
    const [focusedDetId, setFocusedDetId] = useState<number | null>(null);

    const [individuals, setIndividuals] = useState<IndividualData[]>([]);
    const [indsLoading, setIndsLoading] = useState(false);

    const [assignId, setAssignId] = useState('');
    const [assignNotes, setAssignNotes] = useState('');
    const [savingAssign, setSavingAssign] = useState(false);
    const [assignMsg, setAssignMsg] = useState<string | null>(null);

    const [compareId, setCompareId] = useState('');
    const [compareGallery, setCompareGallery] = useState<IndividualGalleryItem[]>([]);
    const [compareLoading, setCompareLoading] = useState(false);

    const [createOpen, setCreateOpen] = useState(false);
    const [newIndividualId, setNewIndividualId] = useState('');
    const [newName, setNewName] = useState('');
    const [refLeft, setRefLeft] = useState<number | null>(null);
    const [refRight, setRefRight] = useState<number | null>(null);
    const [createBusy, setCreateBusy] = useState(false);
    const [createMsg, setCreateMsg] = useState<string | null>(null);

    const [unassignedOnly, setUnassignedOnly] = useState(false);
    const [selectMode, setSelectMode] = useState(false);
    const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
    const [bulkAssignId, setBulkAssignId] = useState('');
    const [bulkAssigning, setBulkAssigning] = useState(false);
    const [bulkAssignMsg, setBulkAssignMsg] = useState<string | null>(null);

    useEffect(() => {
        if (!decoded) return;
        setLoading(true);
        fetchImagesBySpecies(decoded, { page, per_page: 30, unassigned_only: unassignedOnly })
            .then(setImages).catch(() => {}).finally(() => setLoading(false));
    }, [decoded, page, unassignedOnly]);

    const refreshSelectedDetail = useCallback(async () => {
        if (!selected) return;
        try {
            const detail: any = await fetchImageDetail(selected.id);
            setDetections(detail.detections || []);
        } catch {
            setDetections([]);
        }
    }, [selected?.id]);

    useEffect(() => {
        if (!selected) { setDetections([]); return; }
        refreshSelectedDetail();
    }, [selected?.id]);

    useEffect(() => {
        if (!selected) {
            setFocusedDetId(null);
            setAssignId('');
            setAssignNotes('');
            setAssignMsg(null);
            setCompareId('');
            setCompareGallery([]);
            setCreateOpen(false);
            setCreateMsg(null);
            setNewIndividualId('');
            setNewName('');
            setRefLeft(null);
            setRefRight(null);
            return;
        }
        // When an image opens, default focus to first detection if any.
        if (detections.length === 1) setFocusedDetId(detections[0].id);
        if (focusedDetId == null && detections.length > 0) setFocusedDetId(detections[0].id);
    }, [selected?.id, detections.length]);

    useEffect(() => {
        if (!isQuoll) return;
        if (!selected && !selectMode) return;
        setIndsLoading(true);
        fetchIndividuals()
            .then((list) => setIndividuals(list.filter((i) => individualMatchesSpeciesPage(i, decoded))))
            .catch(() => setIndividuals([]))
            .finally(() => setIndsLoading(false));
    }, [selected?.id, isQuoll, decoded, selectMode]);

    useEffect(() => {
        if (!compareId) { setCompareGallery([]); return; }
        setCompareLoading(true);
        fetchIndividualGallery(compareId)
            .then((g) => setCompareGallery(g.items || []))
            .catch(() => setCompareGallery([]))
            .finally(() => setCompareLoading(false));
    }, [compareId]);

    const sortedItems = images ? [...images.items].sort((a, b) => a.filename.localeCompare(b.filename, undefined, { numeric: true, sensitivity: 'base' })) : [];
    const selectedIdx = selected ? sortedItems.findIndex((i) => i.id === selected.id) : -1;
    const goPrev = () => { if (selectedIdx > 0) setSelected(sortedItems[selectedIdx - 1]); };
    const goNext = () => { if (selectedIdx >= 0 && selectedIdx < sortedItems.length - 1) setSelected(sortedItems[selectedIdx + 1]); };

    useEffect(() => {
        if (!selected) return;
        const onKey = (e: KeyboardEvent) => { if (e.key === 'ArrowLeft') goPrev(); if (e.key === 'ArrowRight') goNext(); if (e.key === 'Escape') setSelected(null); };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    });

    if (loading) return <LoadingState />;
    const focused = focusedDetId != null ? detections.find((d) => d.id === focusedDetId) : null;
    const currentAssigned = (() => {
        if (!focused?.annotations || focused.annotations.length === 0) return null;
        const withId = focused.annotations.filter((a) => a && a.individual_id);
        if (withId.length === 0) return null;
        withId.sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''));
        return withId[withId.length - 1].individual_id || null;
    })();

    return (
        <div>
            <nav className="breadcrumb"><Link to="/">Home</Link><span className="sep">›</span><Link to="/individuals">Profiles</Link><span className="sep">›</span><Link to={`/individuals/species/${speciesKey}`}>{decoded}</Link><span className="sep">›</span><span>Images</span></nav>
            <div className="page-header"><h2>All images — {decoded}</h2><span className="tag tag-muted" style={{ marginLeft: '0.5rem' }}>{images?.total ?? 0} images</span></div>

            {/* Filter & selection toolbar */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', marginBottom: '1rem', padding: '0.6rem 0.9rem', background: 'var(--card-bg)', borderRadius: 8, border: '1px solid var(--border)' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.875rem', fontWeight: 500 }}>
                    <input
                        type="checkbox"
                        checked={unassignedOnly}
                        onChange={(e) => {
                            setUnassignedOnly(e.target.checked);
                            setPage(1);
                            setSelectedIds(new Set());
                            setSelectMode(false);
                            setBulkAssignMsg(null);
                        }}
                    />
                    Unassigned only
                </label>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    {selectMode && selectedIds.size > 0 && (
                        <button className="btn btn-outline" style={{ fontSize: '0.8rem' }}
                            onClick={() => setSelectedIds(new Set(sortedItems.map((i) => i.id)))}>
                            Select all on page
                        </button>
                    )}
                    {selectMode && selectedIds.size > 0 && (
                        <button className="btn btn-outline" style={{ fontSize: '0.8rem' }}
                            onClick={() => setSelectedIds(new Set())}>
                            Clear
                        </button>
                    )}
                    <button
                        className={selectMode ? 'btn btn-primary' : 'btn btn-outline'}
                        style={{ fontSize: '0.85rem' }}
                        onClick={() => {
                            setSelectMode((m) => !m);
                            setSelectedIds(new Set());
                            setBulkAssignMsg(null);
                        }}
                    >
                        {selectMode ? `Selection mode (${selectedIds.size} selected)` : 'Select images'}
                    </button>
                </div>
            </div>

            {!images || images.items.length === 0 ? <div className="empty-state">{unassignedOnly ? 'No unassigned images for this species.' : 'No images for this species.'}</div> : (
                <>
                    <div className="image-grid">
                        {sortedItems.map((img) => (
                            <div
                                key={img.id}
                                className="image-card"
                                onClick={() => {
                                    if (selectMode) {
                                        setSelectedIds((prev) => {
                                            const next = new Set(prev);
                                            if (next.has(img.id)) next.delete(img.id);
                                            else next.add(img.id);
                                            return next;
                                        });
                                    } else {
                                        setSelected(img);
                                    }
                                }}
                                style={{
                                    cursor: 'pointer',
                                    position: 'relative',
                                    outline: selectedIds.has(img.id) ? '3px solid #3b82f6' : undefined,
                                    outlineOffset: '-2px',
                                }}
                            >
                                {selectMode && (
                                    <div style={{ position: 'absolute', top: 6, left: 6, zIndex: 2, pointerEvents: 'none' }}>
                                        <input
                                            type="checkbox"
                                            readOnly
                                            checked={selectedIds.has(img.id)}
                                            style={{ width: 17, height: 17, accentColor: '#3b82f6' }}
                                        />
                                    </div>
                                )}
                                <div className="image-thumb">
                                    {(img.thumbnail_path || img.file_path) ? <img src={storageUrl(img.thumbnail_path || img.file_path)} alt={img.filename} /> : '📷'}
                                    {img.has_animal && <div className="image-animal-badge">ANIMAL</div>}
                                </div>
                                <div className="image-info">
                                    <div className="image-filename">{displayImageName(img)}</div>
                                    <div className="image-meta">
                                        {img.processed ? <span className="tag tag-primary">Processed</span> : <span className="tag tag-muted">Pending</span>}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Bulk-assign bar */}
                    {selectMode && selectedIds.size > 0 && (
                        <div style={{ position: 'sticky', bottom: 0, zIndex: 100, background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '0.75rem 1rem', display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', boxShadow: '0 -4px 16px rgba(0,0,0,0.18)', marginTop: '1rem' }}>
                            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                                {selectedIds.size} image{selectedIds.size !== 1 ? 's' : ''} selected
                            </span>
                            <input
                                className="filter-select"
                                style={{ flex: '1 1 160px', minWidth: 120 }}
                                value={bulkAssignId}
                                onChange={(e) => setBulkAssignId(e.target.value)}
                                placeholder="Profile ID (e.g. 02Q2)"
                                disabled={bulkAssigning}
                            />
                            {individuals.length > 0 && (
                                <select
                                    className="filter-select"
                                    value={bulkAssignId}
                                    onChange={(e) => setBulkAssignId(e.target.value)}
                                    disabled={bulkAssigning || indsLoading}
                                    style={{ flex: '1 1 200px', minWidth: 140 }}
                                >
                                    <option value="">Pick profile…</option>
                                    {individuals.map((ind) => (
                                        <option key={ind.individual_id} value={ind.individual_id}>
                                            {ind.individual_id}{(ind as any).name ? ` — ${(ind as any).name}` : ''}
                                        </option>
                                    ))}
                                </select>
                            )}
                            <button
                                className="btn btn-primary"
                                disabled={bulkAssigning || !bulkAssignId.trim() || !user}
                                onClick={async () => {
                                    if (!bulkAssignId.trim()) return;
                                    setBulkAssigning(true);
                                    setBulkAssignMsg(null);
                                    let assigned = 0;
                                    let failed = 0;
                                    for (const imgId of Array.from(selectedIds)) {
                                        try {
                                            const detail: any = await fetchImageDetail(imgId);
                                            const dets: Detection[] = detail.detections || [];
                                            for (const det of dets) {
                                                await createAnnotation({ detection_id: det.id, is_correct: true, individual_id: bulkAssignId.trim() });
                                                assigned++;
                                            }
                                        } catch {
                                            failed++;
                                        }
                                    }
                                    setBulkAssignMsg(`Done: ${assigned} detection${assigned !== 1 ? 's' : ''} assigned to ${bulkAssignId.trim()}${failed ? ` (${failed} image error${failed !== 1 ? 's' : ''})` : ''}.`);
                                    setBulkAssigning(false);
                                    setSelectedIds(new Set());
                                    if (unassignedOnly) {
                                        setLoading(true);
                                        fetchImagesBySpecies(decoded, { page, per_page: 30, unassigned_only: true })
                                            .then(setImages).catch(() => {}).finally(() => setLoading(false));
                                    }
                                }}
                            >
                                {bulkAssigning ? 'Assigning…' : `Assign to ${bulkAssignId || '…'}`}
                            </button>
                            {!user && <span className="tag tag-muted">Login required</span>}
                            {bulkAssignMsg && <span className="tag tag-info" style={{ fontSize: '0.8rem' }}>{bulkAssignMsg}</span>}
                        </div>
                    )}

                    {images.pages > 1 && <div className="pagination"><button className="page-btn" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>Prev</button><span className="page-info">Page {page} of {images.pages}</span><button className="page-btn" onClick={() => setPage((p) => Math.min(images.pages, p + 1))} disabled={page === images.pages}>Next</button></div>}
                </>
            )}
            {selected && (
                <div className="lightbox-overlay" onClick={() => setSelected(null)}>
                    <div className="lightbox-content card" onClick={(e) => e.stopPropagation()}>
                        <div className="card-header" style={{ justifyContent: 'space-between' }}>
                            <h3>{displayImageName(selected)}</h3>
                            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                <label style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.3rem', cursor: 'pointer' }}>
                                    <input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} /> Boxes
                                </label>
                                <button className="btn btn-outline" onClick={goPrev} disabled={selectedIdx <= 0}>← Prev</button>
                                <button className="btn btn-outline" onClick={goNext} disabled={selectedIdx >= sortedItems.length - 1}>Next →</button>
                                <button className="btn btn-outline" onClick={() => setSelected(null)}>Close</button>
                            </div>
                        </div>
                        <div className="card-body">
                            <div style={{ position: 'relative', display: 'inline-block', marginBottom: '1rem', width: '100%', textAlign: 'center' }}>
                                <img src={storageUrl(selected.file_path)} alt={selected.filename} style={{ maxWidth: '100%', maxHeight: '65vh', borderRadius: 8, display: 'block', margin: '0 auto' }}
                                    onLoad={(e) => {
                                        const img = e.currentTarget;
                                        const wrapper = img.parentElement;
                                        if (wrapper) {
                                            wrapper.style.width = img.offsetWidth + 'px';
                                            wrapper.style.margin = '0 auto';
                                        }
                                    }}
                                />
                                {showBoxes && detections.map((det) => (
                                    <div
                                        key={det.id}
                                        className="detection-bbox-overlay"
                                        onClick={() => setFocusedDetId(det.id)}
                                        title="Click to focus this detection"
                                        style={{
                                        position: 'absolute',
                                        left: `${det.bbox_x * 100}%`,
                                        top: `${det.bbox_y * 100}%`,
                                        width: `${det.bbox_w * 100}%`,
                                        height: `${det.bbox_h * 100}%`,
                                        border: det.id === focusedDetId ? '3px solid #3b82f6' : '2px solid #00ff88',
                                        borderRadius: 3,
                                        cursor: 'pointer',
                                    }}>
                                        <span className="detection-bbox-label" style={{
                                            position: 'absolute',
                                            top: -22,
                                            left: -2,
                                            background: 'rgba(0,255,136,0.85)',
                                            color: '#000',
                                            fontSize: '0.65rem',
                                            fontWeight: 700,
                                            padding: '1px 5px',
                                            borderRadius: '3px 3px 0 0',
                                            whiteSpace: 'nowrap',
                                            lineHeight: '18px',
                                            backgroundColor: det.id === focusedDetId ? 'rgba(59,130,246,0.9)' : 'rgba(0,255,136,0.85)',
                                        }}>
                                            {det.species || det.category || 'animal'} — AWC135: {det.classification_confidence != null ? (det.classification_confidence * 100).toFixed(1) + '%' : 'N/A'}
                                        </span>
                                    </div>
                                ))}
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
                                <span className="tag tag-muted">Image #{selected.id}</span>
                                {selected.processed ? <span className="tag tag-primary">Processed</span> : <span className="tag tag-muted">Pending</span>}
                                {selected.has_animal === true && <span className="tag tag-info">Has Animal</span>}
                                {selected.has_animal === false && <span className="tag tag-muted">Empty</span>}
                                {selected.camera_id && <span className="tag tag-info">Cam {selected.camera_id}</span>}
                            </div>
                            {detections.length > 0 && (
                                <div style={{ marginBottom: '1rem' }}>
                                    <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.4rem' }}>Detections ({detections.length})</div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                                        {detections.map((det) => (
                                            <button
                                                key={det.id}
                                                className={det.id === focusedDetId ? 'tag tag-info' : 'tag tag-primary'}
                                                style={{ fontSize: '0.7rem', border: 0, cursor: 'pointer' }}
                                                onClick={() => setFocusedDetId(det.id)}
                                            >
                                                #{det.id} {det.species || 'unknown'} — {det.classification_confidence != null ? (det.classification_confidence * 100).toFixed(1) + '%' : 'N/A'}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {isQuoll && (
                                <div className="card" style={{ marginBottom: '1rem' }}>
                                    <div className="card-header" style={{ justifyContent: 'space-between' }}>
                                        <h3 style={{ margin: 0 }}>Manual re-ID</h3>
                                        {focused ? <span className="tag tag-muted">Focused detection #{focused.id}</span> : <span className="tag tag-muted">Select a detection</span>}
                                    </div>
                                    <div className="card-body">
                                        {!user && (
                                            <div className="tag tag-muted" style={{ marginBottom: '0.75rem' }}>
                                                Login required to save assignments / create profiles.
                                            </div>
                                        )}
                                        {focused && (
                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center', marginBottom: '0.75rem' }}>
                                                <span className="tag tag-primary">{focused.species || 'unknown'}</span>
                                                {currentAssigned ? <span className="tag tag-info">Assigned: {currentAssigned}</span> : <span className="tag tag-muted">Unassigned</span>}
                                            </div>
                                        )}

                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0.75rem', minWidth: 0 }}>
                                            {/* Assign row */}
                                            <div>
                                                <div style={{ fontSize: '0.8rem', fontWeight: 700, marginBottom: 6 }}>Assign to existing ID</div>
                                                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                                                    <input
                                                        className="filter-select"
                                                        style={{ flex: '1 1 160px', minWidth: 100 }}
                                                        value={assignId}
                                                        onChange={(e) => setAssignId(e.target.value)}
                                                        placeholder="e.g. 02Q2"
                                                        disabled={!focused || savingAssign}
                                                    />
                                                    <button
                                                        className="btn btn-primary"
                                                        disabled={!focused || !assignId.trim() || savingAssign}
                                                        onClick={async () => {
                                                            if (!focused) return;
                                                            setSavingAssign(true);
                                                            setAssignMsg(null);
                                                            try {
                                                                await createAnnotation({
                                                                    detection_id: focused.id,
                                                                    is_correct: true,
                                                                    individual_id: assignId.trim(),
                                                                    notes: assignNotes.trim() || undefined,
                                                                });
                                                                setAssignMsg(`Assigned detection #${focused.id} → ${assignId.trim()}`);
                                                                setCompareId(assignId.trim());
                                                                await refreshSelectedDetail();
                                                            } catch (e: any) {
                                                                setAssignMsg(e?.message || 'Failed to assign');
                                                            }
                                                            setSavingAssign(false);
                                                        }}
                                                    >
                                                        {savingAssign ? 'Saving…' : 'Assign'}
                                                    </button>
                                                    <button className="btn btn-outline" onClick={() => { setCreateOpen(true); setCreateMsg(null); }} disabled={!focused}>
                                                        Create new profile…
                                                    </button>
                                                </div>
                                                <div style={{ marginTop: 8 }}>
                                                    <textarea
                                                        className="filter-select"
                                                        style={{ width: '100%', minHeight: 44, boxSizing: 'border-box' }}
                                                        value={assignNotes}
                                                        onChange={(e) => setAssignNotes(e.target.value)}
                                                        placeholder="Notes (optional)"
                                                        disabled={savingAssign}
                                                    />
                                                </div>
                                                {assignMsg && <div className="tag tag-muted" style={{ marginTop: 8 }}>{assignMsg}</div>}
                                            </div>

                                            {/* Reference comparison — constrained so gallery scrolls inside, never stretches the card */}
                                            <div style={{ minWidth: 0, overflow: 'hidden' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: 6, flexWrap: 'wrap' }}>
                                                    <span style={{ fontSize: '0.8rem', fontWeight: 700, whiteSpace: 'nowrap' }}>Reference comparison</span>
                                                    <select
                                                        className="filter-select"
                                                        value={compareId}
                                                        onChange={(e) => setCompareId(e.target.value)}
                                                        disabled={indsLoading}
                                                        style={{ flex: '1 1 180px', minWidth: 120, fontSize: '0.8rem' }}
                                                    >
                                                        <option value="">Pick an individual…</option>
                                                        {individuals.map((i) => (
                                                            <option key={i.individual_id} value={i.individual_id}>
                                                                {i.individual_id}
                                                            </option>
                                                        ))}
                                                    </select>
                                                </div>
                                                {!compareId ? (
                                                    <div className="empty-state" style={{ padding: '0.5rem 0.75rem' }}>Pick an individual above to compare.</div>
                                                ) : compareLoading ? (
                                                    <div className="empty-state" style={{ padding: '0.5rem 0.75rem' }}>Loading gallery…</div>
                                                ) : compareGallery.length === 0 ? (
                                                    <div className="empty-state" style={{ padding: '0.5rem 0.75rem' }}>No gallery items for {compareId}.</div>
                                                ) : (
                                                    <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 8, width: '100%', boxSizing: 'border-box' }}>
                                                        {compareGallery.slice(0, 40).map((it) => (
                                                            <div key={`${it.image_id}-${it.detection_id ?? 'img'}`} style={{ flex: '0 0 110px' }}>
                                                                <img
                                                                    src={it.display_url || it.thumb_url || ''}
                                                                    alt=""
                                                                    style={{ width: 110, height: 80, objectFit: 'cover', borderRadius: 6, border: '1px solid rgba(0,0,0,0.15)', display: 'block' }}
                                                                />
                                                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, whiteSpace: 'nowrap' }}>
                                                                    {it.captured_at ? String(it.captured_at).slice(0, 10) : '—'}
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {createOpen && (
                                <div className="lightbox-overlay" onClick={() => setCreateOpen(false)} style={{ background: 'rgba(0,0,0,0.35)' }}>
                                    <div className="lightbox-content card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 720 }}>
                                        <div className="card-header" style={{ justifyContent: 'space-between' }}>
                                            <h3 style={{ margin: 0 }}>Create new individual profile</h3>
                                            <button className="btn btn-outline" onClick={() => setCreateOpen(false)}>Close</button>
                                        </div>
                                        <div className="card-body">
                                            {!focused ? (
                                                <div className="empty-state">Select a detection first.</div>
                                            ) : (
                                                <>
                                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                                                        <div>
                                                            <div style={{ fontSize: '0.8rem', fontWeight: 700, marginBottom: 6 }}>New ID</div>
                                                            <input className="filter-select" value={newIndividualId} onChange={(e) => setNewIndividualId(e.target.value)} placeholder="e.g. 09Q3" />
                                                        </div>
                                                        <div>
                                                            <div style={{ fontSize: '0.8rem', fontWeight: 700, marginBottom: 6 }}>Name (optional)</div>
                                                            <input className="filter-select" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="nickname" />
                                                        </div>
                                                    </div>
                                                    <div className="tag tag-muted" style={{ marginBottom: 10 }}>
                                                        Choose reference detections. You can navigate images (Prev/Next) while this dialog is open, then click a box to focus it and set it as Left/Right reference.
                                                    </div>
                                                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
                                                        <button className="btn btn-outline" onClick={() => setRefLeft(focused.id)} disabled={createBusy}>Use focused as LEFT ref</button>
                                                        <button className="btn btn-outline" onClick={() => setRefRight(focused.id)} disabled={createBusy}>Use focused as RIGHT ref</button>
                                                        {refLeft != null ? <span className="tag tag-info">Left: #{refLeft}</span> : <span className="tag tag-muted">Left: not set</span>}
                                                        {refRight != null ? <span className="tag tag-info">Right: #{refRight}</span> : <span className="tag tag-muted">Right: not set</span>}
                                                    </div>
                                                    {createMsg && <div className="tag tag-muted" style={{ marginBottom: 10 }}>{createMsg}</div>}
                                                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                                                        <button
                                                            className="btn btn-primary"
                                                            disabled={createBusy || !newIndividualId.trim() || refLeft == null || refRight == null}
                                                            onClick={async () => {
                                                                if (!focused) return;
                                                                setCreateBusy(true);
                                                                setCreateMsg(null);
                                                                try {
                                                                    await createIndividual({
                                                                        individual_id: newIndividualId.trim(),
                                                                        species: decoded || 'Spotted-tailed Quoll',
                                                                        name: newName.trim() || undefined,
                                                                        ref_left_detection_id: refLeft!,
                                                                        ref_right_detection_id: refRight!,
                                                                    });
                                                                    await createAnnotation({
                                                                        detection_id: focused.id,
                                                                        is_correct: true,
                                                                        individual_id: newIndividualId.trim(),
                                                                        notes: `Created profile (left=${refLeft}, right=${refRight})`,
                                                                    });
                                                                    setCreateMsg(`Created ${newIndividualId.trim()} and assigned current detection.`);
                                                                    setCompareId(newIndividualId.trim());
                                                                    await refreshSelectedDetail();
                                                                    setCreateOpen(false);
                                                                } catch (e: any) {
                                                                    setCreateMsg(e?.message || 'Failed to create profile');
                                                                }
                                                                setCreateBusy(false);
                                                            }}
                                                        >
                                                            {createBusy ? 'Creating…' : 'Create profile + assign'}
                                                        </button>
                                                        <button className="btn btn-outline" onClick={() => { setRefLeft(null); setRefRight(null); }} disabled={createBusy}>Clear refs</button>
                                                    </div>
                                                </>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}
                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                                <Link to={`/review-image/${selected.id}`} className="btn btn-primary">Review Image</Link>
                            </div>
                            <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '0.75rem' }}>Use ←/→ to navigate, Esc to close</div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

function QuollIndividualCardLink({ speciesKey, ind }: { speciesKey: string; ind: IndividualData }) {
    const [preview, setPreview] = useState<string | null>(null);
    useEffect(() => {
        let cancelled = false;
        fetchIndividualGallery(ind.individual_id)
            .then((g) => {
                if (!cancelled) setPreview(g.items[0]?.display_url ?? null);
            })
            .catch(() => {
                if (!cancelled) setPreview(null);
            });
        return () => {
            cancelled = true;
        };
    }, [ind.individual_id]);

    return (
        <Link
            to={`/individuals/species/${speciesKey}/individuals/${encodeURIComponent(ind.individual_id)}`}
            className="wt-quoll-card"
        >
            <div className="wt-quoll-card-image">
                {preview ? (
                    <img src={preview} alt="" loading="lazy" />
                ) : (
                    <div className="wt-quoll-card-placeholder">🐾</div>
                )}
            </div>
            <div className="wt-quoll-card-body">
                <div className="wt-quoll-card-id">{ind.individual_id}</div>
                <div className="wt-quoll-card-meta">{ind.species}</div>
                <div className="wt-quoll-card-stats">
                    <span>{ind.total_sightings} sightings</span>
                </div>
            </div>
        </Link>
    );
}

function SpeciesByIndividual() {
    const { speciesKey } = useParams();
    const decoded = speciesKey ? decodeURIComponent(speciesKey).replace(/-/g, ' ') : '';
    const [individuals, setIndividuals] = useState<IndividualData[]>([]);
    const [loading, setLoading] = useState(true);
    const [reidRuntime, setReidRuntime] = useState<Record<string, unknown> | null>(null);

    useEffect(() => {
        fetchIndividuals()
            .then((list) => setIndividuals(list.filter((i) => individualMatchesSpeciesPage(i, decoded))))
            .finally(() => setLoading(false));
    }, [decoded]);

    useEffect(() => {
        fetchReidInfo()
            .then((info) => {
                const r = info.runtime;
                setReidRuntime(r !== null && typeof r === 'object' ? (r as Record<string, unknown>) : null);
            })
            .catch(() => setReidRuntime(null));
    }, []);

    if (loading) return <LoadingState />;
    return (
        <div className="wt-individuals-list-page">
            <nav className="breadcrumb">
                <Link to="/">Home</Link>
                <span className="sep">›</span>
                <Link to="/individuals">Profiles</Link>
                <span className="sep">›</span>
                <Link to={`/individuals/species/${speciesKey}`}>{decoded}</Link>
                <span className="sep">›</span>
                <span>Individuals</span>
            </nav>
            <div className="page-header">
                <h2 style={{ color: WT_GREEN }}>Individuals — {decoded}</h2>
                <p className="text-muted">Select a quoll to open its profile (WildlifeTracker-style).</p>
            </div>
            {individuals.length === 0 ? (
                <div className="card" style={{ padding: '1.5rem', maxWidth: 720 }}>
                    <h3 style={{ marginTop: 0 }}>No individuals listed yet</h3>
                    {Boolean(reidRuntime?.auto_assign_enabled) ? (
                        <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                            The worker is configured to <strong>auto-assign</strong> quoll IDs from your MegaDescriptor gallery
                            when images are processed (MD → AWC quoll → crop → re-ID). If you uploaded before the gallery
                            existed, re-run processing for those images or upload again. IDs must pass the similarity / gap
                            gate (see <Link to="/individuals">Profiles</Link> Notes tab or <code>GET /api/reid/info</code>).
                        </p>
                    ) : (
                        <>
                            <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                                <strong>Automatic pipeline:</strong> train a prototype gallery with{' '}
                                <code>scripts/reid_megadescriptor_hf_mvp.py</code> and save it to{' '}
                                <code>{String(reidRuntime?.gallery_path ?? 'storage/models/megadescriptor_l384_gallery.pt')}</code>
                                {reidRuntime?.gallery_exists === false ? (
                                    <> (file not found yet — cards appear after the gallery exists and new quoll images are processed).</>
                                ) : (
                                    <>; then process images so quoll crops get annotations automatically.</>
                                )}
                            </p>
                            <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                                You can still assign a quoll individual ID manually in{' '}
                                <Link to="/pending-review">Review</Link> (e.g. <code>02Q2</code>); those merge into this list.
                            </p>
                        </>
                    )}
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                        CSV import of individuals/sightings is supported separately if you use that workflow.
                    </p>
                </div>
            ) : (
                <div className="wt-quoll-card-grid">
                    {individuals.map((ind) => (
                        <QuollIndividualCardLink key={ind.individual_id} speciesKey={speciesKey!} ind={ind} />
                    ))}
                </div>
            )}
        </div>
    );
}

/* ============================================================
   INDIVIDUAL PROFILE PAGE (WildlifeTracker-style)
   ============================================================ */
function IndividualImages() {
    const { speciesKey, individualId } = useParams();
    const decodedId = individualId ? decodeURIComponent(individualId) : '';
    const decodedSpecies = speciesKey ? decodeURIComponent(speciesKey).replace(/-/g, ' ') : '';

    const [individual, setIndividual] = useState<IndividualData | null>(null);
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState<'overview' | 'images' | 'movement' | 'notes'>('images');
    const [gallery, setGallery] = useState<IndividualGalleryItem[]>([]);
    const [galLoading, setGalLoading] = useState(true);
    const [galSource, setGalSource] = useState<string>('');
    const [reidInfo, setReidInfo] = useState<Record<string, unknown> | null>(null);

    useEffect(() => {
        fetchIndividuals()
            .then((list) => {
                const found = list.find((i) => i.individual_id === decodedId);
                setIndividual(found || null);
            })
            .catch(() => {})
            .finally(() => setLoading(false));
    }, [decodedId]);

    useEffect(() => {
        if (!decodedId) return;
        setGalLoading(true);
        fetchIndividualGallery(decodedId)
            .then((g) => {
                setGallery(g.items);
                setGalSource(g.source);
            })
            .catch(() => {
                setGallery([]);
                setGalSource('');
            })
            .finally(() => setGalLoading(false));
    }, [decodedId]);

    useEffect(() => {
        fetchReidInfo().then(setReidInfo).catch(() => setReidInfo(null));
    }, []);

    if (loading) return <LoadingState />;

    let daysActive = '—';
    if (individual?.first_seen && individual?.last_seen) {
        const first = new Date(individual.first_seen).getTime();
        const last = new Date(individual.last_seen).getTime();
        const diffDays = Math.ceil((last - first) / (1000 * 3600 * 24));
        daysActive = diffDays === 0 ? '1 Day' : `${diffDays} Days`;
    }

    const mapCenter: [number, number] = [-34.4, 150.3];
    const heroSrc = gallery[0]?.display_url ?? null;
    const gridSlots: (IndividualGalleryItem | null)[] = [...gallery.slice(0, 12)];
    while (gridSlots.length < 12) gridSlots.push(null);

    const commonName = 'Spotted-tailed Quoll';

    return (
        <div className="wt-individual-page">
            <nav className="breadcrumb wt-breadcrumb">
                <Link to="/">Home</Link>
                <span className="sep">›</span>
                <Link to="/individuals">Profiles</Link>
                <span className="sep">›</span>
                <Link to={`/individuals/species/${speciesKey}`}>{decodedSpecies}</Link>
                <span className="sep">›</span>
                <Link to={`/individuals/species/${speciesKey}/individuals`}>Individuals</Link>
                <span className="sep">›</span>
                <span className="wt-breadcrumb-current">{decodedId}</span>
            </nav>

            {!individual && (
                <div className="wt-banner-warn">
                    This individual ID is not in the database list yet; sightings gallery may be empty until data is
                    linked.
                </div>
            )}

            <section className="wt-profile-hero">
                <div className="wt-profile-hero-text">
                    <h1 className="wt-profile-title">
                        {commonName} — <strong>{decodedId}</strong>
                    </h1>
                    <p className="wt-profile-lead">{SPOTTED_QUOLL_OVERVIEW}</p>
                </div>
                <div className="wt-profile-hero-photo">
                    {heroSrc ? (
                        <img src={heroSrc} alt={`${decodedId}`} className="wt-hero-main-img" />
                    ) : (
                        <div className="wt-hero-main-placeholder">📷 No image yet</div>
                    )}
                </div>
                <aside className="wt-profile-sidebar">
                    <div className="wt-sidebar-thumb">
                        {heroSrc ? <img src={heroSrc} alt="" /> : <span>🐾</span>}
                    </div>
                    <h3 className="wt-sidebar-heading">Taxonomy</h3>
                    <ul className="wt-taxonomy-list">
                        <li>
                            <span className="k">Genus</span> <em>Dasyurus</em>
                        </li>
                        <li>
                            <span className="k">Species</span> <em>maculatus</em>
                        </li>
                        <li>
                            <span className="k">Family</span> Dasyuridae
                        </li>
                        <li>
                            <span className="k">Order</span> Dasyuromorphia
                        </li>
                    </ul>
                    <p className="wt-size-line">
                        <span className="wt-paw">🐾</span> Size range (typical): 35 cm – 75 cm
                    </p>
                    <div className="wt-sidebar-actions">
                        <Link to="/images" className="wt-btn wt-btn-primary">
                            ↑ Upload Pic
                        </Link>
                        <button type="button" className="wt-btn wt-btn-outline" disabled title="Demo placeholder">
                            ♥ Like
                        </button>
                    </div>
                </aside>
            </section>

            <div className="wt-tab-shell">
                <div className="wt-tab-header">
                    <div className="wt-tab-id">
                        <span className="wt-tab-icon">🦊</span>
                        <span>
                            <strong>{decodedId}</strong>
                            <span className="wt-tab-species">{commonName}</span>
                        </span>
                    </div>
                    <div className="wt-tabs">
                        {(['overview', 'images', 'movement', 'notes'] as const).map((t) => (
                            <button
                                key={t}
                                type="button"
                                className={`wt-tab ${tab === t ? 'active' : ''}`}
                                onClick={() => setTab(t)}
                            >
                                {t === 'overview' && 'Overview'}
                                {t === 'images' && 'Images'}
                                {t === 'movement' && 'Movement Tracking'}
                                {t === 'notes' && 'Notes'}
                            </button>
                        ))}
                    </div>
                </div>
                <div className="wt-tab-body">
                    {tab === 'overview' && (
                        <div className="wt-overview">
                            <p>{SPOTTED_QUOLL_OVERVIEW}</p>
                            <div className="wt-mini-stats">
                                <div>
                                    <div className="lbl">Sightings</div>
                                    <div className="val">{individual?.total_sightings ?? gallery.length}</div>
                                </div>
                                <div>
                                    <div className="lbl">First seen</div>
                                    <div className="val">
                                        {individual?.first_seen
                                            ? new Date(individual.first_seen).toLocaleDateString()
                                            : '—'}
                                    </div>
                                </div>
                                <div>
                                    <div className="lbl">Last seen</div>
                                    <div className="val">
                                        {individual?.last_seen
                                            ? new Date(individual.last_seen).toLocaleDateString()
                                            : '—'}
                                    </div>
                                </div>
                                <div>
                                    <div className="lbl">Days tracked</div>
                                    <div className="val">{daysActive}</div>
                                </div>
                            </div>
                        </div>
                    )}
                    {tab === 'images' && (
                        <div>
                            {galLoading ? (
                                <LoadingState />
                            ) : gallery.length === 0 ? (
                                <EmptyMsg text="No linked images yet. Assign this individual to detections in Review, or import sightings." />
                            ) : (
                                <>
                                    <p className="wt-gallery-hint">
                                        Source: <code>{galSource || '—'}</code> · {gallery.length} image(s)
                                    </p>
                                    <div className="wt-image-grid-12">
                                        {gridSlots.map((item, idx) => (
                                            <div key={item ? `${item.image_id}-${item.detection_id}` : `ph-${idx}`} className="wt-grid-cell">
                                                {item?.display_url ? (
                                                    <Link to={`/review-image/${item.image_id}`} className="wt-grid-link">
                                                        <img src={item.display_url} alt="" loading="lazy" />
                                                        {item.captured_at && (
                                                            <span className="wt-grid-cap">
                                                                {new Date(item.captured_at).toLocaleDateString()}
                                                            </span>
                                                        )}
                                                    </Link>
                                                ) : (
                                                    <div className="wt-grid-placeholder">📷</div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </>
                            )}
                        </div>
                    )}
                    {tab === 'movement' && (
                        <div>
                            <p className="wt-map-caption">Placeholder territory map (camera coordinates can be wired later).</p>
                            <div className="wt-map-wrap">
                                <MapContainer center={mapCenter} zoom={11} style={{ height: '320px', width: '100%', zIndex: 1 }}>
                                    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="OSM" />
                                    <Marker position={mapCenter}>
                                        <Popup>
                                            <strong>{decodedId}</strong>
                                            <br />
                                            {individual?.last_seen
                                                ? new Date(individual.last_seen).toLocaleDateString()
                                                : 'Sighting'}
                                        </Popup>
                                    </Marker>
                                </MapContainer>
                            </div>
                        </div>
                    )}
                    {tab === 'notes' && (
                        <div className="wt-notes">
                            <h3>Re-identification (prototype)</h3>
                            <p>
                                Offline embeddings (MegaDescriptor-L-384) support matching new crops to known
                                individuals. The API exposes a short summary for demos — no GPU required on the server.
                            </p>
                            {reidInfo && (
                                <ul className="wt-reid-list">
                                    {typeof reidInfo.model_name === 'string' && (
                                        <li>
                                            <strong>Model:</strong> {reidInfo.model_name}
                                        </li>
                                    )}
                                    {typeof reidInfo.metrics_closed_set_rank1 === 'string' && (
                                        <li>
                                            <strong>Rank-1 (typical):</strong> {reidInfo.metrics_closed_set_rank1}
                                        </li>
                                    )}
                                    {typeof reidInfo.metrics_with_unknown_gate === 'string' && (
                                        <li>
                                            <strong>With UNKNOWN gate:</strong> {reidInfo.metrics_with_unknown_gate}
                                        </li>
                                    )}
                                    {Array.isArray(reidInfo.why_not_higher) && (
                                        <li>
                                            <strong>Why accuracy is limited:</strong>
                                            <ul>
                                                {(reidInfo.why_not_higher as string[]).map((line) => (
                                                    <li key={line.slice(0, 40)}>{line}</li>
                                                ))}
                                            </ul>
                                        </li>
                                    )}
                                </ul>
                            )}
                            <p className="wt-doc-hint">
                                Full narrative for your professor: <code>docs/REID_MODEL_RESULTS.md</code> in the repo.
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </div>
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
            <AdminPage embedded />
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
        <div style={{ 
            minHeight: '100vh', 
            background: 'linear-gradient(135deg, #f0fdf4 0%, #e8f5e9 50%, #f0fdf4 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '2rem'
        }}>
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
                gap: '2rem',
                maxWidth: '900px',
                width: '100%',
                alignItems: 'center'
            }}>
                {/* Left Side - Branding & Features */}
                <div style={{
                    background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                    borderRadius: '16px',
                    padding: '3rem 2rem',
                    color: 'white',
                    boxShadow: '0 20px 60px rgba(16, 185, 129, 0.15)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    minHeight: '500px',
                    order: window.innerWidth < 768 ? 2 : 1
                }}>
                    <div>
                        <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🌿</div>
                        <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '0.5rem', lineHeight: '1.2' }}>
                            Wildlife AI Platform
                        </h1>
                        <p style={{ fontSize: '0.95rem', opacity: 0.9, marginBottom: '2rem' }}>
                            Advanced wildlife monitoring and conservation technology
                        </p>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        {[
                            { icon: '🎯', text: 'AI-Powered Detection' },
                            { icon: '📊', text: 'Real-time Analytics' },
                            { icon: '🔒', text: 'Secure & Reliable' }
                        ].map((item, i) => (
                            <div key={i} style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                                <div style={{ fontSize: '1.5rem' }}>{item.icon}</div>
                                <p style={{ margin: 0, fontSize: '0.9rem', fontWeight: '500' }}>{item.text}</p>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Right Side - Form */}
                <div style={{
                    background: 'white',
                    borderRadius: '16px',
                    padding: '2.5rem',
                    boxShadow: '0 20px 60px rgba(0, 0, 0, 0.08)',
                    order: window.innerWidth < 768 ? 1 : 2
                }}>
                    {/* Tab Buttons */}
                    <div style={{ 
                        display: 'flex', 
                        gap: '0.75rem', 
                        marginBottom: '2rem',
                        background: '#f3f4f6',
                        padding: '0.5rem',
                        borderRadius: '10px'
                    }}>
                        {['login', 'register'].map((t) => (
                            <button
                                key={t}
                                onClick={() => setTab(t as 'login' | 'register')}
                                style={{
                                    flex: 1,
                                    padding: '0.75rem 1rem',
                                    border: 'none',
                                    borderRadius: '8px',
                                    fontSize: '0.95rem',
                                    fontWeight: '600',
                                    cursor: 'pointer',
                                    transition: 'all 0.3s ease',
                                    background: tab === t ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : 'transparent',
                                    color: tab === t ? 'white' : '#6b7280'
                                }}
                            >
                                {t === 'login' ? '🔐 Sign In' : '✨ Register'}
                            </button>
                        ))}
                    </div>

                    {/* Form Title */}
                    <div style={{ marginBottom: '2rem' }}>
                        <h2 style={{ fontSize: '1.5rem', fontWeight: '700', color: '#1f2937', margin: '0 0 0.5rem 0' }}>
                            {tab === 'login' ? 'Welcome Back' : 'Join Us'}
                        </h2>
                        <p style={{ color: '#6b7280', margin: 0, fontSize: '0.9rem' }}>
                            {tab === 'login' ? 'Sign in to your account to continue' : 'Create a new account to get started'}
                        </p>
                    </div>

                    {/* Form */}
                    <form onSubmit={tab === 'login' ? handleLogin : handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                        {tab === 'register' && (
                            <div>
                                <label style={{ fontSize: '0.85rem', fontWeight: '600', display: 'block', marginBottom: '0.5rem', color: '#374151' }}>
                                    👤 Full Name
                                </label>
                                <input 
                                    type="text"
                                    value={fullName} 
                                    onChange={(e) => setFullName(e.target.value)}
                                    placeholder="John Doe"
                                    style={{
                                        width: '100%',
                                        padding: '0.875rem 1rem',
                                        border: '2px solid #e5e7eb',
                                        borderRadius: '8px',
                                        fontSize: '0.9rem',
                                        transition: 'all 0.3s ease',
                                        boxSizing: 'border-box',
                                        outline: 'none'
                                    }}
                                    onFocus={(e) => e.target.style.borderColor = '#10b981'}
                                    onBlur={(e) => e.target.style.borderColor = '#e5e7eb'}
                                />
                            </div>
                        )}

                        <div>
                            <label style={{ fontSize: '0.85rem', fontWeight: '600', display: 'block', marginBottom: '0.5rem', color: '#374151' }}>
                                📧 Email Address
                            </label>
                            <input 
                                type="email" 
                                value={email} 
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="you@example.com"
                                required
                                style={{
                                    width: '100%',
                                    padding: '0.875rem 1rem',
                                    border: '2px solid #e5e7eb',
                                    borderRadius: '8px',
                                    fontSize: '0.9rem',
                                    transition: 'all 0.3s ease',
                                    boxSizing: 'border-box',
                                    outline: 'none'
                                }}
                                onFocus={(e) => e.target.style.borderColor = '#10b981'}
                                onBlur={(e) => e.target.style.borderColor = '#e5e7eb'}
                            />
                        </div>

                        <div>
                            <label style={{ fontSize: '0.85rem', fontWeight: '600', display: 'block', marginBottom: '0.5rem', color: '#374151' }}>
                                🔑 Password
                            </label>
                            <input 
                                type="password" 
                                value={password} 
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                required 
                                minLength={8}
                                style={{
                                    width: '100%',
                                    padding: '0.875rem 1rem',
                                    border: '2px solid #e5e7eb',
                                    borderRadius: '8px',
                                    fontSize: '0.9rem',
                                    transition: 'all 0.3s ease',
                                    boxSizing: 'border-box',
                                    outline: 'none'
                                }}
                                onFocus={(e) => e.target.style.borderColor = '#10b981'}
                                onBlur={(e) => e.target.style.borderColor = '#e5e7eb'}
                            />
                        </div>

                        {tab === 'register' && (
                            <div>
                                <label style={{ fontSize: '0.85rem', fontWeight: '600', display: 'block', marginBottom: '0.5rem', color: '#374151' }}>
                                    👨‍💼 Role
                                </label>
                                <select 
                                    value={role} 
                                    onChange={(e) => setRole(e.target.value)}
                                    style={{
                                        width: '100%',
                                        padding: '0.875rem 1rem',
                                        border: '2px solid #e5e7eb',
                                        borderRadius: '8px',
                                        fontSize: '0.9rem',
                                        transition: 'all 0.3s ease',
                                        boxSizing: 'border-box',
                                        outline: 'none',
                                        cursor: 'pointer'
                                    }}
                                    onFocus={(e) => e.currentTarget.style.borderColor = '#10b981'}
                                    onBlur={(e) => e.currentTarget.style.borderColor = '#e5e7eb'}
                                >
                                    <option value="reviewer">👁️ Reviewer</option>
                                    <option value="researcher">🔬 Researcher</option>
                                    <option value="admin">⚙️ Admin</option>
                                </select>
                            </div>
                        )}

                        {error && (
                            <div style={{
                                background: '#fee2e2',
                                border: '2px solid #fca5a5',
                                borderRadius: '8px',
                                padding: '0.75rem 1rem',
                                fontSize: '0.85rem',
                                color: '#991b1b'
                            }}>
                                ⚠️ {error}
                            </div>
                        )}

                        <button 
                            type="submit" 
                            disabled={loading}
                            style={{
                                padding: '0.875rem 1.5rem',
                                border: 'none',
                                borderRadius: '8px',
                                fontSize: '0.95rem',
                                fontWeight: '700',
                                cursor: loading ? 'not-allowed' : 'pointer',
                                background: loading ? '#d1d5db' : 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                                color: 'white',
                                transition: 'all 0.3s ease',
                                marginTop: '0.5rem',
                                boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)',
                                opacity: loading ? 0.7 : 1
                            }}
                            onMouseEnter={(e) => !loading && (e.currentTarget.style.boxShadow = '0 8px 20px rgba(16, 185, 129, 0.4)')}
                            onMouseLeave={(e) => !loading && (e.currentTarget.style.boxShadow = '0 4px 12px rgba(16, 185, 129, 0.3)')}
                        >
                            {loading ? '⏳ Please wait...' : tab === 'login' ? ' Sign In' : ' Create Account'}
                        </button>
                    </form>

                    {/* Footer */}
                    <div style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.85rem', color: '#6b7280' }}>
                        {tab === 'login' ? (
                            <p>Don't have an account? <span style={{ color: '#10b981', fontWeight: '600', cursor: 'pointer' }} onClick={() => setTab('register')}>Register here</span></p>
                        ) : (
                            <p>Already have an account? <span style={{ color: '#10b981', fontWeight: '600', cursor: 'pointer' }} onClick={() => setTab('login')}>Sign in here</span></p>
                        )}
                    </div>
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
