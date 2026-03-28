/**
 * localStorage utilities for persisting quiz state across page reloads
 * Enables users to resume quizzes seamlessly
 */

const STORAGE_PREFIX = 'eduvision_quiz_';

/**
 * Save quiz state to localStorage
 * @param {string} quizId - Unique quiz identifier
 * @param {object} state - Quiz state object {quiz, currentQuestionIndex, userAnswers, isSubmitted}
 */
export const saveQuizState = (quizId, state) => {
  try {
    const key = `${STORAGE_PREFIX}${quizId}`;
    const serialized = JSON.stringify({
      ...state,
      savedAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(), // 7 days
    });
    localStorage.setItem(key, serialized);
    console.debug(`Quiz state saved for ${quizId}`);
  } catch (err) {
    console.error('Failed to save quiz state:', err);
  }
};

/**
 * Load quiz state from localStorage
 * @param {string} quizId - Unique quiz identifier
 * @returns {object|null} - Saved state or null if not found/expired
 */
export const loadQuizState = (quizId) => {
  try {
    const key = `${STORAGE_PREFIX}${quizId}`;
    const serialized = localStorage.getItem(key);
    
    if (!serialized) {
      return null;
    }

    const state = JSON.parse(serialized);
    
    // Check if state has expired
    if (new Date(state.expiresAt) < new Date()) {
      console.debug(`Quiz state expired for ${quizId}`);
      clearQuizState(quizId);
      return null;
    }

    // Return state without metadata
    const { savedAt, expiresAt, ...quizState } = state;
    return quizState;
  } catch (err) {
    console.error('Failed to load quiz state:', err);
    return null;
  }
};

/**
 * Clear quiz state from localStorage
 * @param {string} quizId - Unique quiz identifier
 */
export const clearQuizState = (quizId) => {
  try {
    const key = `${STORAGE_PREFIX}${quizId}`;
    localStorage.removeItem(key);
    console.debug(`Quiz state cleared for ${quizId}`);
  } catch (err) {
    console.error('Failed to clear quiz state:', err);
  }
};

/**
 * Save session state (user, quiz history, preferences)
 * @param {string} sessionId - Unique session identifier
 * @param {object} state - Session state object
 */
export const saveSessionState = (sessionId, state) => {
  try {
    const key = `${STORAGE_PREFIX}session_${sessionId}`;
    const serialized = JSON.stringify({
      ...state,
      savedAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(), // 7 days
    });
    localStorage.setItem(key, serialized);
  } catch (err) {
    console.error('Failed to save session state:', err);
  }
};

/**
 * Load session state from localStorage
 * @param {string} sessionId - Unique session identifier
 * @returns {object|null} - Saved session or null
 */
export const loadSessionState = (sessionId) => {
  try {
    const key = `${STORAGE_PREFIX}session_${sessionId}`;
    const serialized = localStorage.getItem(key);
    
    if (!serialized) {
      return null;
    }

    const state = JSON.parse(serialized);
    
    if (new Date(state.expiresAt) < new Date()) {
      clearSessionState(sessionId);
      return null;
    }

    const { savedAt, expiresAt, ...sessionState } = state;
    return sessionState;
  } catch (err) {
    console.error('Failed to load session state:', err);
    return null;
  }
};

/**
 * Clear session state from localStorage
 * @param {string} sessionId - Unique session identifier
 */
export const clearSessionState = (sessionId) => {
  try {
    const key = `${STORAGE_PREFIX}session_${sessionId}`;
    localStorage.removeItem(key);
  } catch (err) {
    console.error('Failed to clear session state:', err);
  }
};

/**
 * Clear all quiz-related storage
 */
export const clearAllQuizStorage = () => {
  try {
    const keys = Object.keys(localStorage).filter(key => 
      key.startsWith(STORAGE_PREFIX)
    );
    keys.forEach(key => localStorage.removeItem(key));
    console.debug(`Cleared ${keys.length} quiz storage items`);
  } catch (err) {
    console.error('Failed to clear all quiz storage:', err);
  }
};
