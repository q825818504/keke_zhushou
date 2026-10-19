/* Offline DLL/OCR role-build regression with synthetic inventory data. */
const { chromium } = require('../desktop/node_modules/playwright');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '..');
const python = path.join(root, '.venv-ocr', 'Scripts', 'python.exe');
const fixture = path.join(root, 'scripts', 'check_inventory_browser_server.py');
const standardSource = fs.readFileSync(path.join(root, 'role_build_standard.js'), 'utf8');
for (const forbidden of ['KekeVision', '/inventory/equipment/', 'NativeAssemblyPlanner', 'native_read', 'KekeNativeReader']) {
  assert(!standardSource.includes(forbidden), `Standard role build must not reference ${forbidden}`);
}

(async () => {
  const server = spawn(python, [fixture], { cwd: root, windowsHide: true });
  let browser;
  try {
    const port = await new Promise((resolve, reject) => {
      let output = '';
      server.stdout.on('data', data => {
        output += data.toString();
        if (output.includes('\n')) {
          try { resolve(JSON.parse(output.split('\n')[0]).port); } catch (error) { reject(error); }
        }
      });
      server.stderr.on('data', data => process.stderr.write(data));
      server.on('exit', code => reject(Error(`Fixture server exited ${code}`)));
    });

    browser = await chromium.launch({ channel: 'chrome', headless: true });
    const page = await browser.newPage({ viewport: { width: 1380, height: 900 } });
    const pageErrors = [];
    const inventoryRequests = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    page.on('request', request => {
      if (request.url().includes('/inventory/')) inventoryRequests.push(request.url());
    });
    await page.goto(`http://127.0.0.1:${port}`);
    if (await page.evaluate(async () => (await (await fetch('/release/status')).json()).show)) {
      const releaseDialog = page.locator('#releaseNotesDialog');
      await releaseDialog.waitFor({ state: 'visible' });
      await releaseDialog.locator('button').first().click();
      await releaseDialog.waitFor({ state: 'hidden' });
    }
    await page.locator('[data-user-route="role-build"]').click();
    await page.locator('[data-source-select]').waitFor();
    await page.locator('[data-account-select] option[value="OCR账号"]').waitFor({state:'attached'});

    const accountOptions = await page.locator('[data-account-select] option').allTextContents();
    assert(accountOptions.some(text => text.includes('未绑定 UID · 默认账号')), accountOptions);
    await page.locator('[data-account-select]').selectOption('OCR账号');
    await page.waitForFunction(() => document.querySelectorAll('[data-source-select] option').length === 2);

    const sources = await page.locator('[data-source-select] option').allTextContents();
    assert(sources.some(text => text.includes('2026-10-08T10:00:00+00:00')), sources);
    assert(sources.some(text => text.includes('2026-10-08T10:15:00+00:00')), sources);
    assert(!sources.some(text => text.toLowerCase().includes('native')), sources);
    await page.locator('[data-source-select]').selectOption(`ocr:${'2'.repeat(24)}`);
    await page.waitForFunction(() => document.querySelector('.rb-source')?.textContent.includes('10:15:00'));
    assert((await page.locator('.rb-header').innerText()).includes('UID 123456789012'));

    const roleIds = await page.locator('[data-cassette-score-role]').evaluateAll(nodes =>
      nodes.map(node => node.dataset.cassetteScoreRole));
    assert(roleIds.length >= 20, `Expected encyclopedia roster; found ${roleIds.length}`);
    assert(!roleIds.includes('tajiduo'));
    assert(!(await page.locator('.rb-roster').innerText()).includes('塔吉多'));
    await page.locator('[data-account-select]').selectOption('默认账号');
    await page.locator('[data-source-select] option[value="native"]').waitFor({state:'attached'});
    const nativeSources=await page.locator('[data-source-select] option').allTextContents();
    assert(nativeSources.some(text=>text.includes('DLL 离线快照')&&text.includes('2026-10-07T10:00:00+00:00')),nativeSources);
    const roleName=await page.locator('[data-cassette-score-role] b').first().textContent();
    const roleId=await page.locator('[data-cassette-score-role]').first().getAttribute('data-cassette-score-role');
    await page.route('**/inventory/snapshot?**source=native',async route=>{
      const response=await route.fetch();const data=await response.json();
      data.inventory.equipment={saved_at:'2026-10-07T10:00:00+00:00',coverage:{collection_complete:true},records:[
        {instance_id:'native-drive',category:'drive',shape:'EquipmentGeometry_hen2',rarity:'Orange',
         equipped_character_id:'777',sub_attributes:[{name:'攻击力',value:.0375,is_percent:true}]},
        {instance_id:'native-tape',category:'tape',name:'森林萤火之心',rarity:'Orange',main_attributes:[{name:'攻击力',value:.1,is_percent:true}]}
      ]};data.inventory.characters={records:[{character_id:'777',name:roleName}]};
      await route.fulfill({response,json:data});
    });
    await page.locator('[data-source-select]').selectOption('native');
    await page.waitForFunction(()=>document.querySelector('.rb-source')?.textContent.includes('2 件装备'));
    await page.evaluate(()=>{window.Worker=class {postMessage(data){window.__offlineSnapshot=data.snapshot;window.__offlineWorker=this;}terminate(){}};});
    await page.locator('[data-build-calculate]').click();
    const offline=await page.evaluate(()=>window.__offlineSnapshot);
    assert.equal(offline.source_id,'native');
    assert.equal(offline.items.find(item=>item.id==='native-drive').owner,roleId);
    assert.equal(offline.items.find(item=>item.id==='native-drive').rarity,'Orange');
    assert.equal(offline.items.find(item=>item.id==='native-tape').main_stats[0].value,.1);
    assert.equal(offline.items.find(item=>item.id==='native-tape').main_stats[0].is_percent,true);
    let ocrDamage=20;
    await page.route('**/inventory/snapshot?**source=ocr*',async route=>{
      const response=await route.fetch();const data=await response.json();
      data.inventory.equipment={saved_at:'2026-10-08T10:00:00+00:00',coverage:{collection_complete:true},records:[
        {instance_id:'ocr-tape',category:'tape',name:'森林萤火之心',rarity_candidate:'gold',
         main_attributes:{'攻击力%':37.5},sub_attributes:{'暴击伤害%':ocrDamage,'暴击率%':10,'生命值':1000}}]};
      await route.fulfill({response,json:data});
    });
    await page.locator('[data-source-select]').selectOption(`ocr:${'1'.repeat(24)}`);
    await page.waitForFunction(()=>document.querySelector('.rb-source')?.textContent.includes('1 件装备'));
    await page.locator('[data-build-calculate]').click();
    const ocr=await page.evaluate(()=>window.__offlineSnapshot.items[0]);
    assert.equal(ocr.main_stats[0].value,.375);
    assert.equal(ocr.sub_stats.find(row=>row.name==='暴击伤害%').value,.2);
    assert.equal(ocr.sub_stats.find(row=>row.name==='暴击率%').value,.1);
    assert.equal(ocr.sub_stats.find(row=>row.name==='生命值').value,1000);
    await page.evaluate(()=>window.__offlineWorker.onmessage({data:{result:{core:'ocr-tape',modules:[],complete:false}}}));
    const chips=await page.locator('.rb-gear-row .rb-stat-chip').allTextContents();
    assert(chips.some(text=>text.includes('暴击伤害')&&text.includes('20%')),chips);
    assert(!chips.some(text=>text.includes('2,000%')),chips);
    await page.locator('[data-build-save]').click();
    ocrDamage=60;
    await page.locator('[data-role-refresh]').click();
    await page.locator('[data-role-refresh]').waitFor({state:'visible'});
    await page.waitForFunction(()=>!document.querySelector('[data-role-refresh]').disabled);
    const requestsBeforeGame=inventoryRequests.length;
    await page.locator('[data-role-build-tab="game"]').click();
    assert.equal(await page.locator('[data-account-select],[data-source-select],[data-go-read]').count(),0);
    assert((await page.locator('.rb-gear-row .rb-sub-stats').innerText()).includes('20%'),'game view must show saved equipment, not changed live inventory');
    await page.locator('[data-role-refresh]').click();
    assert.equal(inventoryRequests.length,requestsBeforeGame,'game view refresh must read saved plans only');
    const standardRequests = inventoryRequests.slice();
    assert(standardRequests.length >= 3, standardRequests);
    assert(!standardRequests.some(url => url.includes('/inventory/equipment/')), standardRequests);
    assert(standardRequests.every(url => url.includes('/inventory/status') || url.includes('/inventory/snapshot?')),
      standardRequests);

    await page.locator('[data-user-route="role-build-plus"]').click();
    await page.locator('#userRoleBuildPlusRoute').waitFor({ state: 'visible' });
    assert.deepEqual(pageErrors, []);
    console.log(`Offline DLL/OCR role-build passed: optional UID, timestamp selection, native attributes/owner projection, ${roleIds.length} roles, no DLL read/equipment API, PLUS retained.`);
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
