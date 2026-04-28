import React, { useEffect, useState } from 'react';
import { fetchAdminDashboardStats, postAdminReidBackfill, type ReidBackfillMode } from './api';

// --- TypeScript Interfaces for Data Safety ---
interface StatCard {
  label: string;
  value: string | number;
  color: 'green' | 'yellow' | 'red';
}

interface Sighting {
  id: string;
  tag: string;
  status: string;
  img: string;
}

interface DashboardData {
  stats: StatCard[];
  recent_sightings: Sighting[];
}

const AdminPage: React.FC<{ embedded?: boolean }> = ({ embedded = false }) => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reidMode, setReidMode] = useState<ReidBackfillMode>('missing_only');
  const [reidLimit, setReidLimit] = useState(2000);
  const [reidAsync, setReidAsync] = useState(false);
  const [reidBusy, setReidBusy] = useState(false);
  const [reidMsg, setReidMsg] = useState<string | null>(null);

  useEffect(() => {
    fetchAdminDashboardStats()
      .then(setData)
      .catch((err) => {
        console.error(err);
        setError(err.message);
      });
  }, []);

  if (error) return <div style={{ padding: '40px', color: 'red' }}>Error: {error}</div>;
  if (!data) return <div style={{ padding: '40px', color: '#2d6a4f' }}>Loading Wildlife Tracker Dashboard...</div>;

  return (
    <div className="admin-container">
      <style>{inlineCSS}</style>

      {!embedded && (
        <>
          <header className="nav-header">
            <div className="logo">🌿 WildlifeTracker</div>
            <nav className="nav-links">
              <span>Home</span>
              <span>Upload</span>
              <span>Profiles</span>
              <span>Reports</span>
              <span>Help</span>
              <span className="active">Admin</span>
            </nav>
            <div className="user-profile">
              <img src="https://via.placeholder.com/32" alt="Admin Profile" className="avatar" />
            </div>
          </header>

          <div className="search-section">
            <input
              type="text"
              className="search-bar"
              placeholder="Search sightings, locations, or tags..."
            />
          </div>
        </>
      )}

      {/* Activity Summary Section */}
      <section className="dashboard-section">
        <h3 className="section-title">Activity</h3>
        <div className="stats-grid">
          {data.stats.map((stat, i) => (
            <div key={i} className={`stat-card border-${stat.color}`}>
              <div className={`status-dot bg-${stat.color}`}></div>
              <h2 className="stat-value">{stat.value}</h2>
              <p className="stat-label">{stat.label}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="dashboard-section">
        <h3 className="section-title">Quoll re-ID backfill</h3>
        <p style={{ color: '#666', fontSize: 14, lineHeight: 1.5, marginTop: 0, maxWidth: 720 }}>
          Re-run MegaDescriptor on <strong>existing quoll crops</strong> (no MegaDetector). Requires{' '}
          <code>storage/models/megadescriptor_l384_gallery.pt</code> and torch/timm on the API process (or Celery worker
          if you use <em>Queue on worker</em>).
        </p>
        <div className="reid-backfill-panel">
          <label className="reid-label">
            Mode
            <select
              className="reid-select"
              value={reidMode}
              onChange={(e) => setReidMode(e.target.value as ReidBackfillMode)}
              disabled={reidBusy}
            >
              <option value="missing_only">Missing only — detections with no annotations</option>
              <option value="refresh_auto">Refresh auto — replace megadescriptor_reid labels; keep manual IDs</option>
            </select>
          </label>
          <label className="reid-label">
            Max detections
            <input
              type="number"
              className="reid-input"
              min={1}
              max={50000}
              value={reidLimit}
              onChange={(e) => setReidLimit(Number(e.target.value) || 2000)}
              disabled={reidBusy}
            />
          </label>
          <label className="reid-check">
            <input
              type="checkbox"
              checked={reidAsync}
              onChange={(e) => setReidAsync(e.target.checked)}
              disabled={reidBusy}
            />
            Queue on worker (Celery <code>ml</code> queue)
          </label>
          <button
            type="button"
            className="reid-run-btn"
            disabled={reidBusy}
            onClick={async () => {
              setReidBusy(true);
              setReidMsg(null);
              try {
                const out = await postAdminReidBackfill({
                  mode: reidMode,
                  limit: reidLimit,
                  run_async: reidAsync,
                });
                if (out.status === 'queued') {
                  setReidMsg(`Queued task ${out.task_id ?? ''}. Check Celery worker logs.`);
                } else {
                  setReidMsg(
                    `Done: assigned ${String(out.assigned ?? 0)}, unknown ${String(out.unknown ?? 0)}, skipped ${String(out.skipped ?? 0)}, errors ${String(out.errors ?? 0)} (candidates ${String(out.candidates ?? 0)}).`,
                  );
                }
              } catch (e) {
                setReidMsg(e instanceof Error ? e.message : 'Backfill failed');
              } finally {
                setReidBusy(false);
              }
            }}
          >
            {reidBusy ? 'Running…' : 'Run re-ID backfill'}
          </button>
          {reidMsg && (
            <p className="reid-result" role="status">
              {reidMsg}
            </p>
          )}
        </div>
      </section>

      {/* Recent Sightings Grid */}
      <section className="dashboard-section">
        <h3 className="section-title">Recent Sighting</h3>
        <div className="sightings-grid">
          {data.recent_sightings.map((sighting) => (
            <div key={sighting.id} className="sighting-card">
              <div className="image-wrapper">
                <img src={sighting.img} alt="Quoll Sighting" />
                <span className="confidence-badge">{sighting.tag}</span>
              </div>
              <div className="card-info">
                <span className="sighting-id">ID: {sighting.id}</span>
                <span className="version-tag">v.Quoll-AI</span>
              </div>
              <button className="action-btn">{sighting.status}</button>
            </div>
          ))}
        </div>
        <button className="show-more-btn">Show More Records</button>
      </section>

      {/* Analytics Visualization Placeholders */}
      <section className="dashboard-section">
        <h3 className="section-title">Analytics</h3>
        <div className="analytics-grid">
          <div className="chart-box">
            <h4>Identification Accuracy Trend</h4>
            <div className="placeholder-viz">📈 [Line Chart Area]</div>
          </div>
          <div className="chart-box">
            <h4>Positive vs Unverified Identifications</h4>
            <div className="placeholder-viz">⭕ [Donut Chart Area]</div>
          </div>
          <div className="chart-box span-full">
            <h4>User Activity Distribution</h4>
            <div className="placeholder-viz">📊 [Activity Heatmap Area]</div>
          </div>
        </div>
      </section>
    </div>
  );
};

// --- CSS Styles matching the Wildlife Tracker Mockup ---
const inlineCSS = `
  .admin-container { 
    max-width: 1200px; 
    margin: 0 auto; 
    padding: 20px; 
    font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
    background: #ffffff; 
    color: #333;
  }

  .nav-header { 
    display: flex; 
    justify-content: space-between; 
    align-items: center; 
    padding: 10px 0; 
    border-bottom: 1px solid #f0f0f0; 
  }

  .logo { 
    color: #2d6a4f; 
    font-weight: 700; 
    font-size: 22px; 
  }

  .nav-links span { 
    margin-left: 25px; 
    font-size: 14px; 
    cursor: pointer; 
    color: #666; 
    transition: color 0.2s;
  }

  .nav-links .active { 
    color: #2d6a4f; 
    font-weight: bold; 
    border-bottom: 2.5px solid #2d6a4f; 
    padding-bottom: 5px; 
  }

  .avatar { border-radius: 50%; border: 2px solid #2d6a4f; }

  .search-section { text-align: center; margin: 30px 0; }
  .search-bar { 
    width: 65%; 
    padding: 12px 25px; 
    border-radius: 30px; 
    border: 1px solid #e0e0e0; 
    background: #fcfcfc; 
    font-size: 15px;
    outline: none;
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.02);
  }

  .dashboard-section { margin-bottom: 50px; }
  .section-title { font-size: 19px; font-weight: 600; margin-bottom: 20px; color: #222; }

  .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
  .stat-card { 
    position: relative; 
    background: #fff; 
    padding: 25px 20px; 
    border-radius: 12px; 
    border: 1px solid #eeeeee; 
    box-shadow: 0 4px 12px rgba(0,0,0,0.03); 
    transition: transform 0.2s;
  }
  .stat-card:hover { transform: translateY(-3px); }
  
  .border-green { border-top: 6px solid #2d6a4f; }
  .border-yellow { border-top: 6px solid #ffb703; }
  .border-red { border-top: 6px solid #e63946; }

  .stat-value { font-size: 32px; margin: 0; color: #1a1a1a; font-weight: 700; }
  .stat-label { font-size: 12px; color: #777; margin: 8px 0 0 0; line-height: 1.4; }
  
  .status-dot { position: absolute; top: 15px; right: 15px; width: 10px; height: 10px; border-radius: 50%; }
  .bg-green { background: #2d6a4f; } 
  .bg-yellow { background: #ffb703; } 
  .bg-red { background: #e63946; }

  .sightings-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 25px; }
  .sighting-card { 
    background: #fff; 
    border: 1px solid #f0f0f0; 
    border-radius: 12px; 
    padding: 15px; 
    box-shadow: 0 2px 8px rgba(0,0,0,0.04); 
  }
  
  .image-wrapper { position: relative; width: 100%; height: 190px; overflow: hidden; border-radius: 8px; }
  .image-wrapper img { width: 100%; height: 100%; object-fit: cover; }
  .confidence-badge { 
    position: absolute; 
    top: 10px; 
    left: 10px; 
    background: rgba(45, 106, 79, 0.85); 
    color: #fff; 
    padding: 4px 10px; 
    border-radius: 5px; 
    font-size: 11px; 
    font-weight: 600; 
  }
  
  .card-info { display: flex; justify-content: space-between; align-items: center; margin-top: 15px; }
  .sighting-id { font-size: 13px; font-weight: 600; color: #444; }
  .version-tag { font-size: 11px; color: #bbb; }
  
  .action-btn { 
    width: 100%; 
    background: #2d6a4f; 
    color: #fff; 
    border: none; 
    padding: 12px; 
    border-radius: 8px; 
    margin-top: 15px; 
    font-weight: 600; 
    cursor: pointer; 
    transition: background 0.2s;
  }
  .action-btn:hover { background: #1b4332; }
  
  .show-more-btn { 
    width: 100%; 
    margin-top: 35px; 
    background: #2d6a4f; 
    color: #fff; 
    padding: 15px; 
    border: none; 
    border-radius: 10px; 
    font-weight: 700; 
    font-size: 16px; 
    cursor: pointer; 
  }

  .analytics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 25px; }
  .chart-box { border: 1px solid #eeeeee; border-radius: 12px; padding: 20px; min-height: 260px; background: #fafafa; }
  .chart-box h4 { font-size: 15px; margin: 0 0 20px 0; color: #555; border-bottom: 1px solid #f0f0f0; padding-bottom: 10px; }
  .span-full { grid-column: span 2; }
  .placeholder-viz { 
    height: 160px; 
    display: flex; 
    align-items: center; 
    justify-content: center; 
    color: #cccccc; 
    font-weight: bold; 
    background: #fff; 
    border-radius: 8px; 
    border: 1px dashed #ddd; 
  }

  .reid-backfill-panel {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 16px;
    margin-top: 16px;
    padding: 20px;
    background: #fafafa;
    border: 1px solid #eee;
    border-radius: 12px;
    max-width: 900px;
  }
  .reid-label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #444; font-weight: 600; }
  .reid-select, .reid-input {
    min-width: 200px;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid #ddd;
    font-size: 14px;
  }
  .reid-check {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: #555;
    cursor: pointer;
  }
  .reid-run-btn {
    background: #1b4332;
    color: #fff;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    font-size: 14px;
  }
  .reid-run-btn:disabled { opacity: 0.6; cursor: not-allowed; }
  .reid-result { flex-basis: 100%; margin: 0; font-size: 13px; color: #333; line-height: 1.5; }
`;

export default AdminPage;
