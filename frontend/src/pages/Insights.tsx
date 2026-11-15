import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { errorMessage, insights as insightsAPI, type Insight, type InsightsResponse } from '../api';
import './Insights.css';

function badge(insight: Insight): { label: string; tone: string } {
  if (insight.status === 'pattern') {
    return insight.strength === 'consistent'
      ? { label: 'Consistent pattern', tone: 'strong' }
      : { label: 'Early signal', tone: 'early' };
  }
  if (insight.status === 'info') return { label: 'About your habit', tone: 'info' };
  if (insight.status === 'no_pattern') return { label: 'No clear link yet', tone: 'neutral' };
  return { label: 'Collecting data', tone: 'pending' };
}

function basis(insight: Insight): string | null {
  if (insight.status === 'need_more_data') return null;
  const days = insight.evidence.days;
  if (typeof days === 'number' && days > 0) return `Based on ${days} day${days === 1 ? '' : 's'} of your data`;
  const entries = insight.evidence.entries;
  if (typeof entries === 'number' && entries > 0) return `Based on ${entries} entr${entries === 1 ? 'y' : 'ies'}`;
  return null;
}

export default function Insights() {
  const navigate = useNavigate();
  const [data, setData] = useState<InsightsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      setData(await insightsAPI.get());
    } catch (err) {
      setError(errorMessage(err, 'Could not load your patterns.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const found = data?.patterns_found ?? 0;

  return (
    <div className="insights-container">
      <div className="insights-header">
        <div className="header-left">
          <h1>Patterns</h1>
          <p className="subtitle">
            {found > 0
              ? `${found} pattern${found === 1 ? '' : 's'} in your data so far`
              : 'What your journal and calendar show together'}
          </p>
        </div>
        <button onClick={load} className="btn-secondary" disabled={loading}>
          {loading ? 'Checking...' : '🔄 Refresh'}
        </button>
      </div>

      {error && <div className="notice notice-error" role="alert">{error}</div>}

      {loading && !data ? (
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Looking through your entries...</p>
        </div>
      ) : data ? (
        <>
          {data.entries === 0 && (
            <div className="notice notice-info">
              Nothing to analyse yet. Write a short entry and pick a mood each day; patterns appear once
              there are enough days to compare.
            </div>
          )}
          {data.entries > 0 && !data.has_calendar && (
            <div className="notice notice-info">
              Add your calendar to compare your mood with how full your days are.{' '}
              <button className="link-button" onClick={() => navigate('/calendar')}>
                Upload it
              </button>
            </div>
          )}

          <div className="insights-list">
            {data.insights.map((insight) => {
              const tag = badge(insight);
              const based = basis(insight);
              return (
                <article key={insight.id} className={`insight-item insight-${tag.tone}`}>
                  <div className="insight-header-row">
                    <h3 className="insight-title">{insight.title}</h3>
                    <span className={`status-chip chip-${tag.tone}`}>{tag.label}</span>
                  </div>
                  <p className="insight-text">{insight.text}</p>
                  {insight.progress && (
                    <div
                      className="progress-track"
                      role="progressbar"
                      aria-valuemin={0}
                      aria-valuemax={insight.progress.need}
                      aria-valuenow={Math.min(insight.progress.have, insight.progress.need)}
                    >
                      <div
                        className="progress-bar-fill"
                        style={{
                          width: `${Math.min(100, (insight.progress.have / insight.progress.need) * 100)}%`,
                        }}
                      ></div>
                    </div>
                  )}
                  {insight.suggestion && <p className="insight-suggestion">{insight.suggestion}</p>}
                  {based && <p className="insight-basis">{based}</p>}
                </article>
              );
            })}
          </div>

          <div className="explanation-section">
            <h3>How to read these</h3>
            <p>{data.method_note}</p>
            <ul>
              <li>
                <strong>Early signal</strong> means the difference showed up but rests on few days. It may
                fade as you add more.
              </li>
              <li>
                <strong>Consistent pattern</strong> means it held across at least 20 days and is unlikely to
                be chance.
              </li>
              <li>
                A <strong>good day</strong> is one where the moods you logged were more positive (happy,
                energized) than negative (tired, sad).
              </li>
            </ul>
          </div>
        </>
      ) : null}
    </div>
  );
}
