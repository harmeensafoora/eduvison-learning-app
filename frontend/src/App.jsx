import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Dashboard } from './pages/Dashboard';
import { Upload } from './pages/Upload';
import { Analytics } from './pages/Analytics';
import { Learn } from './pages/Learn';
import { Quiz } from './components/Quiz';

/**
 * App component - Root component for EduVision frontend
 * Routes between different pages and manages app state
 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Redirect root to dashboard */}
        <Route path="/" element={<Navigate to="/dashboard" />} />
        
        {/* Main application routes */}
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/learn/:sessionId" element={<Learn />} />
        
        {/* Demo/Dev route for testing quiz component */}
        <Route path="/demo/quiz" element={<DemoQuiz />} />
        
        {/* Catch-all redirect */}
        <Route path="*" element={<Navigate to="/dashboard" />} />
      </Routes>
    </BrowserRouter>
  );
}

/**
 * Demo quiz component for development/testing
 */
function DemoQuiz() {
  const sampleQuiz = {
    id: 'quiz-001',
    conceptId: 'concept-001',
    questions: [
      {
        id: 'q1',
        question_text: 'What is the primary function of mitochondria?',
        distractors: [
          'To generate energy (ATP) through cellular respiration',
          'To store genetic information',
          'To produce proteins',
          'To regulate water balance'
        ],
        correct_answer: 'To generate energy (ATP) through cellular respiration',
        explanation: 'Mitochondria is known as the powerhouse of the cell because it produces ATP (adenosine triphosphate) through aerobic respiration, which is the primary energy currency of the cell.',
      },
      {
        id: 'q2',
        question_text: 'Which of the following is NOT a type of protein structure?',
        distractors: [
          'Primary structure',
          'Secondary structure',
          'Tertiary structure',
          'Quaternary force'
        ],
        correct_answer: 'Quaternary force',
        explanation: 'Proteins have primary, secondary, tertiary, and quaternary structures. "Quaternary force" is not a recognized term in protein structure classification.',
      },
      {
        id: 'q3',
        question_text: 'What is the pH range considered neutral?',
        distractors: [
          '0-6',
          '7',
          '8-14',
          '> 14'
        ],
        correct_answer: '7',
        explanation: 'A pH of 7 is considered neutral on the pH scale, where 1-6 is acidic, and 8-14 is basic (alkaline).',
      },
    ],
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        padding: '40px 20px',
      }}
    >
      {/* Header */}
      <header style={{
        maxWidth: '1200px',
        margin: '0 auto 40px auto',
        color: 'white',
        textAlign: 'center',
      }}>
        <motion.h1
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.1 }}
          style={{
            fontSize: '32px',
            fontWeight: '700',
            margin: '0 0 8px 0',
          }}
        >
          EduVision
        </motion.h1>
        <motion.p
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
          style={{
            fontSize: '16px',
            opacity: 0.9,
            margin: '0',
          }}
        >
          Transform PDFs into Interactive Learning Experiences
        </motion.p>
      </header>

      {/* Main Content */}
      <div style={{
        maxWidth: '1200px',
        margin: '0 auto',
      }}>
        <Quiz quizId={sampleQuiz.id} quizData={sampleQuiz} />
      </div>

      {/* Footer */}
      <footer style={{
        maxWidth: '1200px',
        margin: '60px auto 0 auto',
        paddingTop: '24px',
        borderTop: '1px solid rgba(255, 255, 255, 0.1)',
        color: 'rgba(255, 255, 255, 0.7)',
        textAlign: 'center',
        fontSize: '12px',
      }}>
        <p style={{ margin: '0' }}>
          © 2026 EduVision. Developed with React 19 & Framer Motion.
        </p>
      </footer>
    </motion.div>
  );
}
