window.__desktopErrors = [];
window.addEventListener('error', event => window.__desktopErrors.push(event.message));
window.addEventListener('unhandledrejection', event => window.__desktopErrors.push(String(event.reason)));
window.addEventListener('DOMContentLoaded', () => {
  let currentVersion = null, busy = false;
  const check = async () => {
    if (busy) return;
    busy = true;
    try {
      const response = await fetch('/local-data-version', { cache: 'no-store' });
      if (!response.ok) return;
      const { version } = await response.json();
      if (currentVersion && currentVersion !== version) {
        sessionStorage.setItem('keke-desktop-view', JSON.stringify({ route: userActiveRoute, character: selectedCharacter, tab: userActiveTab }));
        location.reload();
      }
      currentVersion = version;
    } catch { /* Keep the current display when local data is temporarily unavailable. */ }
    finally { busy = false; }
  };
  try {
    const view = JSON.parse(sessionStorage.getItem('keke-desktop-view') || 'null');
    sessionStorage.removeItem('keke-desktop-view');
    if (view) {
      if (characterData[view.character]) applyCharacter(view.character);
      userActiveTab = view.tab || 'overview';
      showUserRoute(view.route || 'team');
    }
  } catch { /* A malformed view state does not change user settings. */ }
  check();
  setInterval(check, 2500);
  window.addEventListener('focus', check);
});
document.addEventListener('keydown', event => {
  if (!event.ctrlKey || !/^[1-7]$/.test(event.key) || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
  event.preventDefault();
  showUserRoute(['team','characters','arc-drives','cassettes','drive-blocks','inventory','vision'][Number(event.key)-1]);
});
