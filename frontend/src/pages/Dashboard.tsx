import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import {
  assessment,
  calendar,
  insights,
  journal,
  type CalendarStats,
  type Insight,
  type JournalStats,
  type QuizProfile,
} from '../api';
import './Dashboard.css';

const MOOD_EMOJI: Record<string, string> = {
  happy: '😊',
  neutral: '😐',
  sad: '😔',
  energized: '⚡',
  tired: '😴',
};

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [journalStats, setJournalStats] = useState<JournalStats | null>(null);
  const [calendarStats, setCalendarStats] = useState<CalendarStats | null>(null);
  const [highlight, setHighlight] = useState<Insight | null>(null);
  const [profile, setProfile] = useState<QuizProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    // Each panel loads on its own; one failing does not blank the page.
    Promise.all([
      journal.getStats().catch(() => null),
      calendar.getStats().catch(() => null),
      insights.get().catch(() => null),
      assessment.getProfile().catch(() => null),
    ]).then(([jStats, cStats, patterns, quiz]) => {
      if (cancelled) return;
      setJournalStats(jStats);
      setCalendarStats(cStats);
      const list = patterns?.insights ?? [];
      // Lead with a real pattern; otherwise show what is still being collected.
      setHighlight(
        list.find((i) => i.status === 'pattern') ?? list.find((i) => i.status === 'need_more_data') ?? null,
      );
      setProfile(quiz?.has_profile ? quiz.profile : null);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const hasCalendar = Boolean(calendarStats?.has_data);
  const focusShare = calendarStats?.focus_share;

  return (
    <div className="dashboard-content">
      <div className="welcome-section">
        <h2>Welcome back 👋</h2>
        {profile ? (
          <button className="profile-badge" onClick={() => navigate('/assessment')}>
            <span className="profile-badge-emoji">{profile.profile_emoji}</span>
            <span className="profile-name">{profile.profile_name}</span>
          </button>
        ) : (
          <p>{user?.email}</p>
        )}

        {loading ? (
          <div className="loading-stats">
            <div className="spinner"></div>
          </div>
        ) : (
          <>
            <div className="status-grid">
              <button className="status-card clickable" onClick={() => navigate('/journal')}>
                <h3>📝 {journalStats?.total_entries ?? 0}</h3>
                <p>Journal entries</p>
              </button>

              <button className="status-card clickable" onClick={() => navigate('/journal')}>
                <h3>🔥 {journalStats?.entries_this_week ?? 0}</h3>
                <p>In the last 7 days</p>
              </button>

              <button className="status-card clickable" onClick={() => navigate('/journal')}>
                <h3>{journalStats?.dominant_mood ? MOOD_EMOJI[journalStats.dominant_mood] : '–'}</h3>
                <p>Most common mood</p>
              </button>

              <button className="status-card clickable" onClick={() => navigate('/calendar')}>
                <h3>📅 {hasCalendar ? `${calendarStats?.avg_hours_per_workday ?? 0}h` : '–'}</h3>
                <p>{hasCalendar ? 'Scheduled per weekday' : 'No calendar yet'}</p>
              </button>

              <button className="status-card clickable" onClick={() => navigate('/calendar')}>
                <h3>🎯 {hasCalendar && focusShare != null ? `${Math.round(focusShare * 100)}%` : '–'}</h3>
                <p>Working hours in open blocks</p>
              </button>

              <button className="status-card clickable" onClick={() => navigate('/calendar')}>
                <h3>🔗 {hasCalendar ? calendarStats?.back_to_back_per_week ?? 0 : '–'}</h3>
                <p>Back-to-back per week</p>
              </button>
            </div>

            {highlight && (
              <button className="dashboard-insight-preview" onClick={() => navigate('/insights')}>
                <span className="insight-badge">
                  {highlight.status === 'pattern' ? '💡 Pattern in your data' : '⏳ Still collecting'}
                </span>
                <span className="insight-preview-title">{highlight.title}</span>
                <span className="insight-preview-text">{highlight.text}</span>
                <span className="insight-cta">See all patterns →</span>
              </button>
            )}
          </>
        )}

        <div className="dashboard-actions">
          <button onClick={() => navigate('/journal')} className="btn-primary btn-large">
            📝 Write an entry
          </button>
          <button onClick={() => navigate('/calendar')} className="btn-primary btn-large">
            {hasCalendar ? '📅 Calendar' : '📅 Add your calendar'}
          </button>
          {!profile && (
            <button onClick={() => navigate('/assessment')} className="btn-secondary btn-large">
              ✨ Work-style quiz
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
