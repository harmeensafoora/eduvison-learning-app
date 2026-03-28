import { motion } from 'framer-motion';

/**
 * QuestionCard component - Displays individual quiz question with options
 * Features:
 * - Radio button selection
 * - Animated transitions
 * - Question number display
 * - Distractors with visual feedback
 */
export const QuestionCard = ({ 
  question, 
  userAnswer, 
  onAnswerChange, 
  isSubmitted,
  questionNumber,
  totalQuestions 
}) => {
  const isAnswered = userAnswer !== undefined && userAnswer !== null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
      className="question-card"
      style={{
        background: 'white',
        borderRadius: '12px',
        padding: '24px',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.1)',
        marginBottom: '24px',
      }}
    >
      {/* Question Header */}
      <div style={{ marginBottom: '16px' }}>
        <div style={{
          fontSize: '12px',
          fontWeight: '600',
          color: '#667eea',
          letterSpacing: '0.5px',
          marginBottom: '8px',
          textTransform: 'uppercase',
        }}>
          Question {questionNumber} of {totalQuestions}
        </div>
        <h2 style={{
          fontSize: '18px',
          fontWeight: '600',
          color: '#1a1a1a',
          margin: 0,
          lineHeight: '1.5',
        }}>
          {question.question_text}
        </h2>
      </div>

      {/* Options */}
      <div style={{ marginTop: '20px' }}>
        <fieldset style={{ border: 'none', padding: 0, margin: 0 }}>
          <legend style={{ display: 'none' }}>Select the correct answer</legend>
          {question.distractors && question.distractors.length > 0 && (
            <div>
              {question.distractors.map((option, idx) => (
                <motion.label
                  key={idx}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: idx * 0.1 }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '12px 16px',
                    marginBottom: '12px',
                    border: '2px solid',
                    borderColor: userAnswer === option ? '#667eea' : '#e0e0e0',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    backgroundColor: userAnswer === option ? '#f0f4ff' : 'transparent',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!isSubmitted) {
                      e.currentTarget.style.borderColor = '#667eea';
                      e.currentTarget.style.backgroundColor = '#f9f9ff';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSubmitted) {
                      e.currentTarget.style.borderColor = userAnswer === option ? '#667eea' : '#e0e0e0';
                      e.currentTarget.style.backgroundColor = userAnswer === option ? '#f0f4ff' : 'transparent';
                    }
                  }}
                >
                  <input
                    type="radio"
                    name={`question-${question.id}`}
                    value={option}
                    checked={userAnswer === option}
                    onChange={() => onAnswerChange(question.id, option)}
                    disabled={isSubmitted}
                    style={{
                      width: '18px',
                      height: '18px',
                      marginRight: '12px',
                      cursor: isSubmitted ? 'not-allowed' : 'pointer',
                      accentColor: '#667eea',
                    }}
                  />
                  <span style={{
                    fontSize: '14px',
                    fontWeight: '500',
                    color: '#333',
                    flex: 1,
                  }}>
                    {option}
                  </span>
                </motion.label>
              ))}

              {/* Correct Answer */}
              {isSubmitted && question.correct_answer && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.3 }}
                  style={{
                    marginTop: '16px',
                    padding: '12px 16px',
                    backgroundColor: '#f0fff4',
                    borderLeft: '4px solid #4caf50',
                    borderRadius: '4px',
                  }}
                >
                  <div style={{ fontSize: '12px', fontWeight: '600', color: '#2e7d32' }}>
                    Correct Answer
                  </div>
                  <div style={{ fontSize: '14px', color: '#1b5e20', fontWeight: '500' }}>
                    {question.correct_answer}
                  </div>
                </motion.div>
              )}

              {/* Explanation */}
              {isSubmitted && question.explanation && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.4 }}
                  style={{
                    marginTop: '16px',
                    padding: '12px 16px',
                    backgroundColor: '#fff3e0',
                    borderLeft: '4px solid #ff9800',
                    borderRadius: '4px',
                  }}
                >
                  <div style={{ fontSize: '12px', fontWeight: '600', color: '#e65100', marginBottom: '4px' }}>
                    Explanation
                  </div>
                  <div style={{ fontSize: '13px', color: '#bf360c', lineHeight: '1.5' }}>
                    {question.explanation}
                  </div>
                </motion.div>
              )}
            </div>
          )}
        </fieldset>
      </div>

      {/* Answer Status */}
      {isAnswered && !isSubmitted && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          style={{
            marginTop: '16px',
            fontSize: '12px',
            fontWeight: '600',
            color: '#4caf50',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <span style={{ fontSize: '16px' }}>✓</span>
          Answer recorded
        </motion.div>
      )}
    </motion.div>
  );
};
