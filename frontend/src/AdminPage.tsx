import { useEffect, useMemo, useState } from 'react';
import {
  fetchUsers,
  fetchSystemMetrics,
  changeUserRole,
  getExportUrl,
  getQuollExportUrl,
  getMetadataExportUrl,
  type UserData,
} from './api';

type MetricsData = {
  total_images?: number;
  total_detections?: number;
  total_users?: number;
  pending_jobs?: number;
  db_size_mb?: number;
  storage_size_mb?: number;
};

export default function AdminPage() {
  const [users, setUsers] = useState<UserData[]>([]);
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [updatingUserId, setUpdatingUserId] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;

    Promise.all([fetchUsers(), fetchSystemMetrics()])
      .then(([userData, metricData]) => {
        if (!alive) return;
        setUsers(userData);
        setMetrics(metricData);
        setError(null);
      })
      .catch((e: any) => {
        if (!alive) return;
        setError(e?.message || 'Failed to load admin data');
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, []);

  const filteredUsers = useMemo(() => {
    return users.filter((user) => {
      const matchesSearch =
        user.email.toLowerCase().includes(search.toLowerCase()) ||
        (user.full_name || '').toLowerCase().includes(search.toLowerCase());

      const matchesRole = roleFilter === 'all' || user.role === roleFilter;

      return matchesSearch && matchesRole;
    });
  }, [users, search, roleFilter]);

  const onRoleChange = async (userId: number, role: string) => {
    try {
      setUpdatingUserId(userId);
      const updated = await changeUserRole(userId, role);
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
    } catch (e: any) {
      alert(e?.message || 'Failed to change role');
    } finally {
      setUpdatingUserId(null);
    }
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner" />
        <span>Loading admin panel...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <div className="icon">⚠️</div>
        <h3>Connection Error</h3>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <h2>Admin Dashboard</h2>
        <p>System management, user administration, and exports</p>
      </div>

      <div className="stats-grid">
        <StatCard icon="📷" value={fmt(metrics?.total_images)} label="Images" />
        <StatCard icon="🔍" value={fmt(metrics?.total_detections)} label="Detections" />
        <StatCard icon="👤" value={fmt(metrics?.total_users)} label="Users" />
        <StatCard icon="⏳" value={fmt(metrics?.pending_jobs)} label="Pending Jobs" />
        <StatCard icon="💾" value={`${fmt(metrics?.db_size_mb)} MB`} label="DB Size" />
        <StatCard icon="📁" value={`${fmt(metrics?.storage_size_mb)} MB`} label="Storage" />
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <h3>Admin Actions</h3>
        </div>
        <div className="card-body">
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <a href={getQuollExportUrl('csv')} className="btn btn-primary" download>
              Export Quoll Detections
            </a>
            <a href={getMetadataExportUrl('csv')} className="btn btn-outline" download>
              Export Full Metadata
            </a>
            <a href={getExportUrl('json')} className="btn btn-outline" download>
              Export Report JSON
            </a>
            <a href={getExportUrl('csv')} className="btn btn-outline" download>
              Export Report CSV
            </a>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <h3>User Management</h3>
          <span className="tag tag-primary">{filteredUsers.length} shown</span>
        </div>
        <div className="card-body">
          <div className="filters-bar">
            <input
              className="filter-select"
              style={{ minWidth: 260 }}
              type="text"
              placeholder="Search by email or name"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />

            <select
              className="filter-select"
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
            >
              <option value="all">All Roles</option>
              <option value="admin">Admin</option>
              <option value="researcher">Researcher</option>
              <option value="reviewer">Reviewer</option>
            </select>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Name</th>
                  <th>Role</th>
                  <th>Active</th>
                  <th>Change Role</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                      No users found
                    </td>
                  </tr>
                ) : (
                  filteredUsers.map((user) => (
                    <tr key={user.id}>
                      <td>{user.email}</td>
                      <td>{user.full_name || '—'}</td>
                      <td>
                        <span
                          className={
                            user.role === 'admin'
                              ? 'tag tag-primary'
                              : user.role === 'researcher'
                              ? 'tag tag-info'
                              : 'tag tag-muted'
                          }
                        >
                          {user.role}
                        </span>
                      </td>
                      <td>{user.is_active ? '✅ Yes' : '❌ No'}</td>
                      <td>
                        <select
                          className="filter-select"
                          value={user.role}
                          disabled={updatingUserId === user.id}
                          onChange={(e) => onRoleChange(user.id, e.target.value)}
                          style={{ fontSize: '0.8rem' }}
                        >
                          <option value="admin">admin</option>
                          <option value="researcher">researcher</option>
                          <option value="reviewer">reviewer</option>
                        </select>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="chart-grid">
        <div className="card">
          <div className="card-header">
            <h3>Admin Notes</h3>
          </div>
          <div className="card-body">
            <ul style={{ paddingLeft: '1rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              <li>Use this page to manage user roles and monitor platform storage.</li>
              <li>Exports download directly from the backend API endpoints.</li>
              <li>If data does not load, the backend server is likely not running locally.</li>
            </ul>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3>System Summary</h3>
          </div>
          <div className="card-body">
            <div style={{ display: 'grid', gap: '0.75rem' }}>
              <SummaryRow label="Total Images" value={fmt(metrics?.total_images)} />
              <SummaryRow label="Total Detections" value={fmt(metrics?.total_detections)} />
              <SummaryRow label="Total Users" value={fmt(metrics?.total_users)} />
              <SummaryRow label="Pending Jobs" value={fmt(metrics?.pending_jobs)} />
              <SummaryRow label="Database Size" value={`${fmt(metrics?.db_size_mb)} MB`} />
              <SummaryRow label="Storage Size" value={`${fmt(metrics?.storage_size_mb)} MB`} />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function StatCard({ icon, value, label }: { icon: string; value: string; label: string }) {
  return (
    <div className="stat-card">
      <div className="stat-icon">{icon}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        borderBottom: '1px solid var(--border)',
        paddingBottom: '0.5rem',
      }}
    >
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function fmt(value: number | undefined): string {
  return typeof value === 'number' ? value.toLocaleString() : '0';
}
