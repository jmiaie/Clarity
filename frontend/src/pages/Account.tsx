import { useState, type FormEvent } from 'react';
import { useAuth } from '../AuthContext';
import { account, browserTimezone, errorMessage } from '../api';
import './Account.css';

type Notice = { kind: 'success' | 'error'; text: string } | null;

export default function Account() {
  const { user, refresh, logout } = useAuth();
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [deletePassword, setDeletePassword] = useState('');

  const deviceZone = browserTimezone();
  const zoneDiffers = Boolean(user && user.timezone !== deviceZone);

  const run = async (action: () => Promise<void>, failure: string) => {
    setNotice(null);
    setBusy(true);
    try {
      await action();
    } catch (err) {
      setNotice({ kind: 'error', text: errorMessage(err, failure) });
    } finally {
      setBusy(false);
    }
  };

  const applyDeviceTimezone = () =>
    run(async () => {
      await account.setTimezone(deviceZone);
      await refresh();
      setNotice({ kind: 'success', text: `Timezone set to ${deviceZone}.` });
    }, 'Could not update your timezone.');

  const changePassword = (e: FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      setNotice({ kind: 'error', text: 'New password must be at least 8 characters.' });
      return;
    }
    run(async () => {
      await account.changePassword(currentPassword, newPassword);
      setCurrentPassword('');
      setNewPassword('');
      setNotice({ kind: 'success', text: 'Password changed.' });
    }, 'Could not change your password.');
  };

  const exportData = () =>
    run(async () => {
      const data = await account.exportData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'clarity-export.json';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setNotice({ kind: 'success', text: 'Your data was downloaded as clarity-export.json.' });
    }, 'Could not export your data.');

  const deleteAccount = (e: FormEvent) => {
    e.preventDefault();
    if (!window.confirm('Delete your account and everything in it? This cannot be undone.')) return;
    run(async () => {
      await account.deleteAccount(deletePassword);
      logout();
    }, 'Could not delete your account.');
  };

  return (
    <div className="account-container">
      <h1>Account</h1>
      <p className="subtitle">{user?.email}</p>

      {notice && (
        <div className={`notice notice-${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}>
          {notice.text}
        </div>
      )}

      <section className="account-section">
        <h2>Timezone</h2>
        <p>
          Entries and patterns use <strong>{user?.timezone}</strong>.
          {zoneDiffers && ` This device is set to ${deviceZone}.`}
        </p>
        {zoneDiffers && (
          <button className="btn-secondary" onClick={applyDeviceTimezone} disabled={busy}>
            Use {deviceZone}
          </button>
        )}
      </section>

      <section className="account-section">
        <h2>Change password</h2>
        <form onSubmit={changePassword} className="account-form">
          <label htmlFor="currentPassword">Current password</label>
          <input
            id="currentPassword"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
          />
          <label htmlFor="newPassword">New password</label>
          <input
            id="newPassword"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            minLength={8}
            required
          />
          <button type="submit" className="btn-secondary" disabled={busy}>
            Change password
          </button>
        </form>
      </section>

      <section className="account-section">
        <h2>Your data</h2>
        <p>
          Only your signed-in account can see your entries in the app. They are stored on our server
          without end-to-end encryption, so treat this like any online notes service. Calendar imports
          keep start and end times only; titles, guests and descriptions are never stored. Patterns are
          computed by counting, on our server. Your entries are not sent to any AI service.
        </p>
        <button className="btn-secondary" onClick={exportData} disabled={busy}>
          Download everything (JSON)
        </button>
      </section>

      <section className="account-section danger-zone">
        <h2>Delete account</h2>
        <p>Removes your account, every journal entry and all calendar data. This cannot be undone.</p>
        <form onSubmit={deleteAccount} className="account-form">
          <label htmlFor="deletePassword">Confirm with your password</label>
          <input
            id="deletePassword"
            type="password"
            autoComplete="current-password"
            value={deletePassword}
            onChange={(e) => setDeletePassword(e.target.value)}
            required
          />
          <button type="submit" className="btn-danger" disabled={busy}>
            Delete my account
          </button>
        </form>
      </section>
    </div>
  );
}
