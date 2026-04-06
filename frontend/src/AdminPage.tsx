import React, { useEffect, useState } from 'react';

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

const AdminPage: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Note: Adjust port 8000 if your FastAPI is running elsewhere
    // The path /api/admin/dashboard-stats matches your main.py + admin.py setup
    fetch('http://localhost:8000/api/admin/dashboard-stats')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to fetch dashboard data');
        return res.json();
      })
      .then((json) => setData(json))
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

      {/* Navigation Header */}
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

      {/* Global Search */}
      <div className="search-section">
        <input 
          type="text" 
          className="search-bar" 
          placeholder="Search sightings, locations, or tags..." 
        />
      </div>

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
`;

export default AdminPage;
