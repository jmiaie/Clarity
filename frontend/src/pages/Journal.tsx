import { useEffect, useState } from 'react';
import { errorMessage, journal as journalAPI, type JournalEntry, type Mood } from '../api';
import './Journal.css';

const MOODS: Array<{ value: Mood; label: string; emoji: string }> = [
  { value: 'happy', label: '😊 Happy', emoji: '😊' },
  { value: 'energized', label: '⚡ Energized', emoji: '⚡' },
  { value: 'neutral', label: '😐 Neutral', emoji: '😐' },
  { value: 'tired', label: '😴 Tired', emoji: '😴' },
  { value: 'sad', label: '😔 Sad', emoji: '😔' },
];

export default function Journal() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showEditor, setShowEditor] = useState(false);
  const [editingEntry, setEditingEntry] = useState<JournalEntry | null>(null);
  const [error, setError] = useState('');

  // Editor state
  const [content, setContent] = useState('');
  const [mood, setMood] = useState<Mood | ''>('');
  const [tags, setTags] = useState('');
  const [saving, setSaving] = useState(false);

  // Search/filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [moodFilter, setMoodFilter] = useState('');

  const loadEntries = async () => {
    try {
      const data = await journalAPI.listEntries({
        search: searchQuery.trim() || undefined,
        mood: moodFilter || undefined,
        limit: 100,
      });
      setEntries(data);
      setError('');
    } catch (err) {
      setError(errorMessage(err, 'Could not load your entries.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Wait for a pause in typing before searching.
    const timer = window.setTimeout(loadEntries, searchQuery ? 250 : 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery, moodFilter]);

  const closeEditor = () => {
    setShowEditor(false);
    setEditingEntry(null);
    setContent('');
    setMood('');
    setTags('');
  };

  const handleNewEntry = () => {
    closeEditor();
    setError('');
    setShowEditor(true);
  };

  const handleEditEntry = (entry: JournalEntry) => {
    setEditingEntry(entry);
    setContent(entry.content);
    setMood(entry.mood || '');
    setTags(entry.tags || '');
    setError('');
    setShowEditor(true);
  };

  const handleSave = async () => {
    if (!content.trim()) {
      setError('Write something before saving.');
      return;
    }

    setSaving(true);
    try {
      if (editingEntry) {
        await journalAPI.updateEntry(editingEntry.id, { content, mood: mood || null, tags: tags || null });
      } else {
        await journalAPI.createEntry(content, mood || null, tags || null);
      }
      closeEditor();
      await loadEntries();
    } catch (err) {
      setError(errorMessage(err, 'Could not save your entry. Your text is still here; try again.'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Delete this entry? This cannot be undone.')) return;
    try {
      await journalAPI.deleteEntry(id);
      await loadEntries();
    } catch (err) {
      setError(errorMessage(err, 'Could not delete that entry.'));
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) return 'Today';
    if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: date.getFullYear() !== today.getFullYear() ? 'numeric' : undefined,
    });
  };

  const getMoodEmoji = (moodValue: string | null) =>
    MOODS.find((m) => m.value === moodValue)?.emoji ?? null;

  return (
    <div className="journal-container">
      {/* Header */}
      <div className="journal-header">
        <div className="header-left">
          <h1>Journal</h1>
          <p className="subtitle">
            {entries.length} {entries.length === 1 ? 'entry' : 'entries'}
          </p>
        </div>
        <button onClick={handleNewEntry} className="btn-primary">
          + New Entry
        </button>
      </div>

      {error && !showEditor && <div className="notice notice-error" role="alert">{error}</div>}

      {/* Search and Filters */}
      <div className="journal-filters">
        <input
          type="text"
          placeholder="Search entries..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
        />
        
        <select
          value={moodFilter}
          onChange={(e) => setMoodFilter(e.target.value)}
          className="mood-filter"
        >
          <option value="">All Moods</option>
          {MOODS.map(mood => (
            <option key={mood.value} value={mood.value}>
              {mood.label}
            </option>
          ))}
        </select>
      </div>

      {/* Editor Modal */}
      {showEditor && (
        <div className="editor-modal">
          <div className="editor-content">
            <div className="editor-header">
              <h2>{editingEntry ? 'Edit Entry' : 'New Entry'}</h2>
              <button
                onClick={closeEditor}
                className="btn-close"
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <div className="editor-body">
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="How did today go? What helped, what got in the way?"
                maxLength={20000}
                className="entry-textarea"
                autoFocus
              />

              <div className="editor-controls">
                <div className="control-group">
                  <label>How was today overall?</label>
                  <select
                    value={mood}
                    onChange={(e) => setMood(e.target.value as Mood | '')}
                    className="mood-select"
                  >
                    <option value="">Pick a mood (needed for patterns)</option>
                    {MOODS.map(m => (
                      <option key={m.value} value={m.value}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="control-group">
                  <label>Tags</label>
                  <input
                    type="text"
                    value={tags}
                    onChange={(e) => setTags(e.target.value)}
                    placeholder="work, exercise, creative (comma-separated)"
                    className="tags-input"
                  />
                </div>
              </div>

              {error && <div className="notice notice-error" role="alert">{error}</div>}

              <div className="editor-actions">
                <button
                  onClick={closeEditor}
                  className="btn-secondary"
                  disabled={saving}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  className="btn-primary"
                  disabled={saving}
                >
                  {saving ? 'Saving...' : 'Save Entry'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Entries List */}
      <div className="entries-list">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading entries...</p>
          </div>
        ) : entries.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📝</div>
            <h3>No entries yet</h3>
            <p>
              {searchQuery || moodFilter
                ? 'No entries match your filters'
                : 'Start your journey by writing your first entry'}
            </p>
            {!searchQuery && !moodFilter && (
              <button onClick={handleNewEntry} className="btn-primary">
                Write Your First Entry
              </button>
            )}
          </div>
        ) : (
          entries.map((entry) => (
            <div key={entry.id} className="entry-card">
              <div className="entry-header">
                <div className="entry-meta">
                  <span className="entry-date">{formatDate(entry.entry_date)}</span>
                  {entry.mood && (
                    <span className="entry-mood">{getMoodEmoji(entry.mood)}</span>
                  )}
                </div>
                <div className="entry-actions">
                  <button
                    onClick={() => handleEditEntry(entry)}
                    className="btn-icon"
                    title="Edit"
                    aria-label="Edit entry"
                  >
                    ✏️
                  </button>
                  <button
                    onClick={() => handleDelete(entry.id)}
                    className="btn-icon"
                    title="Delete"
                    aria-label="Delete entry"
                  >
                    🗑️
                  </button>
                </div>
              </div>

              <div className="entry-content">
                {entry.content.length > 300
                  ? entry.content.substring(0, 300) + '...'
                  : entry.content}
              </div>

              {entry.tags && (
                <div className="entry-tags">
                  {entry.tags.split(',').map((tag) => (
                    <span key={tag} className="tag">
                      {tag.trim()}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
