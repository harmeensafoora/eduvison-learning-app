import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import axios from 'axios';
import { Quiz } from '../components/Quiz';

/**
 * Learn page - Main learning interface
 * Displays:
 * - Document summary and concepts
 * - Interactive quiz for each concept
 * - Progress tracking
 * - Navigation between concepts
 */
export function Learn() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [session, setSession] = useState(null);
  const [concepts, setConcepts] = useState([]);
  const [currentConceptIdx, setCurrentConceptIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showSummary, setShowSummary] = useState(false);

  useEffect(() => {
    fetchSessionData();
  }, [sessionId]);

  const fetchSessionData = async () => {
    try {
      const [sessionRes, summaryRes] = await Promise.all([
        axios.get(`/api/session/${sessionId}`),
        axios.get(`/api/session/${sessionId}/detailed-summary`)
      ]);

      setSession(sessionRes.data);
      setConcepts(sessionRes.data.concepts_json || []);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load learning session');
      console.error('Session fetch error:', err);
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

  if (error) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6 flex items-center justify-center"
      >
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md text-center">
          <h1 className="text-2xl font-bold text-slate-900 mb-4">Error</h1>
          <p className="text-slate-600 mb-6">{error}</p>
          <button
            onClick={() => navigate('/dashboard')}
            className="bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-6 rounded-lg transition"
          >
            Back to Dashboard
          </button>
        </div>
      </motion.div>
    );
  }

  const currentConcept = concepts[currentConceptIdx];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100"
    >
      {/* Header with Progress */}
      <div className="bg-white shadow-sm border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => navigate('/dashboard')}
              className="text-slate-600 hover:text-slate-900 transition font-medium"
            >
              ← Back
            </button>
            <button
              onClick={() => setShowSummary(!showSummary)}
              className="bg-blue-100 text-blue-700 px-4 py-2 rounded-lg hover:bg-blue-200 transition font-medium"
            >
              {showSummary ? 'Hide' : 'Show'} Summary
            </button>
          </div>

          {/* Progress Bar */}
          <div className="mb-4">
            <div className="flex justify-between items-center mb-2">
              <h3 className="font-semibold text-slate-900">{session?.filename}</h3>
              <span className="text-sm text-slate-600">
                Concept {currentConceptIdx + 1} of {concepts.length}
              </span>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-2">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${((currentConceptIdx + 1) / concepts.length) * 100}%` }}
                transition={{ duration: 0.5 }}
                className="bg-blue-500 h-2 rounded-full"
              ></motion.div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {showSummary ? (
          // Summary View
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-lg shadow-md p-8 mb-8"
          >
            <h2 className="text-2xl font-bold text-slate-900 mb-4">Document Summary</h2>
            <div className="prose prose-sm max-w-none text-slate-700 whitespace-pre-wrap">
              {session?.summary || 'No summary available'}
            </div>

            <div className="mt-8 pt-8 border-t border-slate-200">
              <h3 className="text-lg font-semibold text-slate-900 mb-4">Key Concepts</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {concepts.map((concept, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: idx * 0.05 }}
                    className="p-4 border border-slate-200 rounded-lg hover:bg-blue-50 cursor-pointer transition"
                    onClick={() => {
                      setCurrentConceptIdx(idx);
                      setShowSummary(false);
                    }}
                  >
                    <p className="font-medium text-slate-900">{concept.name}</p>
                    <p className="text-sm text-slate-600 mt-1">{concept.summary}</p>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        ) : (
          // Learning View
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main Content */}
            <div className="lg:col-span-2">
              {currentConcept && (
                <motion.div
                  key={currentConceptIdx}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-white rounded-lg shadow-md p-8"
                >
                  <div className="mb-6">
                    <h2 className="text-2xl font-bold text-slate-900">{currentConcept.name}</h2>
                    <p className="text-slate-600 mt-2">{currentConcept.summary}</p>
                  </div>

                  {currentConcept.prerequisites_json?.length > 0 && (
                    <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                      <p className="text-sm font-medium text-blue-900">Prerequisites:</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {currentConcept.prerequisites_json.map((prereq, idx) => (
                          <span key={idx} className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                            {prereq}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <Quiz conceptId={currentConcept.id} />
                </motion.div>
              )}
            </div>

            {/* Sidebar - Navigation */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
              className="bg-white rounded-lg shadow-md p-6 h-fit sticky top-24"
            >
              <h3 className="font-semibold text-slate-900 mb-4">Concepts</h3>
              <div className="space-y-2">
                {concepts.map((concept, idx) => (
                  <motion.button
                    key={idx}
                    whileHover={{ scale: 1.02 }}
                    onClick={() => setCurrentConceptIdx(idx)}
                    className={`w-full text-left p-3 rounded-lg transition ${
                      currentConceptIdx === idx
                        ? 'bg-blue-500 text-white'
                        : 'bg-slate-100 text-slate-900 hover:bg-slate-200'
                    }`}
                  >
                    <p className="text-sm font-medium">{concept.name}</p>
                    <p className="text-xs opacity-75 mt-1">
                      {concept.estimated_minutes} min
                    </p>
                  </motion.button>
                ))}
              </div>

              {/* Navigation Buttons */}
              <div className="flex gap-2 mt-6 pt-6 border-t border-slate-200">
                <button
                  onClick={() => setCurrentConceptIdx(Math.max(0, currentConceptIdx - 1))}
                  disabled={currentConceptIdx === 0}
                  className="flex-1 py-2 px-3 bg-slate-100 text-slate-900 rounded-lg hover:bg-slate-200 disabled:opacity-50 transition font-medium"
                >
                  ← Prev
                </button>
                <button
                  onClick={() => setCurrentConceptIdx(Math.min(concepts.length - 1, currentConceptIdx + 1))}
                  disabled={currentConceptIdx === concepts.length - 1}
                  className="flex-1 py-2 px-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 transition font-medium"
                >
                  Next →
                </button>
              </div>

              {currentConceptIdx === concepts.length - 1 && (
                <motion.button
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  onClick={() => navigate('/dashboard')}
                  className="w-full mt-3 py-2 px-3 bg-green-500 text-white rounded-lg hover:bg-green-600 transition font-medium"
                >
                  ✓ Complete Learning
                </motion.button>
              )}
            </motion.div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

export default Learn;
