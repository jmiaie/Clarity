import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { calendar as calendarAPI, errorMessage, type CalendarStats, type UploadResult } from '../api';
import './Calendar.css';

const SKIP_LABELS: Record<string, string> = {
  all_day: 'all-day',
  marked_free: 'marked free',
  cancelled: 'cancelled',
  declined: 'declined',
  too_long: 'longer than 8 hours',
  outside_window: 'outside the last 120 days',
  unreadable: 'unreadable',
};

function formatHour(hour: number | null | undefined): string {
  if (hour === null || hour === undefined) return '–';
  const period = hour >= 12 ? 'PM' : 'AM';
  return `${hour % 12 || 12} ${period}`;
}

function formatDay(iso: string | undefined): string {
  if (!iso) return '';
  // Date-only strings are parsed as UTC; pin to noon so the label cannot slip a day.
  return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function describeSkipped(result: UploadResult): string {
  const parts = Object.entries(result.skipped)
    .filter(([, count]) => count > 0)
    .map(([reason, count]) => `${count} ${SKIP_LABELS[reason] ?? reason}`);
  return parts.length ? ` Left out: ${parts.join(', ')}.` : '';
}

export default function Calendar() {
  const [stats, setStats] = useState<CalendarStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadData = async () => {
    try {
      setStats(await calendarAPI.getStats());
    } catch (error) {
      setNotice({ kind: 'error', text: errorMessage(error, 'Could not load your calendar data.') });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleFileSelect = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setNotice(null);
    setUploading(true);
    try {
      const result = await calendarAPI.upload(file);
      setNotice({
        kind: 'success',
        text: `Imported ${result.imported} events from ${formatDay(result.range_start)} to ${formatDay(
          result.range_end,
        )}.${describeSkipped(result)}`,
      });
      await loadData();
    } catch (error) {
      setNotice({ kind: 'error', text: errorMessage(error, 'Upload failed. Please try again.') });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleClear = async () => {
    if (!window.confirm('Remove all imported calendar data? Your journal is not affected.')) return;
    try {
      await calendarAPI.deleteAll();
      setNotice({ kind: 'success', text: 'Calendar data removed.' });
      await loadData();
    } catch (error) {
      setNotice({ kind: 'error', text: errorMessage(error, 'Could not remove calendar data.') });
    }
  };

  const openFilePicker = () => fileInputRef.current?.click();
  const hasCalendar = Boolean(stats?.has_data);
  const stale = hasCalendar && (stats?.days_since_upload ?? 0) >= 7;

  return (
    <div className="calendar-container">
      <div className="calendar-header">
        <div className="header-left">
          <h1>Calendar</h1>
          <p className="subtitle">
            {hasCalendar
              ? `Last ${stats?.workdays} weekdays: ${formatDay(stats?.range_start)} to ${formatDay(stats?.range_end)}`
              : 'Add your calendar to see how your time is spent'}
          </p>
        </div>
        <button onClick={openFilePicker} className="btn-primary" disabled={uploading}>
          {uploading ? 'Importing...' : hasCalendar ? '🔄 Upload a newer export' : '📤 Upload calendar'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".ics,.csv,text/calendar"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          aria-label="Calendar export file"
        />
      </div>

      {notice && (
        <div className={`notice notice-${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}>
          {notice.text}
        </div>
      )}

      {loading ? (
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Loading calendar data...</p>
        </div>
      ) : !hasCalendar ? (
        <div className="empty-state">
          <div className="empty-icon">📅</div>
          <h3>No calendar yet</h3>
          <p>Export your calendar once and upload the file here.</p>

          <div className="instructions-card">
            <h4>Google Calendar (on a computer)</h4>
            <ol>
              <li>
                Open{' '}
                <a href="https://calendar.google.com" target="_blank" rel="noopener noreferrer">
                  Google Calendar
                </a>
                , then Settings ⚙️ → Import &amp; export
              </li>
              <li>Click Export. A ZIP file downloads.</li>
              <li>Open the ZIP and upload the <strong>.ics</strong> file for your main calendar.</li>
            </ol>
            <h4>Outlook or Apple Calendar</h4>
            <ol>
              <li>Apple Calendar: File → Export → Export, then upload the .ics file.</li>
              <li>Outlook: File → Save Calendar saves an .ics file. An exported .csv also works.</li>
            </ol>
          </div>

          <p className="privacy-note">
            🔒 Only the start and end time of each event is stored. Titles, guests and descriptions are
            discarded during import.
          </p>

          <button onClick={openFilePicker} className="btn-primary btn-large" disabled={uploading}>
            Upload calendar file
          </button>
        </div>
      ) : (
        <>
          {stale && (
            <div className="notice notice-warning">
              This export is {stats?.days_since_upload} days old. Upload a newer one so recent days are
              included in your patterns.
            </div>
          )}

          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-icon">📊</div>
              <div className="stat-value">{stats?.avg_events_per_workday}</div>
              <div className="stat-label">Events per weekday</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">⏱️</div>
              <div className="stat-value">{stats?.avg_hours_per_workday}h</div>
              <div className="stat-label">Scheduled per weekday</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">🎯</div>
              <div className="stat-value">
                {stats?.focus_share != null ? `${Math.round(stats.focus_share * 100)}%` : '–'}
              </div>
              <div className="stat-label">Working hours in open 90-min blocks</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">📅</div>
              <div className="stat-value">{stats?.busiest_weekday ?? '–'}</div>
              <div className="stat-label">Heaviest day</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">🕐</div>
              <div className="stat-value">{formatHour(stats?.busiest_hour)}</div>
              <div className="stat-label">Most common start time</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">🔗</div>
              <div className="stat-value">{stats?.back_to_back_per_week}</div>
              <div className="stat-label">Back-to-back per week</div>
            </div>
          </div>

          {stats?.observations && stats.observations.length > 0 && (
            <div className="insights-section">
              <h2>What your calendar shows</h2>
              <ul className="observation-list">
                {stats.observations.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <p className="method-note">
                Counts timed events on weekdays, with working hours taken as {stats.working_hours}. All-day,
                declined, cancelled and "free" events are left out.
              </p>
            </div>
          )}

          <div className="calendar-actions">
            <button onClick={handleClear} className="btn-secondary">
              🗑️ Remove calendar data
            </button>
          </div>
        </>
      )}
    </div>
  );
}
