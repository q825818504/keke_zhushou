// Exercises only temporary account data served by the desktop runtime fixture.
const {chromium}=require('../desktop/node_modules/playwright');
const {spawn}=require('node:child_process');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
  const server=spawn(path.join(root,'.venv-ocr/Scripts/python.exe'),['scripts/check_inventory_browser_server.py'],{cwd:root,windowsHide:true});
  let browser;
  try{
    const port=await new Promise((resolve,reject)=>{
      let output='';server.stdout.on('data',part=>{output+=part;if(output.includes('\n'))try{resolve(JSON.parse(output.split('\n')[0]).port);}catch(error){reject(error);}});
      server.stderr.on('data',part=>process.stderr.write(part));server.once('exit',code=>reject(Error('Fixture exited '+code)));
    });
    browser=await chromium.launch({channel:'chrome',headless:true});
    const page=await browser.newPage({viewport:{width:1380,height:900}}),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto('http://127.0.0.1:'+port);
    if(await page.evaluate(async()=>(await(await fetch('/release/status')).json()).show)){
      await page.locator('#releaseNotesDialog').waitFor({state:'visible'});await page.locator('#releaseNotesDialog button').click();
    }
    const nav=page.locator('.desktop-sidebar [data-user-route="role-build-plus"]');
    assert.equal(await nav.locator('.role-build-plus').textContent(),'PLUS');
    assert.match(await nav.getAttribute('aria-label'),/角色配装/);
    await page.locator('[data-user-route="inventory"]').click();
    await page.locator('#inventoryAccountSelect option[value="OCR账号"]').waitFor({state:'attached'});
    await page.locator('#inventoryAccountSelect').selectOption('OCR账号');
    await page.locator('[data-account-action="delete-account"]').waitFor();
    await page.waitForFunction(()=>document.querySelector('#inventoryAccountUID').value==='123456789012');
    const select=await page.locator('#inventorySource').boundingBox(),button=await page.locator('[data-inventory="delete"]').boundingBox();
    assert.ok(Math.abs(select.y+select.height-button.y-button.height)<=1,'data selector and delete button must align');
    await page.screenshot({path:path.join(root,'build/inventory-account-controls-qa.png'),fullPage:true});
    page.once('dialog',dialog=>dialog.dismiss());
    await page.locator('[data-account-action="delete-account"]').click();
    assert.equal(await page.locator('#inventoryAccountUID').inputValue(),'123456789012');
    page.once('dialog',dialog=>{assert.match(dialog.message(),/123456789012/);assert.match(dialog.message(),/全部截图/);dialog.accept();});
    await page.locator('[data-account-action="delete-account"]').click();
    await page.waitForFunction(()=>!document.querySelector('#inventoryAccountSelect option[value="OCR账号"]'));
    let state=await page.evaluate(async()=>({status:await(await fetch('/inventory/status')).json(),history:await(await fetch('/vision/history?account=OCR%E8%B4%A6%E5%8F%B7')).json()}));
    assert.equal(state.history.length,0);
    assert.equal(state.status.account_profiles.some(row=>row.uid==='123456789012'),false);
    assert.equal(state.status.account_profiles.some(row=>row.uid==='987654321098'),true);
    await page.reload();await page.locator('[data-user-route="inventory"]').click();
    await page.locator('#inventoryAccountSelect option[value="uid:987654321098"]').waitFor({state:'attached'});
    assert.equal(await page.locator('#inventoryAccountSelect option[value="OCR账号"]').count(),0);
    await page.setViewportSize({width:960,height:680});
    await page.screenshot({path:path.join(root,'build/inventory-account-controls-narrow-qa.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('Account deletion UI passed: correct UID confirmation, cancellation, source alignment, PLUS badge and accessible nav label, complete OCR cleanup, other UID preserved, reload remains deleted.');
  }finally{if(browser)await browser.close();server.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
