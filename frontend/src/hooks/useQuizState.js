import { useState, useEffect, useCallback } from 'react';
import { loadQuizState, saveQuizState, clearQuizState } from '../utils/storage';

/**
 * Custom hook for managing quiz state with localStorage persistence
 * Handles quiz data, user responses, progress tracking, and resumption
 */
export const useQuizState = (quizId) => {
  const [quiz, setQuiz] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [userAnswers, setUserAnswers] = useState({});
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load quiz state from localStorage or initialize
  useEffect(() => {
    const loadState = async () => {
      try {
        setLoading(true);
        
        // Try to resume from localStorage
        const savedState = loadQuizState(quizId);
        if (savedState) {
          setQuiz(savedState.quiz);
          setCurrentQuestionIndex(savedState.currentQuestionIndex);
          setUserAnswers(savedState.userAnswers);
          setIsSubmitted(savedState.isSubmitted);
        } else {
          // If no saved state, would fetch from backend here
          // For now, initialize empty state
          setQuiz(null);
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadState();
  }, [quizId]);

  // Save quiz state to localStorage whenever it changes
  useEffect(() => {
    if (quiz) {
      saveQuizState(quizId, {
        quiz,
        currentQuestionIndex,
        userAnswers,
        isSubmitted,
      });
    }
  }, [quiz, currentQuestionIndex, userAnswers, isSubmitted, quizId]);

  const recordAnswer = useCallback((questionId, answer) => {
    setUserAnswers((prev) => ({
      ...prev,
      [questionId]: answer,
    }));
  }, []);

  const nextQuestion = useCallback(() => {
    if (quiz && currentQuestionIndex < quiz.questions.length - 1) {
      setCurrentQuestionIndex((prev) => prev + 1);
    }
  }, [quiz, currentQuestionIndex]);

  const prevQuestion = useCallback(() => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex((prev) => prev - 1);
    }
  }, [currentQuestionIndex]);

  const goToQuestion = useCallback((index) => {
    if (quiz && index >= 0 && index < quiz.questions.length) {
      setCurrentQuestionIndex(index);
    }
  }, [quiz]);

  const submitQuiz = useCallback(async () => {
    if (quiz) {
      setIsSubmitted(true);
      // Here you would call the backend API to submit responses
      // const response = await submitQuizResponses(quizId, userAnswers);
    }
  }, [quiz, quizId, userAnswers]);

  const resetQuiz = useCallback(() => {
    setCurrentQuestionIndex(0);
    setUserAnswers({});
    setIsSubmitted(false);
    clearQuizState(quizId);
  }, [quizId]);

  const calculateProgress = useCallback(() => {
    if (!quiz) return 0;
    return Math.round(((currentQuestionIndex + 1) / quiz.questions.length) * 100);
  }, [quiz, currentQuestionIndex]);

  const getCurrentQuestion = useCallback(() => {
    if (quiz && quiz.questions && currentQuestionIndex < quiz.questions.length) {
      return quiz.questions[currentQuestionIndex];
    }
    return null;
  }, [quiz, currentQuestionIndex]);

  const getScore = useCallback(() => {
    if (!quiz || !userAnswers) return 0;
    let correctCount = 0;
    quiz.questions.forEach((q) => {
      if (userAnswers[q.id] === q.correctAnswer) {
        correctCount++;
      }
    });
    return Math.round((correctCount / quiz.questions.length) * 100);
  }, [quiz, userAnswers]);

  return {
    quiz,
    setQuiz,
    currentQuestionIndex,
    userAnswers,
    isSubmitted,
    loading,
    error,
    recordAnswer,
    nextQuestion,
    prevQuestion,
    goToQuestion,
    submitQuiz,
    resetQuiz,
    calculateProgress,
    getCurrentQuestion,
    getScore,
  };
};
