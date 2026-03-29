import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { QuestionCard } from './QuestionCard';
import { useQuizState } from '../hooks/useQuizState';

/**
 * Quiz component - Main quiz container with navigation
 * Features:
 * - Question navigation (prev/next/jump to question)
 * - Progress tracking with progress bar
 * - Question overview sidebar
 * - Submit functionality
 * - Results display after submission
 */
export const Quiz = ({ quizData, quizId }) => {
  const {
    quiz,
    setQuiz,
    currentQuestionIndex,
    userAnswers,
    isSubmitted,
    recordAnswer,
    nextQuestion,
    prevQuestion,
    goToQuestion,
    submitQuiz,
    resetQuiz,
    calculateProgress,
    getCurrentQuestion,
    getScore,
  } = useQuizState(quizId);

  // Initialize quiz data
  React.useEffect(() => {
    if (quizData && !quiz) {
      setQuiz(quizData);
    }
  }, [quizData, quiz, setQuiz]);

  if (!quiz) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '400px',
          fontSize: '16px',
          color: '#666',
        }}
      >
        Loading quiz...
      </motion.div>
    );
  }

  const currentQuestion = getCurrentQuestion();
  const progress = calculateProgress();
  const score = getScore();
  const totalQuestions = quiz.questions?.length || 0;
  const answeredQuestions = Object.keys(userAnswers).length;

  return (
    <div style={{
      maxWidth: '1200px',
      margin: '0 auto',
      display: 'grid',
      gridTemplateColumns: '1fr 300px',
      gap: '24px',
      padding: '24px',
    }}>
      {/* Main Content */}
      <div>
        {/* Progress Bar */}
        <div style={{ marginBottom: '32px' }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: '8px',
            fontSize: '13px',
            fontWeight: '600',
            color: '#666',
          }}>
            <span>Progress</span>
            <span>{progress}%</span>
          </div>
          <motion.div
            style={{
              width: '100%',
              height: '8px',
              backgroundColor: '#e0e0e0',
              borderRadius: '4px',
              overflow: 'hidden',
            }}
          >
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.5 }}
              style={{
                height: '100%',
                background: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%)',
                borderRadius: '4px',
              }}
            />
          </motion.div>
        </div>

        {/* Question Content */}
        {!isSubmitted && currentQuestion && (
          <AnimatePresence mode="wait">
            <QuestionCard
              key={currentQuestionIndex}
              question={currentQuestion}
              userAnswer={userAnswers[currentQuestion.id]}
              onAnswerChange={recordAnswer}
              isSubmitted={false}
              questionNumber={currentQuestionIndex + 1}
              totalQuestions={totalQuestions}
            />
          </AnimatePresence>
        )}

        {/* Results Screen */}
        {isSubmitted && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            style={{
              background: 'white',
              borderRadius: '12px',
              padding: '40px 24px',
              textAlign: 'center',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.1)',
            }}
          >
            <div style={{ marginBottom: '24px' }}>
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', delay: 0.2 }}
                style={{
                  fontSize: '64px',
                  fontWeight: 'bold',
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  marginBottom: '16px',
                }}
              >
                {score}%
              </motion.div>
              <h2 style={{
                fontSize: '24px',
                fontWeight: '600',
                color: '#1a1a1a',
                margin: '0 0 8px 0',
              }}>
                Quiz Complete!
              </h2>
              <p style={{
                fontSize: '14px',
                color: '#666',
                margin: '0',
              }}>
                You got {Object.values(userAnswers).filter(
                  (ans, idx) => ans === Object.values(userAnswers)[idx]
                ).length} out of {totalQuestions} questions correct
              </p>
            </div>

            {/* Review Answers Button */}
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => {
                resetQuiz();
              }}
              style={{
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                padding: '12px 24px',
                fontSize: '14px',
                fontWeight: '600',
                cursor: 'pointer',
                marginTop: '16px',
              }}
            >
              Retake Quiz
            </motion.button>
          </motion.div>
        )}

        {/* Navigation Buttons */}
        {!isSubmitted && (
          <div style={{
            display: 'flex',
            gap: '12px',
            marginTop: '32px',
            justifyContent: 'space-between',
          }}>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={prevQuestion}
              disabled={currentQuestionIndex === 0}
              style={{
                padding: '12px 24px',
                backgroundColor: currentQuestionIndex === 0 ? '#e0e0e0' : 'white',
                border: '2px solid #667eea',
                borderRadius: '8px',
                fontSize: '14px',
                fontWeight: '600',
                color: '#667eea',
                cursor: currentQuestionIndex === 0 ? 'not-allowed' : 'pointer',
                opacity: currentQuestionIndex === 0 ? 0.6 : 1,
              }}
            >
              ← Previous
            </motion.button>

            {currentQuestionIndex === totalQuestions - 1 ? (
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={submitQuiz}
                style={{
                  padding: '12px 32px',
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: '600',
                  cursor: 'pointer',
                }}
              >
                Submit Quiz
              </motion.button>
            ) : (
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={nextQuestion}
                style={{
                  padding: '12px 24px',
                  backgroundColor: 'white',
                  border: '2px solid #667eea',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: '600',
                  color: '#667eea',
                  cursor: 'pointer',
                }}
              >
                Next →
              </motion.button>
            )}
          </div>
        )}
      </div>

      {/* Sidebar - Question Overview */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.2 }}
        style={{
          background: 'white',
          borderRadius: '12px',
          padding: '20px',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.1)',
          height: 'fit-content',
          position: 'sticky',
          top: '24px',
        }}
      >
        <h3 style={{
          fontSize: '13px',
          fontWeight: '700',
          color: '#1a1a1a',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          margin: '0 0 16px 0',
        }}>
          Questions
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
          {quiz.questions?.map((q, idx) => (
            <motion.button
              key={idx}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => goToQuestion(idx)}
              style={{
                aspectRatio: '1',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '6px',
                border: currentQuestionIndex === idx ? '2px solid #667eea' : '1px solid #e0e0e0',
                backgroundColor:
                  currentQuestionIndex === idx
                    ? '#667eea'
                    : userAnswers[q.id]
                    ? '#f0f4ff'
                    : 'white',
                color: currentQuestionIndex === idx ? 'white' : '#1a1a1a',
                fontWeight: '600',
                fontSize: '12px',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
            >
              {idx + 1}
            </motion.button>
          ))}
        </div>
        <div style={{
          marginTop: '16px',
          paddingTop: '16px',
          borderTop: '1px solid #e0e0e0',
          fontSize: '12px',
          color: '#666',
        }}>
          <div style={{ marginBottom: '8px' }}>
            Answered: <strong>{answeredQuestions}</strong>/{totalQuestions}
          </div>
          <div>
            Remaining: <strong>{totalQuestions - answeredQuestions}</strong>
          </div>
        </div>
      </motion.div>
    </div>
  );
};
