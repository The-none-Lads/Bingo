import React, { useState, useEffect, useCallback } from 'react';
import { Users, Activity, Database, Shield, Power, RotateCcw, Search, ChevronDown, ChevronUp, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';

const API_BASE = window.__CONFIG__?.apiBaseUrl || 'http://localhost:8000';

export function AdminDashboard({ currentUser, onClose }) {
  const [activeTab, setActiveTab] = useState('users');
  const [users, setUsers] = useState([]);
  const [systemHealth, setSystemHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedUser, setExpandedUser] = useState(null);

  const fetchUsers = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/users?limit=500`, {
        credentials: 'include'
      });
      if (!res.ok) throw new Error(`Failed to fetch users: ${res.status}`);
      const data = await res.json();
      setUsers(data);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  const fetchSystemHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/system/health`, {
        credentials: 'include'
      });
      if (!res.ok) throw new Error(`Failed to fetch health: ${res.status}`);
      const data = await res.json();
      setSystemHealth(data);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    const loadAll = async () => {
      setLoading(true);
      await Promise.all([fetchUsers(), fetchSystemHealth()]);
      setLoading(false);
    };
    loadAll();
  }, [fetchUsers, fetchSystemHealth]);

  const updateUserRole = async (userId, newRole) => {
    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ role: newRole })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to update role');
      }
      await fetchUsers();
      await fetchSystemHealth();
    } catch (err) {
      setError(err.message);
    }
  };

  const toggleUserActive = async (userId, currentStatus) => {
    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ is_active: !currentStatus })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to update status');
      }
      await fetchUsers();
      await fetchSystemHealth();
    } catch (err) {
      setError(err.message);
    }
  };

  const revokeUserSessions = async (userId) => {
    if (!confirm('Revoke all sessions for this user? They will be logged out.')) return;
    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}/sessions`, {
        method: 'DELETE',
        credentials: 'include'
      });
      if (!res.ok) throw new Error('Failed to revoke sessions');
      await fetchUsers();
      await fetchSystemHealth();
    } catch (err) {
      setError(err.message);
    }
  };

  const globalLogout = async () => {
    if (!confirm('Force logout ALL users except yourself? This cannot be undone.')) return;
    try {
      const res = await fetch(`${API_BASE}/admin/sessions/global-logout`, {
        method: 'POST',
        credentials: 'include'
      });
      if (!res.ok) throw new Error('Failed');
      await fetchSystemHealth();
    } catch (err) {
      setError(err.message);
    }
  };

  const filteredUsers = users.filter(u =>
    u.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
    u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
    u.role.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getRoleBadgeColor = (role) => {
    switch (role) {
      case 'ADMIN': return 'bg-red-100 text-red-800 border-red-200';
      case 'OPERATOR': return 'bg-blue-100 text-blue-800 border-blue-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <Shield className="w-8 h-8 text-purple-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">System Administration</h1>
                <p className="text-sm text-gray-500">Manage users, sessions, and system health</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-all"
            >
              Close
            </button>
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="max-w-7xl mx-auto px-6 mt-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
            <XCircle className="w-5 h-5 text-red-500" />
            <span className="text-red-700">{error}</span>
            <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700">
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-6 mt-6">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
          <button
            onClick={() => setActiveTab('users')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${
              activeTab === 'users' ? 'bg-white shadow text-gray-900' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Users className="w-4 h-4" />
            Users ({users.length})
          </button>
          <button
            onClick={() => setActiveTab('system')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${
              activeTab === 'system' ? 'bg-white shadow text-gray-900' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Activity className="w-4 h-4" />
            System Health
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        {activeTab === 'users' && (
          <div className="space-y-4">
            {/* Search and Actions */}
            <div className="flex gap-4 items-center">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search users by name, email, or role..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                />
              </div>
              <button
                onClick={globalLogout}
                className="px-4 py-2 bg-red-50 text-red-700 border border-red-200 rounded-lg hover:bg-red-100 transition-all text-sm font-medium flex items-center gap-2"
              >
                <Power className="w-4 h-4" />
                Force Logout All
              </button>
            </div>

            {/* Users Table */}
            <div className="bg-white rounded-xl shadow-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">User</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Role</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Sessions</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Joined</th>
                      <th className="px-6 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {filteredUsers.map((user) => (
                      <React.Fragment key={user.id}>
                        <tr className={`hover:bg-gray-50 ${!user.is_active ? 'opacity-60' : ''}`}>
                          <td className="px-6 py-4">
                            <div>
                              <div className="font-medium text-gray-900">{user.username}</div>
                              <div className="text-sm text-gray-500">{user.email}</div>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium border ${getRoleBadgeColor(user.role)}`}>
                              {user.role}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            {user.is_active ? (
                              <span className="inline-flex items-center gap-1 text-green-700 text-sm">
                                <CheckCircle className="w-3.5 h-3.5" /> Active
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-gray-500 text-sm">
                                <XCircle className="w-3.5 h-3.5" /> Disabled
                              </span>
                            )}
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-600">
                            {user.session_count}
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-500">
                            {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex justify-end gap-2">
                              <button
                                onClick={() => setExpandedUser(expandedUser === user.id ? null : user.id)}
                                className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded"
                                title="Expand"
                              >
                                {expandedUser === user.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                              </button>
                            </div>
                          </td>
                        </tr>
                        {expandedUser === user.id && (
                          <tr>
                            <td colSpan="6" className="bg-gray-50 px-6 py-4">
                              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {/* Role Management */}
                                <div className="bg-white rounded-lg p-4 border">
                                  <h4 className="text-sm font-semibold text-gray-700 mb-3">Change Role</h4>
                                  <div className="flex gap-2">
                                    {['USER', 'OPERATOR', 'ADMIN'].map((role) => (
                                      <button
                                        key={role}
                                        onClick={() => updateUserRole(user.id, role)}
                                        disabled={user.role === role}
                                        className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                                          user.role === role
                                            ? 'bg-purple-100 text-purple-700 border border-purple-200'
                                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200 border border-gray-200'
                                        }`}
                                      >
                                        {role}
                                      </button>
                                    ))}
                                  </div>
                                </div>

                                {/* Account Status */}
                                <div className="bg-white rounded-lg p-4 border">
                                  <h4 className="text-sm font-semibold text-gray-700 mb-3">Account Status</h4>
                                  <button
                                    onClick={() => toggleUserActive(user.id, user.is_active)}
                                    disabled={user.id === currentUser?.id}
                                    className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                                      user.is_active
                                        ? 'bg-red-50 text-red-700 border border-red-200 hover:bg-red-100'
                                        : 'bg-green-50 text-green-700 border border-green-200 hover:bg-green-100'
                                    } ${user.id === currentUser?.id ? 'opacity-50 cursor-not-allowed' : ''}`}
                                  >
                                    {user.is_active ? 'Disable Account' : 'Enable Account'}
                                  </button>
                                  {user.id === currentUser?.id && (
                                    <p className="text-xs text-gray-400 mt-2">Cannot modify own account</p>
                                  )}
                                </div>

                                {/* Sessions */}
                                <div className="bg-white rounded-lg p-4 border">
                                  <h4 className="text-sm font-semibold text-gray-700 mb-3">Sessions</h4>
                                  <button
                                    onClick={() => revokeUserSessions(user.id)}
                                    disabled={user.session_count === 0}
                                    className="px-3 py-1.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 transition-all flex items-center gap-1.5"
                                  >
                                    <RotateCcw className="w-3.5 h-3.5" />
                                    Revoke All Sessions
                                  </button>
                                  <p className="text-xs text-gray-400 mt-2">{user.session_count} active session(s)</p>
                                </div>
                              </div>

                              {/* Auth Providers */}
                              {user.auth_providers && user.auth_providers.length > 0 && (
                                <div className="mt-3 flex gap-2 items-center">
                                  <span className="text-xs text-gray-500">Auth providers:</span>
                                  {user.auth_providers.map((provider) => (
                                    <span key={provider} className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                                      {provider}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'system' && systemHealth && (
          <div className="space-y-6">
            {/* Health Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl shadow p-6">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-purple-100 rounded-lg">
                    <Users className="w-6 h-6 text-purple-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-gray-900">{systemHealth.users.total}</p>
                    <p className="text-sm text-gray-500">Total Users</p>
                  </div>
                </div>
                <div className="mt-3 text-xs text-gray-400">
                  {systemHealth.users.active} active
                </div>
              </div>

              <div className="bg-white rounded-xl shadow p-6">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-blue-100 rounded-lg">
                    <Activity className="w-6 h-6 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-gray-900">{systemHealth.games.active}</p>
                    <p className="text-sm text-gray-500">Active Games</p>
                  </div>
                </div>
                <div className="mt-3 text-xs text-gray-400">
                  {systemHealth.games.total} / {systemHealth.games.max} max
                </div>
              </div>

              <div className="bg-white rounded-xl shadow p-6">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-green-100 rounded-lg">
                    <Database className="w-6 h-6 text-green-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-gray-900">{systemHealth.cards.persistent}</p>
                    <p className="text-sm text-gray-500">Persistent Cards</p>
                  </div>
                </div>
                <div className="mt-3 text-xs text-gray-400">
                  {systemHealth.cards.ephemeral} in-memory
                </div>
              </div>

              <div className="bg-white rounded-xl shadow p-6">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-amber-100 rounded-lg">
                    <Shield className="w-6 h-6 text-amber-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-gray-900">{systemHealth.sessions.active}</p>
                    <p className="text-sm text-gray-500">Active Sessions</p>
                  </div>
                </div>
                <div className="mt-3 text-xs text-gray-400">
                  {systemHealth.sessions.total} total
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="bg-white rounded-xl shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h3>
              <div className="flex gap-3">
                <button
                  onClick={globalLogout}
                  className="px-4 py-2 bg-red-50 text-red-700 border border-red-200 rounded-lg hover:bg-red-100 transition-all text-sm font-medium flex items-center gap-2"
                >
                  <Power className="w-4 h-4" />
                  Force Logout All Users
                </button>
                <button
                  onClick={fetchSystemHealth}
                  className="px-4 py-2 bg-gray-50 text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-100 transition-all text-sm font-medium flex items-center gap-2"
                >
                  <RotateCcw className="w-4 h-4" />
                  Refresh Stats
                </button>
              </div>
            </div>

            {/* System Resources */}
            <div className="bg-white rounded-xl shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Resource Usage</h3>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600">Games</span>
                    <span className="text-gray-900 font-medium">{systemHealth.games.total} / {systemHealth.games.max}</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full transition-all"
                      style={{ width: `${Math.min(100, (systemHealth.games.total / systemHealth.games.max) * 100)}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600">Sessions</span>
                    <span className="text-gray-900 font-medium">{systemHealth.sessions.active} active</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-amber-500 rounded-full transition-all"
                      style={{ width: `${Math.min(100, (systemHealth.sessions.active / Math.max(1, systemHealth.sessions.total)) * 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
