import { useState, useEffect, useRef, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation, useParams, Navigate } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, CartesianGrid } from 'recharts';
import L from 'leaflet';
import { AuthProvider, useAuth } from './auth';
import {
    fetchStats, fetchImages, fetchIndividuals, fetchCollectionStats, fetchCameraStats,
    fetchSpeciesCounts, fetchReport, fetchDetectionDetail, fetchAnnotations, fetchDetections,
    createAnnotation, uploadBatch, fetchJobStatus, fetchUsers, changeUserRole,
    fetchSystemMetrics, register, getExportUrl, getQuollExportUrl, getMetadataExportUrl, fetchImagesBySpecies, fetchImageDetail,
    storageUrl, createMissedDetection,
    type DashboardStats, type ImageData, type IndividualData, type CollectionStat,
    type CameraStat, type SpeciesCount, type PaginatedResponse, type ReportData,
    type DetectionDetail, type AnnotationData, type JobStatus, type UserData, type Detection,
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
                    
                    {/* NEW ADMIN ROUTE ADDED HERE */}
                    <Route path="/admin" element={<RequireAuth role="admin"><AdminDashboard /></RequireAuth>} />
                    
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
    HEADER 
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
        { path: '/admin', label: 'Admin' }, // Added Admin to Nav
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
                        className={`nav-link ${loc.pathname === item.path || (item.path === '/pending-review' && loc.pathname.startsWith('/review')) ? 'active' : ''}`}
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
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden style={{width: 24, height: 24, marginRight: 8}}>
            <path d="M17 8C8 10 5.9 16.17 3.82 21.34L5.71 22L6.66 19.7C7.14 18.66 7.5 17.59 7.77 16.5C8.5 18 9.5 19.5 10.5 20.5C11.5 21.5 13 22 15 22C19 22 22 19 22 15C22 12 20.5 9.5 18 8C17 8 17 8 17 8Z" />
        </svg>
    );
}

/* ============================================================
    ADMIN DASHBOARD COMPONENT 
   ============================================================ */
function AdminDashboard() {
    const [data, setData] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetch('http://localhost:8000/api/admin/dashboard-stats')
            .then(res => {
                if (!res.ok) throw new Error("Could not connect to backend");
                return res.json();
            })
            .then(setData)
            .catch(err => setError(err.message));
    }, []);

    if (error) return <ErrorState message={error} />;
    if (!data) return <LoadingState />;

    const accuracyData = [
        { month: 'Jan', acc: 5 }, { month: '2y', acc: 60 }, 
        { month: '5', acc: 45 }, { month: '30', acc: 65 }, 
        { month: 'Der', acc: 80 }, { month: '100', acc: 88 }
    ];

    const pieData = [
        { name: 'Positive', value: 72 }, { name: 'Unverified', value: 28 }
    ];

    const userActivity = [
        { name: 'Normal User', value: 30 }, 
        { name: 'Camera Traps', value: 20 }, 
        { name: 'UOW Ecologist', value: 40 },
        { name: 'Other', value: 10 }
    ];

    return (
        <div className="admin-dashboard-page">
            <style>{adminStyles}</style>
            <div className="search-container">
                <input type="text" className="search-bar" placeholder="Search sightings, IDs, or locations..." />
            </div>

            <section className="admin-section">
                <h3 className="section-title">Activity</h3>
                <div className="activity-stats-grid">
                    {data.stats.map((s: any, i: number) => (
                        <div key={i} className={`admin-stat-card border-${s.color}`}>
                            <div className={`status-dot dot-${s.color}`}></div>
                            <h2 className="admin-stat-value">{s.value}</h2>
                            <p className="admin-stat-label">{s.label}</p>
                        </div>
                    ))}
                </div>
            </section>

            <section className="admin-section">
                <h3 className="section-title">Recent Sighting</h3>
                <div className="recent-sightings-grid">
                    {data.recent_sightings.map((s: any) => (
                        <div key={s.id} className="admin-quoll-card">
                            <div className="admin-img-wrap">
                                <img src={s.img} alt="Quoll" />
                                <span className="conf-badge">{s.tag}</span>
                            </div>
                            <div className="admin-card-meta">
                                <span className="sighting-id">{s.id}</span>
                                <span className="version-tag">v.1.0</span>
                            </div>
                            <Link to={`/review-image/${s.id.replace('#', '')}`} className="admin-review-btn">Review</Link>
                        </div>
                    ))}
                </div>
                <button className="admin-show-more">Show More</button>
            </section>

            <section className="admin-section">
                <h3 className="section-title">Analytics</h3>
                <div className="analytics-layout">
                    <div className="admin-chart-card">
                        <h4>Identification Accuracy Trend</h4>
                        <div style={{ height: 200 }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={accuracyData}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{fontSize: 10}} />
                                    <YAxis axisLine={false} tickLine={false} tick={{fontSize: 10}} />
                                    <Tooltip />
                                    <Line type="monotone" dataKey="acc" stroke="#2d6a4f" strokeWidth={3} dot={{ r: 4, fill: '#2d6a4f' }} />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                    <div className="admin-chart-card">
                        <h4>Positive vs Unverified Identifications</h4>
                        <div style={{ height: 200, position: 'relative' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={pieData} innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                                        <Cell fill="#2d6a4f" />
                                        <Cell fill="#e0e0e0" />
                                    </Pie>
                                    <Tooltip />
                                </PieChart>
                            </ResponsiveContainer>
                            <div className="chart-overlay-text">72%</div>
                        </div>
                    </div>
                    <div className="admin-chart-card span-full">
                        <h4>User Activity Distribution</h4>
                        <div style={{ height: 250 }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={userActivity} cx="50%" cy="50%" outerRadius={100} fill="#8884d8" dataKey="value" label={({name, value}) => `${name} ${value}%`}>
                                        {userActivity.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                                        ))}
                                    </Pie>
                                    <Tooltip />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
}

const adminStyles = `
    .admin-dashboard-page { padding: 20px; max-width: 1200px; margin: auto; }
    .search-container { text-align: center; margin-bottom: 30px; }
    .search-bar { width: 60%; padding: 12px 25px; border-radius: 25px; border: 1px solid #ddd; background: #fcfcfc; outline: none; }
    .admin-section { margin-bottom: 45px; }
    .section-title { font-size: 20px; font-weight: 600; margin-bottom: 20px; color: #333; }
    .activity-stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
    .admin-stat-card { background: white; padding: 25px 20px; border-radius: 12px; border: 1px solid #eee; position: relative; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }
    .border-green { border-top: 5px solid #2d6a4f; }
    .border-yellow { border-top: 5px solid #ffb703; }
    .border-red { border-top: 5px solid #e63946; }
    .admin-stat-value { font-size: 28px; margin: 0; color: #222; }
    .admin-stat-label { font-size: 11px; color: #888; margin: 5px 0 0; }
    .status-dot { position: absolute; top: 15px; right: 15px; width: 8px; height: 8px; border-radius: 50%; }
    .dot-green { background: #2d6a4f; } .dot-yellow { background: #ffb703; } .dot-red { background: #e63946; }
    .recent-sightings-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
    .admin-quoll-card { background: white; border: 1px solid #eee; border-radius: 10px; padding: 12px; }
    .admin-img-wrap { position: relative; width: 100%; height: 180px; overflow: hidden; border-radius: 6px; }
    .admin-img-wrap img { width: 100%; height: 100%; object-fit: cover; }
    .conf-badge { position: absolute; top: 8px; left: 8px; background: rgba(45,106,79,0.85); color: white; padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; }
    .admin-card-meta { display: flex; justify-content: space-between; margin-top: 10px; font-size: 12px; color: #aaa; }
    .admin-review-btn { display: block; background: #2d6a4f; color: white; text-align: center; text-decoration: none; padding: 10px; border-radius: 6px; margin-top: 12px; font-weight: 600; font-size: 13px; }
    .admin-show-more { width: 100%; background: #2d6a4f; color: white; border: none; padding: 15px; border-radius: 8px; margin-top: 25px; font-weight: bold; cursor: pointer; }
    .analytics-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 25px; }
    .admin-chart-card { background: #fff; border: 1px solid #eee; border-radius: 12px; padding: 20px; position: relative; }
    .admin-chart-card h4 { margin: 0 0 20px; font-size: 14px; color: #444; }
    .span-full { grid-column: span 2; }
    .chart-overlay-text { position: absolute; top: 55%; left: 50%; transform: translate(-50%, -50%); font-size: 24px; font-weight: bold; color: #2d6a4f; }
`;



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
            <div className="footer-bottom">© 2026 WildlifeTracker. All rights reserved.</div>
        </footer>
    );
}

function HelpPage() {
    return (
        <div className="page-header">
            <h2>Help</h2>
            <p>Documentation and support — coming soon.</p>
        </div>
    );
}

function PendingReviewPage() {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [report, setReport] = useState<ReportData | null>(null);
    const [detections, setDetections] = useState<Detection[]>([]);
    const [emptyImages, setEmptyImages] = useState<PaginatedResponse<ImageData> | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [filter, setFilter] = useState<string | null>(null);
    const [search, setSearch] = useState('');
    const [focusSpecies, setFocusSpecies] = useState<'quoll' | 'all'>('quoll');

    useEffect(() => {
        let alive = true;
        const load = async () => {
            setLoading(true);
            try {
                const [s, r, detRes, emptyRes] = await Promise.all([
                    fetchStats(),
                    fetchReport(),
                    fetchDetections({ per_page: 200, min_confidence: 0 }),
                    fetchImages({ has_animal: false, per_page: 50 }),
                ]);
                if (!alive) return;
                setStats(s);
                setReport(r);
                setDetections(detRes.items || []);
                setEmptyImages(emptyRes);
                setError(null);
            } catch (e: any) {
                setError(e.message);
            } finally {
                if (alive) setLoading(false);
            }
        };
        load();
    }, []);

    const lowConf = detections.filter((d) => (d.detection_confidence < 0.7) || (d.classification_confidence != null && d.classification_confidence < 0.7));
    const highConf = detections.filter((d) => d.detection_confidence >= 0.7 && (d.classification_confidence == null || d.classification_confidence >= 0.7));
    const noAnimalCount = emptyImages?.total ?? report?.empty_images ?? 0;

    const metrics = {
        lowConf: lowConf.length,
        conflict: 0,
        noAnimal: noAnimalCount,
        newIndividual: Math.min(highConf.length, 50),
    };

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
                <p className="pending-review-subtitle">Review and verify AI-detected images for Spotted-tail Quolls.</p>
            </div>

            <div className="review-metrics">
                <div className="review-metric-card warning">
                    <span className="dot yellow" /><span className="icon">⚠</span>
                    <div><strong>{fmt(metrics.lowConf)}</strong> Low Confidence Identifications</div>
                </div>
                <div className="review-metric-card danger">
                    <span className="dot red" /><span className="icon">✕</span>
                    <div><strong>{fmt(metrics.conflict)}</strong> Conflict Detections</div>
                </div>
                <div className="review-metric-card muted">
                    <span className="dot gray" /><span className="icon">↻</span>
                    <div><strong>{fmt(metrics.noAnimal)}</strong> No Animal Detected</div>
                </div>
                <div className="review-metric-card success">
                    <span className="dot green" /><span className="icon">+</span>
                    <div><strong>{fmt(metrics.newIndividual)}</strong> New Individuals Potential</div>
                </div>
            </div>

            <div className="review-toolbar">
                <input type="search" className="review-search" placeholder="Search by filename, camera trap, or date" value={search} onChange={(e) => setSearch(e.target.value)} />
                <select className="filter-select"><option>Spotted-tail Quoll</option><option>All Species</option></select>
                <select className="filter-select"><option>Date Range</option></select>
                <select className="filter-select"><option>Camera Location</option></select>
                <select className="filter-select"><option>Sort by Date</option></select>
            </div>

            {!filter ? (
                <div className="review-category-grid">
                    <ReviewCategoryCard title="Low confidence" tag={`${lowConf.length > 0 ? Math.round((lowConf[0].detection_confidence || 0) * 100) : 0}% - Low Confidence`} tagClass="warning" imageCount={lowConf.length} onReview={() => setFilter('low-confidence')} />
                    <ReviewCategoryCard title="Conflict" tag="Conflict" tagClass="danger" imageCount={metrics.conflict} onReview={() => setFilter('conflict')} />
                    <ReviewCategoryCard title="New Individual" tag="89% - High" tagClass="success" imageCount={metrics.newIndividual} onReview={() => setFilter('new-individual')} />
                    <ReviewCategoryCard title="No Animal (Miss fire)" tag="No Detection" tagClass="muted" imageCount={metrics.noAnimal} onReview={() => setFilter('no-animal')} />
                </div>
            ) : (
                <div className="review-list-view">
                    <button type="button" className="btn btn-outline" style={{ marginBottom: '1rem' }} onClick={() => setFilter(null)}>← Back to categories</button>
                    {filter === 'low-confidence' && (
                        <div className="review-item-grid">
                            {lowConf.slice(0, 20).map((d) => (
                                <div key={d.id} className="review-item-card">
                                    <div className="review-item-tags">
                                        <span className={`tag tag-${(d.detection_confidence || 0) >= 0.7 ? 'primary' : 'accent'}`}>{Math.round((d.detection_confidence || 0) * 100)}%</span>
                                        <span className="tag tag-muted">Low Confidence</span>
                                    </div>
                                    <div>Image Count — 1</div>
                                    <div className="review-item-model">Model: YOLOV8</div>
                                    <Link to={`/review/${d.id}`} className="btn btn-primary" style={{ marginTop: '0.75rem' }}>Review</Link>
                                </div>
                            ))}
                        </div>
                    )}
                    {filter === 'no-animal' && emptyImages && (
                        <div className="review-item-grid">
                            {emptyImages.items.map((img) => (
                                <div key={img.id} className="review-item-card">
                                    <div className="review-item-tags"><span className="tag tag-muted">No Animal</span></div>
                                    <div>{img.filename}</div>
                                    <Link to={`/review-empty/${img.id}`} className="btn btn-primary" style={{ marginTop: '0.75rem' }}>Annotate (add animal)</Link>
                                </div>
                            ))}
                        </div>
                    )}
                    {(filter === 'conflict' || filter === 'new-individual') && (
                        <div className="review-item-grid">
                            {(filter === 'new-individual' ? highConf : detections).slice(0, 20).map((d) => (
                                <div key={d.id} className="review-item-card">
                                    <div className="review-item-tags">
                                        <span className="tag tag-primary">{Math.round((d.detection_confidence || 0) * 100)}%</span>
                                    </div>
                                    <Link to={`/review/${d.id}`} className="btn btn-primary" style={{ marginTop: '0.75rem' }}>Review</Link>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            <div className="review-side-panels">
                <div className="review-panel card">
                    <h4>Analytics Overview</h4>
                    <p>Reviews Completed This Week: <strong>{report?.processed_images ?? 0}</strong></p>
                    <p>Average Model Confidence: <strong>76%</strong></p>
                    <p>Most Common Pending: <span className="tag tag-accent">Low Confidence</span></p>
                </div>
                <div className="review-panel card">
                    <h4>Focus Species</h4>
                    <label><input type="radio" checked={focusSpecies === 'quoll'} onChange={() => setFocusSpecies('quoll')} /> Spotted-tail Quoll</label>
                    <label><input type="radio" checked={focusSpecies === 'all'} onChange={() => setFocusSpecies('all')} /> All Species</label>
                    <a href={getExportUrl('csv', focusSpecies === 'quoll' ? 'quoll' : undefined)} className="btn btn-outline" style={{ marginTop: '0.75rem', display: 'inline-flex' }}>Export Summary</a>
                </div>
            </div>
        </div>
    );
}

function ReviewCategoryCard({ title, tag, tagClass, imageCount, onReview }: { title: string; tag: string; tagClass: string; imageCount: number; onReview: () => void }) {
    return (
        <div className="review-category-card card">
            <div className="review-category-tags">
                <span className={`tag tag-${tagClass}`}>{tag}</span>
                <span className={`tag tag-${tagClass}`}>{tag.split(' ')[0]}</span>
            </div>
            <div className="review-category-title">{title}</div>
            <div className="review-category-meta">Image Count - {fmt(imageCount)}</div>
            <div className="review-category-model">Model: YOLOV8</div>
            <button type="button" className="btn btn-primary" onClick={onReview}>Review</button>
        </div>
    );
}

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

    const totalDet = report?.total_detections ?? stats.total_detections;
    const observationTrends = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'].map((name, i) => ({
        name,
        count: Math.round(totalDet * (0.6 + (i * 0.1)) + Math.random() * 20),
    }));

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
    const [images, setImages] = useState<PaginatedResponse<ImageData> | null>(null);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState<ImageData | null>(null);
    const [detections, setDetections] = useState<Detection[]>([]);
    const [showBoxes, setShowBoxes] = useState(true);

    useEffect(() => {
        if (!decoded) return;
        setLoading(true);
        fetchImagesBySpecies(decoded, { page, per_page: 30 }).then(setImages).catch(() => {}).finally(() => setLoading(false));
    }, [decoded, page]);

    useEffect(() => {
        if (!selected) { setDetections([]); return; }
        fetchImageDetail(selected.id).then((detail: any) => {
            setDetections(detail.detections || []);
        }).catch(() => setDetections([]));
    }, [selected?.id]);

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
    return (
        <div>
            <nav className="breadcrumb"><Link to="/">Home</Link><span className="sep">›</span><Link to="/individuals">Profiles</Link><span className="sep">›</span><Link to={`/individuals/species/${speciesKey}`}>{decoded}</Link><span className="sep">›</span><span>Images</span></nav>
            <div className="page-header"><h2>All images — {decoded}</h2><span className="tag tag-muted" style={{ marginLeft: '0.5rem' }}>{images?.total ?? 0} images</span></div>
            {!images || images.items.length === 0 ? <div className="empty-state">No images for this species.</div> : (
                <>
                    <div className="image-grid">
                        {sortedItems.map((img) => (
                            <div key={img.id} className="image-card" onClick={() => setSelected(img)} style={{ cursor: 'pointer' }}>
                                <div className="image-thumb">
                                    {(img.thumbnail_path || img.file_path) ? <img src={storageUrl(img.thumbnail_path || img.file_path)} alt={img.filename} /> : '📷'}
                                    {img.has_animal && <div className="image-animal-badge">ANIMAL</div>}
                                </div>
                                <div className="image-info">
                                    <div className="image-filename">{img.filename}</div>
                                    <div className="image-meta">
                                        {img.processed ? <span className="tag tag-primary">Processed</span> : <span className="tag tag-muted">Pending</span>}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                    {images.pages > 1 && <div className="pagination"><button className="page-btn" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>Prev</button><span className="page-info">Page {page} of {images.pages}</span><button className="page-btn" onClick={() => setPage((p) => Math.min(images.pages, p + 1))} disabled={page === images.pages}>Next</button></div>}
                </>
            )}
            {selected && (
                <div className="lightbox-overlay" onClick={() => setSelected(null)}>
                    <div className="lightbox-content card" onClick={(e) => e.stopPropagation()}>
                        <div className="card-header" style={{ justifyContent: 'space-between' }}>
                            <h3>{selected.filename}</h3>
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
                                    <div key={det.id} className="detection-bbox-overlay" style={{
                                        position: 'absolute',
                                        left: `${det.bbox_x * 100}%`,
                                        top: `${det.bbox_y * 100}%`,
                                        width: `${det.bbox_w * 100}%`,
                                        height: `${det.bbox_h * 100}%`,
                                        border: '2px solid #00ff88',
                                        borderRadius: 3,
                                        pointerEvents: 'none',
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
                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                                <Link to={`/review-image/${selected.id}`} className="btn btn-primary">Review Image</Link>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

function SpeciesByIndividual() {
    const { speciesKey } = useParams();
    const decoded = speciesKey ? decodeURIComponent(speciesKey).replace(/-/g, ' ') : '';
    const [individuals, setIndividuals] = useState<IndividualData[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => { fetchIndividuals().then((list) => setIndividuals(list.filter((i) => i.species.toLowerCase().includes(decoded.toLowerCase())))).finally(() => setLoading(false)); }, [decoded]);

    if (loading) return <LoadingState />;
    return (
        <div>
            <nav className="breadcrumb"><Link to="/">Home</Link><span className="sep">›</span><Link to="/individuals">Profiles</Link><span className="sep">›</span><Link to={`/individuals/species/${speciesKey}`}>{decoded}</Link><span className="sep">›</span><span>By individual</span></nav>
            <div className="page-header"><h2>Individuals — {decoded}</h2></div>
            <div className="quoll-grid">
                {individuals.map((ind) => (
                    <Link key={ind.individual_id} to={`/individuals/species/${speciesKey}/individuals/${encodeURIComponent(ind.individual_id)}`} className="quoll-card">
                        <div className="quoll-id">🐾 {ind.individual_id}</div>
                        <div className="quoll-species">{ind.species}</div>
                        <div className="quoll-stats"><div className="quoll-stat"><div className="label">Sightings</div><div className="value">{ind.total_sightings}</div></div></div>
                    </Link>
                ))}
            </div>
        </div>
    );
}

function IndividualImages() {
    const { speciesKey, individualId } = useParams();
    const decoded = individualId ? decodeURIComponent(individualId) : '';

    return (
        <div>
            <nav className="breadcrumb"><Link to="/">Home</Link><span className="sep">›</span><Link to="/individuals">Profiles</Link><span className="sep">›</span><Link to={`/individuals/species/${speciesKey}`}>{speciesKey}</Link><span className="sep">›</span><Link to={`/individuals/species/${speciesKey}/individuals`}>Individuals</Link><span className="sep">›</span><span>{decoded}</span></nav>
            <div className="page-header"><h2>Individual {decoded}</h2><p>Sightings and images for this individual (list requires backend support)</p></div>
        </div>
    );
}

function BatchUpload() {
    const [job, setJob] = useState<JobStatus | null>(null);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [dragOver, setDragOver] = useState(false);
    const [collectionName, setCollectionName] = useState('');
    const folderRef = useRef<HTMLInputElement>(null);

    const folderInfo = selectedFiles.length > 0 ? parseFolderStructure(selectedFiles) : null;

    useEffect(() => {
        if (folderInfo?.collectionName && !collectionName) setCollectionName(folderInfo.collectionName);
    }, [folderInfo?.collectionName]);

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
        setUploading(true);
        setError(null);
        try {
            const res = await uploadBatch(selectedFiles, collectionName || undefined);
            pollJob(res.job_id);
        } catch (e: any) {
            setError(e.message);
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
                <div className="dropzone-icon">☁️</div>
                <p className="dropzone-text">Drop folder here or click to browse</p>
                <button type="button" className="btn btn-primary" onClick={(e) => { e.stopPropagation(); folderRef.current?.click(); }}>Choose Folder</button>
            </div>

            {folderInfo && selectedFiles.length > 0 && !job && (
                <div className="upload-summary card">
                    <div className="card-header"><h3>Folder Summary</h3></div>
                    <div className="card-body">
                        <input className="filter-select" style={{ width: '100%' }} value={collectionName} onChange={(e) => setCollectionName(e.target.value)} placeholder="Collection Name" />
                        <div style={{ marginTop: '1rem' }}>{selectedFiles.length} images found in {folderInfo.cameras.size} cameras.</div>
                        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
                            <button className="btn btn-primary" onClick={handleUpload} disabled={uploading}>{uploading ? 'Uploading...' : 'Upload & Process'}</button>
                            <button className="btn btn-outline" onClick={() => setSelectedFiles([])}>Clear</button>
                        </div>
                    </div>
                </div>
            )}

            {job && (
                <div className="upload-batch-progress card" style={{ marginTop: '2rem' }}>
                    <div className="card-header"><h3>Processing Batch...</h3><span className={`tag tag-accent`}>{job.status}</span></div>
                    <div className="card-body">
                        <div className="progress-bar-bg"><div className="progress-bar-fill" style={{ width: `${job.percent}%` }} /></div>
                        <div style={{ textAlign: 'right', fontSize: '0.8rem', marginTop: '0.5rem' }}>{job.percent.toFixed(1)}%</div>
                    </div>
                </div>
            )}
        </>
    );
}

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
            <div className="page-header"><h2>Reports</h2><p>Data analytics and exports</p></div>
            <div className="stats-grid">
                <StatCard icon="📷" value={fmt(report.total_images)} label="Total Images" />
                <StatCard icon="✅" value={fmt(report.processed_images)} label="Processed" />
                <StatCard icon="🔍" value={fmt(report.total_detections)} label="Detections" />
                <StatCard icon="🐾" value={fmt(report.quoll_detections)} label="Quolls" />
            </div>
            <div className="card" style={{ marginTop: '2rem' }}>
                <div className="card-header"><h3>Exports</h3></div>
                <div className="card-body" style={{ display: 'flex', gap: '1rem' }}>
                    <a href={getExportUrl('csv')} className="btn btn-outline" download>Download CSV Report</a>
                    <a href={getQuollExportUrl('csv')} className="btn btn-primary" download>Download Quoll Only CSV</a>
                </div>
            </div>
        </>
    );
}

function ImageReview() {
    const params = useParams();
    const id = parseInt(params.detectionId || '0');
    const [det, setDet] = useState<DetectionDetail | null>(null);
    const [anns, setAnns] = useState<AnnotationData[]>([]);
    const [form, setForm] = useState({ is_correct: true, corrected_species: '', notes: '', individual_id: '', flag_for_retraining: false, bbox: undefined as any });
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
            setForm({ is_correct: true, corrected_species: '', notes: '', individual_id: '', flag_for_retraining: false, bbox: undefined });
        } catch { }
        setSaving(false);
    };

    if (loading) return <LoadingState />;
    if (!det) return <div className="empty-state"><h3>Detection not found</h3></div>;

    return (
        <>
            <div className="page-header"><h2>Review Detection #{det.id}</h2></div>
            <div className="chart-grid">
                <div className="card">
                    <div className="card-body" style={{ textAlign: 'center' }}>
                        {det.crop_path && <img src={storageUrl(det.crop_path)} alt="crop" style={{ maxWidth: '100%', borderRadius: 8 }} />}
                        <div style={{ marginTop: '1rem' }}><strong>Species:</strong> {det.species || 'Unknown'} ({Math.round(det.detection_confidence * 100)}%)</div>
                    </div>
                </div>
                <div className="card">
                    <div className="card-header"><h3>Annotate</h3></div>
                    <div className="card-body">
                        <select className="filter-select" style={{ width: '100%' }} value={String(form.is_correct)} onChange={(e) => setForm({ ...form, is_correct: e.target.value === 'true' })}>
                            <option value="true">Correct</option><option value="false">Incorrect</option>
                        </select>
                        <input className="filter-select" style={{ width: '100%', marginTop: '1rem' }} value={form.individual_id} onChange={(e) => setForm({ ...form, individual_id: e.target.value })} placeholder="Individual ID" />
                        <textarea className="filter-select" style={{ width: '100%', marginTop: '1rem', minHeight: 80 }} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Notes" />
                        <button className="btn btn-primary" style={{ marginTop: '1rem', width: '100%' }} onClick={submit} disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
                    </div>
                </div>
            </div>
        </>
    );
}

function ReviewImage() {
    const { imageId } = useParams();
    const id = parseInt(imageId || '0');
    const [image, setImage] = useState<ImageData | null>(null);
    const [loading, setLoading] = useState(true);
    const [step, setStep] = useState<'choose' | 'annotate' | 'done'>('choose');
    const [bbox, setBbox] = useState<any>(null);
    const [species, setSpecies] = useState('Spotted-tailed Quoll');
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
    if (step === 'done') return <div className="empty-state"><h3>Review Saved!</h3><Link to="/admin" className="btn btn-primary">Return to Admin</Link></div>;

    return (
        <div className="review-image-layout card">
            <div className="card-body" style={{ textAlign: 'center' }}>
                {step === 'choose' ? (
                    <>
                        <img src={storageUrl(image.file_path)} alt="review" style={{ maxWidth: '100%', borderRadius: 8 }} />
                        <div style={{ marginTop: '2rem', display: 'flex', gap: '1rem', justifyContent: 'center' }}>
                            <button className="btn btn-outline" onClick={confirmEmpty}>Mark as Empty</button>
                            <button className="btn btn-primary" onClick={() => setStep('annotate')}>Found Animal</button>
                        </div>
                    </>
                ) : (
                    <>
                        <BboxDrawer imageUrl={storageUrl(image.file_path)} onDraw={setBbox} />
                        <div style={{ marginTop: '2rem' }}>
                            <select className="filter-select" value={species} onChange={(e) => setSpecies(e.target.value)}>
                                <option>Spotted-tailed Quoll</option><option>Kangaroo</option><option>Wombat</option>
                            </select>
                            <button className="btn btn-primary" style={{ marginLeft: '1rem' }} onClick={submitAnimal} disabled={!bbox || saving}>Save Observation</button>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

function BboxDrawer({ imageUrl, onDraw }: { imageUrl: string; onDraw: (bbox: any) => void }) {
    const imgRef = useRef<HTMLImageElement>(null);
    const [box, setBox] = useState<any>(null);

    const handleDown = (e: any) => {
        const rect = imgRef.current!.getBoundingClientRect();
        setBox({ x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height, w: 0, h: 0 });
    };

    const handleUp = (e: any) => {
        if (!box) return;
        const rect = imgRef.current!.getBoundingClientRect();
        const endX = (e.clientX - rect.left) / rect.width;
        const endY = (e.clientY - rect.top) / rect.height;
        const finalBox = { x: Math.min(box.x, endX), y: Math.min(box.y, endY), w: Math.abs(endX - box.x), h: Math.abs(endY - box.y) };
        setBox(finalBox);
        onDraw(finalBox);
    };

    return (
        <div style={{ position: 'relative', display: 'inline-block', cursor: 'crosshair' }} onPointerDown={handleDown} onPointerUp={handleUp}>
            <img ref={imgRef} src={imageUrl} alt="draw" style={{ maxWidth: '100%', borderRadius: 8 }} draggable={false} />
            {box && <div style={{ position: 'absolute', border: '3px solid #10b981', background: 'rgba(16,185,129,0.2)', left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.w * 100}%`, height: `${box.h * 100}%` }} />}
        </div>
    );
}

function LoginPage() {
    const { login } = useAuth();
    const [email, setEmail] = useState('');
    const [pass, setPass] = useState('');
    const submit = (e: any) => { e.preventDefault(); login(email, pass); };
    return (
        <div style={{ maxWidth: 400, margin: '100px auto' }} className="card">
            <form className="card-body" onSubmit={submit}>
                <h3>Login</h3>
                <input className="filter-select" style={{ width: '100%', marginTop: '1rem' }} placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} />
                <input className="filter-select" style={{ width: '100%', marginTop: '1rem' }} type="password" placeholder="Password" value={pass} onChange={e => setPass(e.target.value)} />
                <button className="btn btn-primary" style={{ width: '100%', marginTop: '2rem' }}>Sign In</button>
            </form>
        </div>
    );
}

function ReviewEmptyImage() { return <Navigate to="/" />; }

function StatCard({ icon, value, label }: { icon: string; value: string; label: string }) {
    return <div className="stat-card"><div className="stat-icon">{icon}</div><div className="stat-value">{value}</div><div className="stat-label">{label}</div></div>;
}

function LoadingState() { return <div className="loading-container"><div className="spinner" /><span>Loading Wildlife Tracker...</span></div>; }
function ErrorState({ message }: { message: string }) { return <div className="empty-state"><h3>Connection Error</h3><p>{message}</p></div>; }
function fmt(n: number): string { return n.toLocaleString(); }

export default App;
