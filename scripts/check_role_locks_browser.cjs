/* Account-scoped persistent PLUS role protection; synthetic UI, no game input. */
const {chromium}=require('../desktop/node_modules/playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
  const server=spawn(path.join(root,'.venv-ocr/Scripts/python.exe'),['scripts/check_inventory_browser_server.py'],{cwd:root,windowsHide:true});
  let browser;
  try{
    const port=await new Promise((resolve,reject)=>{let text='';server.stdout.on('data',part=>{text+=part;if(text.includes('\n'))try{resolve(JSON.parse(text.split('\n')[0]).port)}catch(error){reject(error)}});server.stderr.on('data',part=>process.stderr.write(part));server.on('exit',code=>reject(Error('fixture '+code)));});
    browser=await chromium.launch({channel:'chrome',headless:true});
    const page=await browser.newPage({viewport:{width:1380,height:1000}}),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto('http://127.0.0.1:'+port);
    if(await page.evaluate(async()=>(await(await fetch('/release/status')).json()).show))await page.locator('#releaseNotesDialog button').first().click();
    await page.locator('[data-user-route="role-build-plus"]').click();
    const info=await page.evaluate(()=>({ready:true,account:'lock-fixture-A',account_uid:'123456789012',items:[],characters:
      Object.entries(characterData).filter(([,d])=>d.knowledge?.recommended?.cassette).slice(0,2).map(([name,d],i)=>({character_id:String(1001+i),name,
        board:d.knowledge.terminal.layout.active_slots.map(slot=>[slot.row,slot.column])}))}));
    await page.evaluate(value=>{window.KekeRoleBuild.setSnapshot(value);window.Worker=class{postMessage(data){window.__protectedOwners=data.protectedOwners;}terminate(){}};},info);
    const panel=page.locator('#userRoleBuildPlusRoute');
    await panel.locator('[data-cassette-score-role="1001"]').click();
    assert.equal(await panel.locator('[data-role-lock]').getAttribute('aria-pressed'),'false');
    assert.equal(await panel.locator('.rb-role-lock-badge').count(),0);
    assert.equal(await panel.locator('[data-role-build-standard]').count(),0);
    await panel.locator('[data-role-lock]').click();
    assert.equal(await panel.locator('[data-role-lock]').getAttribute('aria-pressed'),'true');
    assert.equal(await panel.locator('[data-cassette-score-role="1001"] .rb-role-lock-badge').count(),1);
    assert.equal(await panel.locator('.rb-role-lock-badge').evaluate(node=>getComputedStyle(node).pointerEvents),'none');
    assert(await panel.locator('[data-role-lock]').evaluate(node=>node.classList.contains('is-locked')&&getComputedStyle(node).color==='rgb(255, 92, 101)'));
    await panel.locator('[data-cassette-score-role="1002"]').click();
    await panel.locator('[data-build-exclude]').uncheck();
    await panel.locator('[data-build-calculate]').click();
    assert.deepEqual(await page.evaluate(()=>window.__protectedOwners),['1001']);
    await panel.locator('[data-build-stop]').click();
    await page.evaluate(value=>window.KekeRoleBuild.setSnapshot({...value,account:'lock-fixture-B',account_uid:'987654321098'}),info);
    await panel.locator('[data-cassette-score-role="1001"]').click();
    assert.equal(await panel.locator('[data-role-lock]').getAttribute('aria-pressed'),'false','different account must not inherit locks');
    await panel.locator('[data-role-lock]').click();
    await page.reload();await page.locator('[data-user-route="role-build-plus"]').click();
    await page.evaluate(value=>window.KekeRoleBuild.setSnapshot(value),info);
    await panel.locator('[data-cassette-score-role="1001"]').click();
    assert.equal(await panel.locator('[data-role-lock]').getAttribute('aria-pressed'),'true','lock must survive reload');
    await panel.locator('[data-cassette-score-role="1002"]').click();
    await panel.locator('[data-role-lock]').click();
    assert.equal(await panel.locator('.rb-role-lock-badge').count(),2);
    await panel.locator('[data-role-unlock-all]').click();
    assert.equal(await panel.locator('[data-role-lock]').getAttribute('aria-pressed'),'false');
    assert.equal(await panel.locator('.rb-role-lock-badge').count(),0);
    assert(await panel.locator('[data-role-unlock-all]').isDisabled());
    await page.evaluate(value=>window.KekeRoleBuild.setSnapshot({...value,account:'lock-fixture-B',account_uid:'987654321098'}),info);
    await panel.locator('[data-cassette-score-role="1001"]').click();
    assert.equal(await panel.locator('[data-role-lock]').getAttribute('aria-pressed'),'true','bulk unlock must preserve other UID locks');
    assert.deepEqual(errors,[]);
    console.log('PLUS role locks passed: gray/red state, persistence, account isolation, protected owners forwarded with transfers allowed, unlock.');
  }finally{if(browser)await browser.close();server.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
