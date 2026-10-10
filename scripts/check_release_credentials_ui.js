// Exercise actual credential event handlers with a local API double; no real token or network.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
async function check(failed) {
  const nodes = new Map();
  function node(selector) {
    if (!nodes.has(selector)) nodes.set(selector, {
      dataset: {}, textContent: '', value: '', listeners: {}, disabled: false,
      addEventListener(event, action) { (this.listeners[event] ||= []).push(action); },
      async click() { await Promise.all((this.listeners.click || []).map(action => action({ target: this }))); },
      showModal() { this.open = true; }, close() { this.open = false; }
    });
    return nodes.get(selector);
  }
  let configured = false, resume;
  const savePending = new Promise(resolve => { resume = resolve; });
  const document = {
    querySelector: node,
    querySelectorAll: selector => selector.includes('button')
      ? [node('#releaseCredentialsButton'), node('#releaseConfigButton')] : []
  };
  const context = { document, Event, location: { protocol: 'http:', hostname: '127.0.0.1' },
    window: { dispatchEvent() {} }, fetch: async path => {
      let value = { ok: true }, ok = true;
      if (path === '/api/ping') value = { service: 'keke-admin', capabilities: ['character-save'] };
      if (path === '/api/status') value = { git: { available: true, remoteConfigured: true, changes: [] } };
      if (path === '/api/release/status') value = { configured, version: null, config_revision: 0 };
      if (path === '/api/release/credentials') {
        await savePending;
        ok = !failed; configured = !failed;
        value = failed ? { error: 'Gitee令牌无效，令牌未保存。' }
          : { ok: true, configured: true, message: '发布令牌已保存，Gitee仓库权限验证通过。尚未上传发行文件。' };
      }
      return { ok, status: ok ? 200 : 409, json: async () => value };
    }
  };
  vm.createContext(context); vm.runInContext(fs.readFileSync('admin_bridge.js', 'utf8'), context);
  await context.window.KekeAdminBridge.bindDialog();
  await node('#repoSyncButton').click();
  assert.match(node('#releasePublishStatus').textContent, /尚未保存/);
  node('#releaseToken').value = 'test-token-not-a-real-secret';
  node('#releaseCredentialsButton').textContent = '保存发布凭据';
  const saving = node('#releaseCredentialsButton').click();
  assert.equal(node('#releasePublishStatus').dataset.tone, 'working');
  assert.equal(node('#releaseCredentialsButton').disabled, true);
  resume(); await saving;
  assert.equal(node('#releaseCredentialsButton').disabled, false);
  assert.equal(node('#releaseCredentialsButton').textContent, '保存发布凭据');
  if (failed) {
    assert.equal(node('#releasePublishStatus').dataset.tone, 'error');
    assert.match(node('#releasePublishStatus').textContent, /令牌无效/);
    assert.ok(node('#releaseToken').value, 'Failure must keep the field available for retry');
  } else {
    assert.equal(node('#releasePublishStatus').dataset.tone, 'success');
    assert.match(node('#releasePublishStatus').textContent, /令牌已保存/);
    assert.equal(node('#releaseToken').value, '');
    await node('#repoSyncButton').click();
    assert.match(node('#releasePublishStatus').textContent, /令牌已保存/);
  }
}
(async () => { await check(false); await check(true); console.log('Credential UI: progress, immediate saved status, reopen and visible failure/retry passed.'); })()
  .catch(error => { console.error(error); process.exitCode = 1; });
