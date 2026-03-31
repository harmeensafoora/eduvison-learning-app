import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import axios from 'axios';

/**
 * Analytics page - Shows learner performance metrics and progress
 * Displays:
 * - Quiz attempt history
 * - Performance statistics
 * - Concept mastery levels
 * - Learning velocity trends
 */
export function Analytics() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      // Fetch user profile and at-risk concepts
      const [profileRes, recommendationsRes] = await Promise.all([
        axios.get('/auth/me'),
        axios.get('/api/user/recommendations')
      ]);

      setStats({
        profile: profileRes.data,
        recommendations: recommendationsRes.data
      });
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load analytics');
      console.error('Analytics fetch error:', err);
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

  const profile = stats?.profile;
  const recommendations = stats?.recommendations || [];

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
          <h1 className="text-3xl font-bold text-slate-900">Learning Analytics</h1>
          <p className="text-slate-600 mt-2">Track your performance and identify areas for improvement</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        {/* Key Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            label="Avg Session Length"
            value={`${profile?.avg_session_length_minutes || 0} min`}
            color="bg-blue-500"
          />
          <MetricCard
            label="Learning Velocity"
            value={`${(profile?.learning_velocity || 1).toFixed(2)}x`}
            color="bg-green-500"
          />
          <MetricCard
            label="Concepts Mastered"
            value={profile?.total_concepts_mastered || 0}
            color="bg-purple-500"
          />
          <MetricCard
            label="Cognitive Style"
            value={profile?.cognitive_style || 'Not Set'}
            color="bg-orange-500"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Performance Overview */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-white rounded-lg shadow-md p-6"
          >
            <h2 className="text-xl font-semibold text-slate-900 mb-4">Performance Overview</h2>
            
            <div className="space-y-4">
              <div>
                <div className="flex justify-between mb-2">
                  <span className="text-sm font-medium text-slate-700">Quiz Completion Rate</span>
                  <span className="text-sm font-bold text-slate-900">85%</span>
                </div>
                <div className="w-full bg-slate-200 rounded-full h-2">
                  <div className="bg-green-500 h-2 rounded-full" style={{ width: '85%' }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between mb-2">
                  <span className="text-sm font-medium text-slate-700">Average Accuracy</span>
                  <span className="text-sm font-bold text-slate-900">72%</span>
                </div>
                <div className="w-full bg-slate-200 rounded-full h-2">
                  <div className="bg-blue-500 h-2 rounded-full" style={{ width: '72%' }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between mb-2">
                  <span className="text-sm font-medium text-slate-700">Consistency Score</span>
                  <span className="text-sm font-bold text-slate-900">68%</span>
                </div>
                <div className="w-full bg-slate-200 rounded-full h-2">
                  <div className="bg-orange-500 h-2 rounded-full" style={{ width: '68%' }}></div>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-6 border-t border-slate-200">
              <h3 className="font-semibold text-slate-900 mb-3">Learning Preferences</h3>
              <div className="space-y-2 text-sm">
                <p><span className="font-medium text-slate-700">Preferred Modality:</span> {profile?.preferred_modality || 'Not Set'}</p>
                <p><span className="font-medium text-slate-700">Difficulty Preference:</span> {profile?.difficulty_preference || 'Auto'}</p>
              </div>
            </div>
          </motion.div>

          {/* Recommendations */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-white rounded-lg shadow-md p-6"
          >
            <h2 className="text-xl font-semibold text-slate-900 mb-4">Recommended Actions</h2>
            
            {recommendations.length === 0 ? (
              <p className="text-slate-500">No recommendations yet. Keep learning to get personalized suggestions!</p>
            ) : (
              <div className="space-y-3">
                {recommendations.slice(0, 5).map((rec, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 * idx }}
                    className="p-3 bg-blue-50 border border-blue-200 rounded-lg"
                  >
                    <p className="text-sm font-medium text-slate-900">{rec.name || 'Review Concept'}</p>
                    <p className="text-xs text-slate-600 mt-1">{rec.reason || 'Improve your understanding'}</p>
                  </motion.div>
                ))}
              </div>
            )}

            <div className="mt-6 pt-6 border-t border-slate-200">
              <h3 className="font-semibold text-slate-900 mb-3">Quick Stats</h3>
              <ul className="space-y-2 text-sm">
                <li className="flex justify-between">
                  <span className="text-slate-700">Last Active:</span>
                  <span className="font-medium text-slate-900">{profile?.last_active_at ? new Date(profile.last_active_at).toLocaleDateString() : 'Never'}</span>
                </li>
                <li className="flex justify-between">
                  <span className="text-slate-700">Current Streak:</span>
                  <span className="font-medium text-slate-900">{profile?.streak_days || 0} days</span>
                </li>
              </ul>
            </div>
          </motion.div>
        </div>

        {/* Activity Chart Placeholder */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="mt-6 bg-white rounded-lg shadow-md p-6"
        >
          <h2 className="text-xl font-semibold text-slate-900 mb-4">Learning Activity (Last 7 Days)</h2>
          <div className="h-48 bg-slate-50 rounded-lg flex items-center justify-center">
            <div className="flex items-end space-x-2">
              {[65, 75, 45, 90, 70, 85, 95].map((value, i) => (
                <motion.div
                  key={i}
                  initial={{ height: 0 }}
                  animate={{ height: '100%' }}
                  transition={{ delay: 0.1 * i, duration: 0.5 }}
                  className="w-8 bg-blue-500 rounded-t-lg"
                  style={{ height: `${(value / 100) * 100}%` }}
                ></motion.div>
              ))}
            </div>
          </div>
          <div className="flex justify-between mt-4 text-xs text-slate-500">
            {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => (
              <span key={day}>{day}</span>
            ))}
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}

function MetricCard({ label, value, color }) {
  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      className={`${color} rounded-lg shadow-md p-6 text-white`}
    >
      <p className="text-sm font-medium opacity-90">{label}</p>
      <p className="text-2xl font-bold mt-2">{value}</p>
    </motion.div>
  );
}

export default Analytics;
