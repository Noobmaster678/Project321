import React, { useEffect, useState } from 'react';

export default function AdminPage() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    fetch('http://localhost:5000/api/admin/dashboard')
      .then(res => res.json())
      .then(setData)
      .catch(err => console.error("Backend Error:", err));
  }, []);

  if (!data) return <div style={{padding: '20px'}}>Loading Wildlife Tracker Data...</div>;

  return (
    <div className="dashboard-container">
      <style>{`
        .dashboard-container { font-family: 'Inter', sans-serif; padding: 20px; background: #fff; max-width: 1200px; margin: auto; }
        .nav-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 10px; color: #2d6a4f; }
        .search-bar { width: 100%; max-width: 600px; padding: 10px; margin: 20px auto; display: block; border-radius: 20px; border: 1px solid #ddd; background: #f9f9f9; }
        
        .grid-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }
        .stat-card { padding: 20px; border-radius: 8px; border: 1px solid #eee; position: relative; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .stat-card.green { border-top: 5px solid #2d6a4f; }
        .stat-card.yellow { border-top: 5px solid #ffb703; }
        .stat-card.red { border-top: 5px solid #e63946; }
        .stat-card h1 { margin: 0; font-size: 24px; }
        .stat-card p { margin: 5px 0 0; font-size: 12px; color: #666; }

        .sighting-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        .sighting-card { border: 1px solid #eee; border-radius: 8px; overflow: hidden; padding: 10px; }
        .sighting-card img { width: 100%; border-radius: 4px; display: block; }
        .card-info { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }
        .btn-review { background: #2d6a4f; color: white; border: none; padding: 8px 0; width: 100%; border-radius: 4px; margin-top: 10px; cursor: pointer; }
        
        .analytics-section { margin-top: 40px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .chart-box { border: 1px solid #eee; padding: 20px; border-radius: 8px; min-height: 200px; text-align: center; }
        .full-width { grid-column: span 2; }
      `}</style>

      <header className="nav-header">
        <strong>WildlifeTracker</strong>
        <div style={{fontSize: '14px'}}>Home Upload Profiles Reports Help <b>Admin</b></div>
      </header>

      <input type="text" className="search-bar" placeholder="Search..." />

      <h3>Activity</h3>
      <div className="grid-stats">
        {data.stats.map((s: any, i: number) => (
          <div key={i} className={`stat-card ${s.color}`}>
            <h1>{s.value}</h1>
            <p>{s.label}</p>
          </div>
        ))}
      </div>

      <h3>Recent Sighting</h3>
      <div className="sighting-grid">
        {data.recent_sightings.map((s: any) => (
          <div key={s.id} className="sighting-card">
            <div style={{position: 'relative'}}>
              <img src={s.img} alt="Wildlife" />
              <span style={{position: 'absolute', top: '5px', left: '5px', background: 'rgba(255,255,255,0.8)', fontSize: '10px', padding: '2px 5px', borderRadius: '3px'}}>{s.tag}</span>
            </div>
            <div className="card-info">
              <span style={{fontSize: '12px', color: '#888'}}>{s.id}</span>
              <span style={{fontSize: '10px', color: '#bbb'}}>v0.0.1</span>
            </div>
            <button className="btn-review">{s.status}</button>
          </div>
        ))}
      </div>

      <h3>Analytics</h3>
      <div className="analytics-section">
        <div className="chart-box">Identification Accuracy Trend</div>
        <div className="chart-box">Positive vs Unverified</div>
        <div className="chart-box full-width">User Activity</div>
      </div>
    </div>
  );
}
