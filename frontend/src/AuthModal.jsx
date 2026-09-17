import React, { useState } from 'react';
import { User, Lock, Key, Mail, LogOut, X, ShieldAlert, Check } from 'lucide-react';

export const AuthModal = ({ isOpen, onClose, currentUser, onAuthSuccess, onLogout, apiBaseUrl }) => {
  const [tab, setTab] = useState('login'); // 'login' | 'register' | 'password'
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    currentPassword: '',
    newPassword: '',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setError('');
    setSuccess('');
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const res = await fetch(`${apiBaseUrl}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        credentials: 'include',
        body: JSON.stringify({
          username: formData.username,
          password: formData.password,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Login failed');
      }

      setSuccess('Logged in successfully!');
      onAuthSuccess(data);
      setTimeout(() => {
        onClose();
        setSuccess('');
      }, 700);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const res = await fetch(`${apiBaseUrl}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        credentials: 'include',
        body: JSON.stringify({
          username: formData.username,
          email: formData.email,
          password: formData.password,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Registration failed');
      }

      setSuccess(`Registered successfully! Role: ${data.role}`);
      onAuthSuccess(data);
      setTimeout(() => {
        onClose();
        setSuccess('');
      }, 1000);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const res = await fetch(`${apiBaseUrl}/auth/password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        credentials: 'include',
        body: JSON.stringify({
          current_password: formData.currentPassword,
          new_password: formData.newPassword,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Password update failed');
      }

      setSuccess('Password updated successfully!');
      setFormData({ ...formData, currentPassword: '', newPassword: '' });
      setTimeout(() => {
        onClose();
        setSuccess('');
      }, 1000);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-md bg-gray-900 border border-yellow-500/50 rounded-2xl shadow-2xl p-6 text-white">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors"
        >
          <X className="w-6 h-6" />
        </button>

        {/* Header Tabs */}
        {currentUser ? (
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-yellow-400 flex items-center gap-2">
              <User className="w-6 h-6" /> Account Management
            </h2>
            <p className="text-sm text-gray-400 mt-1">
              Logged in as <span className="font-semibold text-white">{currentUser.username}</span> ({currentUser.role})
            </p>
          </div>
        ) : (
          <div className="flex border-b border-gray-700 mb-6">
            <button
              onClick={() => {
                setTab('login');
                setError('');
              }}
              className={`flex-1 py-3 font-semibold text-center transition-all ${
                tab === 'login'
                  ? 'text-yellow-400 border-b-2 border-yellow-400'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => {
                setTab('register');
                setError('');
              }}
              className={`flex-1 py-3 font-semibold text-center transition-all ${
                tab === 'register'
                  ? 'text-yellow-400 border-b-2 border-yellow-400'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Register
            </button>
          </div>
        )}

        {/* Error / Success alerts */}
        {error && (
          <div className="mb-4 p-3 bg-red-950/80 border border-red-500 rounded-lg text-red-200 text-sm flex items-start gap-2">
            <ShieldAlert className="w-5 h-5 flex-shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
        )}
        {success && (
          <div className="mb-4 p-3 bg-green-950/80 border border-green-500 rounded-lg text-green-200 text-sm flex items-start gap-2">
            <Check className="w-5 h-5 flex-shrink-0 text-green-400" />
            <span>{success}</span>
          </div>
        )}

        {/* Logged in view */}
        {currentUser ? (
          <div className="space-y-4">
            <form onSubmit={handleChangePassword} className="space-y-3">
              <h3 className="font-semibold text-sm text-yellow-400 uppercase tracking-wider">Change Password</h3>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Current Password</label>
                <input
                  type="password"
                  name="currentPassword"
                  value={formData.currentPassword}
                  onChange={handleChange}
                  required
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-yellow-400 outline-none text-white text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">New Password (min 8 chars)</label>
                <input
                  type="password"
                  name="newPassword"
                  value={formData.newPassword}
                  onChange={handleChange}
                  required
                  minLength={8}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-yellow-400 outline-none text-white text-sm"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-yellow-500 hover:bg-yellow-400 text-black font-bold rounded-lg transition-all disabled:opacity-50 text-sm"
              >
                {loading ? 'Updating...' : 'Update Password'}
              </button>
            </form>

            <div className="pt-4 border-t border-gray-800">
              <button
                type="button"
                onClick={onLogout}
                className="w-full py-2.5 bg-red-600/80 hover:bg-red-600 text-white font-bold rounded-lg transition-all flex items-center justify-center gap-2 text-sm"
              >
                <LogOut className="w-4 h-4" /> Sign Out
              </button>
            </div>
          </div>
        ) : tab === 'login' ? (
          /* Login Form */
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Username or Email</label>
              <div className="relative">
                <User className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  name="username"
                  value={formData.username}
                  onChange={handleChange}
                  required
                  placeholder="admin or user@example.com"
                  className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-yellow-400 outline-none text-white text-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-gray-400 mb-1">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                <input
                  type="password"
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  required
                  className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-yellow-400 outline-none text-white text-sm"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-yellow-500 hover:bg-yellow-400 text-black font-bold rounded-lg transition-all disabled:opacity-50 mt-2"
            >
              {loading ? 'Authenticating...' : 'Sign In'}
            </button>
          </form>
        ) : (
          /* Register Form */
          <form onSubmit={handleRegister} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Username</label>
              <div className="relative">
                <User className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  name="username"
                  value={formData.username}
                  onChange={handleChange}
                  required
                  minLength={3}
                  maxLength={32}
                  placeholder="e.g. operator1"
                  className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-yellow-400 outline-none text-white text-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-gray-400 mb-1">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  required
                  placeholder="operator@example.com"
                  className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-yellow-400 outline-none text-white text-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-gray-400 mb-1">Password (min 8 chars)</label>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                <input
                  type="password"
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  required
                  minLength={8}
                  className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-yellow-400 outline-none text-white text-sm"
                />
              </div>
            </div>

            <p className="text-xs text-gray-400 italic">
              Notice: The first user registered on an unconfigured server automatically receives Administrator privileges.
            </p>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-yellow-500 hover:bg-yellow-400 text-black font-bold rounded-lg transition-all disabled:opacity-50 mt-2"
            >
              {loading ? 'Creating Account...' : 'Register Account'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
