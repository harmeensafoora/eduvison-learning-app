import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import axios from 'axios';

/**
 * Dashboard page - Shows learner overview and progress summary
 * Displays:
 * - Recently uploaded documents
 * - Learning streak
 * - Concepts mastered
 * - Recommended next steps
 */
export function Dashboard() {
  const [documents, setDocuments] = useState([]);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [docsRes, profileRes] = await Promise.all([
        axios.get('/api/user/documents'),
        axios.get('/auth/me')
      ]);
      setDocuments(docsRes.data);
      setProfile(profileRes.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load dashboard');
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6"
    >
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900">
            Welcome back, {profile?.display_name || 'Learner'}!
          </h1>
          <p className="text-slate-600 mt-2">Track your learning progress and continue where you left off</p>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <StatCard
            title="Concepts Mastered"
            value={profile?.total_concepts_mastered || 0}
            subtitle="Total concepts learned"
          />
          <StatCard
            title="Learning Streak"
            value={profile?.streak_days || 0}
            subtitle="Days in a row"
          />
          <StatCard
            title="Documents"
            value={documents.length}
            subtitle="PDFs uploaded"
          />
        </div>

        {/* Recent Documents */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold text-slate-900 mb-4">Recent Documents</h2>
          {documents.length === 0 ? (
            <p className="text-slate-500">No documents yet. Upload your first PDF to get started!</p>
          ) : (
            <div className="space-y-3">
              {documents.map((doc, idx) => (
                <motion.div
                  key={doc.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="p-4 border border-slate-200 rounded-lg hover:bg-slate-50 cursor-pointer transition"
                >
                  <div className="flex justify-between items-center">
                    <div>
                      <p className="font-medium text-slate-900">{doc.filename}</p>
                      <p className="text-sm text-slate-500">{new Date(doc.created_at).toLocaleDateString()}</p>
                    </div>
                    <span className={`px-3 py-1 rounded text-sm font-medium ${
                      doc.status === 'complete' ? 'bg-green-100 text-green-800' :
                      doc.status === 'processing' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-slate-100 text-slate-800'
                    }`}>
                      {doc.status}
                    </span>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="mt-8">
          <h2 className="text-xl font-semibold text-slate-900 mb-4">Quick Actions</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <ActionButton label="Upload PDF" icon="📤" href="/upload" />
            <ActionButton label="My Analytics" icon="📊" href="/analytics" />
            <ActionButton label="Settings" icon="⚙️" href="/settings" />
            <ActionButton label="Help" icon="❓" href="/help" />
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function StatCard({ title, value, subtitle }) {
  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      className="bg-white rounded-lg shadow-md p-6 border-l-4 border-blue-500"
    >
      <p className="text-slate-600 text-sm font-medium">{title}</p>
      <p className="text-3xl font-bold text-slate-900 mt-2">{value}</p>
      <p className="text-slate-500 text-xs mt-1">{subtitle}</p>
    </motion.div>
  );
}

function ActionButton({ label, icon, href }) {
  return (
    <motion.a
      href={href}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      className="bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-lg p-4 text-center font-medium hover:shadow-lg transition"
    >
      <div className="text-2xl mb-2">{icon}</div>
      {label}
    </motion.a>
  );
}

export default Dashboard;
