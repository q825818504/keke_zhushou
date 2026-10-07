window.__desktopErrors = window.__desktopErrors || [];
window.addEventListener('error', event => window.__desktopErrors.push(event.message));
window.addEventListener('unhandledrejection', event => window.__desktopErrors.push(String(event.reason)));
window.addEventListener('DOMContentLoaded', () => {
  document.body.classList.add('desktop-mode');
  const admin = new URLSearchParams(location.search).get('desktop') === 'admin';
  if (admin) {
    let editorDirty = false;
    const publishDirty = () => {
      window.pywebview?.api?.set_dirty(editorDirty || (typeof guideDirty !== 'undefined' && guideDirty));
    };
    document.querySelector('#editorCard').addEventListener('input', () => { editorDirty = true; publishDirty(); });
    window.addEventListener('keke-role-dirty', () => { editorDirty = true; publishDirty(); });
    window.addEventListener('keke-role-saved', () => { editorDirty = false; publishDirty(); });
    document.addEventListener('click', () => setTimeout(publishDirty, 0));
    document.addEventListener('dragend', () => setTimeout(publishDirty, 0));
    window.desktopCanClose = () => {
      if (typeof guideDirty !== 'undefined' && guideDirty && !guideCanLeave()) return false;
      return !editorDirty || window.confirm('角色编辑有未保存的修改，仍要关闭吗？');
    };
    document.querySelector('.brand-lockup small').textContent = '资料管理';
    document.querySelector('[data-nav="工作台"]')?.remove();
    const roleCount = document.querySelector('[data-nav="角色管理"] em');
    if (roleCount) roleCount.textContent = Object.keys(characterData).length;
    const bottom = document.querySelector('.sidebar-bottom');
    bottom.innerHTML = '<button class="desktop-tool" id="desktopPreview">用户端预览</button><button class="desktop-tool" id="desktopWorkspace">切换项目资料库…</button><small class="desktop-workspace-path" id="desktopWorkspacePath"></small>';
    document.querySelector('#desktopPreview').addEventListener('click', () => showUserExperience());
    document.querySelector('#desktopWorkspace').addEventListener('click', async () => {
      if (!window.desktopCanClose()) return;
      try { await window.pywebview.api.choose_workspace(); }
      catch (error) { notify(error.message || '无法打开所选项目资料库'); }
    });
    document.querySelector('.sidebar .brand-lockup strong').textContent = '可可助手';
    showRoleManagement();
    const showWorkspace = async () => {
      if (window.pywebview?.api) {
        document.querySelector('#desktopWorkspacePath').textContent = await window.pywebview.api.workspace();
      }
    };
    window.addEventListener('pywebviewready', showWorkspace);
    showWorkspace();
  }
  document.addEventListener('keydown', event => {
    if (!event.ctrlKey || !/^[1-5]$/.test(event.key) || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
    event.preventDefault();
    if (admin) showUserExperience();
    showUserRoute(['team','characters','arc-drives','cassettes','drive-blocks'][Number(event.key)-1]);
  });
  document.querySelector('.main-content').addEventListener('scroll', () => {
    document.body.classList.toggle('desktop-scrolled', document.querySelector('.main-content').scrollTop > 8);
  }, { passive: true });
});
