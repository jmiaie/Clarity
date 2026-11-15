import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { assessment as assessmentAPI, errorMessage, type QuizProfile, type QuizQuestion } from '../api';
import './Assessment.css';

const QUESTIONS_PER_PAGE = 5;

export default function Assessment() {
  const navigate = useNavigate();
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [disclaimer, setDisclaimer] = useState('');
  // question id -> chosen option id ("a".."d")
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [profile, setProfile] = useState<QuizProfile | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    Promise.all([assessmentAPI.getProfile(), assessmentAPI.getQuestions()])
      .then(([existing, quiz]) => {
        if (cancelled) return;
        if (existing.has_profile) setProfile(existing.profile);
        setQuestions(quiz.questions);
        setDisclaimer(quiz.disclaimer);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err, 'Could not load the quiz.'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const totalPages = Math.max(1, Math.ceil(questions.length / QUESTIONS_PER_PAGE));
  const currentQuestions = questions.slice(
    currentStep * QUESTIONS_PER_PAGE,
    (currentStep + 1) * QUESTIONS_PER_PAGE,
  );
  const pageComplete = currentQuestions.every((q) => answers[q.id]);
  const answeredCount = Object.keys(answers).length;

  const goTo = (step: number) => {
    setCurrentStep(step);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleSubmit = async () => {
    setError('');
    setSubmitting(true);
    try {
      const payload: Record<string, string> = {};
      for (const [questionId, optionId] of Object.entries(answers)) payload[questionId] = optionId;
      const result = await assessmentAPI.submit(payload);
      setProfile(result.profile);
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(errorMessage(err, 'Could not score your answers. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetake = async () => {
    if (!window.confirm('Retake the quiz? Your current result will be cleared.')) return;
    try {
      await assessmentAPI.reset();
      setProfile(null);
      setAnswers({});
      setCurrentStep(0);
    } catch (err) {
      setError(errorMessage(err, 'Could not reset the quiz.'));
    }
  };

  if (loading) {
    return (
      <div className="assessment-container">
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Loading quiz...</p>
        </div>
      </div>
    );
  }

  if (profile) {
    return (
      <div className="assessment-container">
        <div className="profile-result">
          <div className="profile-header">
            <div className="profile-emoji">{profile.profile_emoji}</div>
            <h1>{profile.profile_name}</h1>
            <p className="profile-description">{profile.description}</p>
          </div>

          {error && <div className="notice notice-error" role="alert">{error}</div>}

          <div className="profile-sections">
            <div className="profile-section">
              <h3>💪 Strengths</h3>
              <ul>
                {profile.strengths.map((strength) => (
                  <li key={strength}>{strength}</li>
                ))}
              </ul>
            </div>

            <div className="profile-section">
              <h3>📅 A schedule to try</h3>
              <p>{profile.optimal_schedule}</p>
            </div>

            <div className="profile-section">
              <h3>👥 Meetings</h3>
              <p>{profile.meeting_preference}</p>
            </div>

            <div className="profile-section">
              <h3>💡 Ideas to test</h3>
              <ul>
                {profile.tips.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>
            </div>
          </div>

          <p className="quiz-disclaimer">{profile.disclaimer || disclaimer}</p>

          <div className="profile-actions">
            <button onClick={() => navigate('/dashboard')} className="btn-primary">
              Back to home
            </button>
            <button onClick={handleRetake} className="btn-secondary">
              Retake quiz
            </button>
          </div>
        </div>
      </div>
    );
  }

  const progress = ((currentStep + 1) / totalPages) * 100;

  return (
    <div className="assessment-container">
      <div className="assessment-header">
        <h1>Work-style quiz</h1>
        <p className="subtitle">Twenty quick questions about how you like to work</p>

        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${progress}%` }}></div>
        </div>
        <p className="progress-text">
          Step {currentStep + 1} of {totalPages} · {answeredCount}/{questions.length} answered
        </p>
      </div>

      {error && <div className="notice notice-error" role="alert">{error}</div>}

      <div className="questions-section">
        {currentQuestions.map((question) => (
          <fieldset key={question.id} className="question-card">
            <legend className="question-text">
              {question.id}. {question.text}
            </legend>
            <div className="options-list">
              {question.options.map((option) => {
                const selected = answers[question.id] === option.id;
                return (
                  <label key={option.id} className={`option-item ${selected ? 'selected' : ''}`}>
                    <input
                      type="radio"
                      name={`question-${question.id}`}
                      value={option.id}
                      checked={selected}
                      onChange={() => setAnswers((previous) => ({ ...previous, [question.id]: option.id }))}
                    />
                    <span className="option-text">{option.text}</span>
                    <span className="option-checkmark">✓</span>
                  </label>
                );
              })}
            </div>
          </fieldset>
        ))}
      </div>

      <div className="assessment-actions">
        {currentStep > 0 && (
          <button onClick={() => goTo(currentStep - 1)} className="btn-secondary">
            ← Back
          </button>
        )}

        <div className="spacer"></div>

        {currentStep < totalPages - 1 ? (
          <button onClick={() => goTo(currentStep + 1)} className="btn-primary" disabled={!pageComplete}>
            Next →
          </button>
        ) : (
          <button onClick={handleSubmit} className="btn-primary" disabled={!pageComplete || submitting}>
            {submitting ? 'Scoring...' : 'See my result'}
          </button>
        )}
      </div>

      {disclaimer && <p className="quiz-disclaimer">{disclaimer}</p>}
    </div>
  );
}
