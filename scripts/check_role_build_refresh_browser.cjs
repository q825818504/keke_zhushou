const {chromium}=require('../desktop/node_modules/playwright');
const {spawn}=require('node:child_process');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');

(async()=>{
 const server=spawn(path.join(root,'.venv-ocr/Scripts/python.exe'),[path.join(root,'scripts/check_role_build_refresh_browser_server.py')],{cwd:root,windowsHide:true});
 let browser;
 try{
  const port=await new Promise((resolve,reject)=>{
   let output='';
   server.stdout.on('data',part=>{output+=part.toString();if(output.includes('\n'))try{resolve(JSON.parse(output.split('\n')[0]).port)}catch(error){reject(error)}});
   server.stderr.on('data',part=>process.stderr.write(part));
   server.on('exit',code=>reject(Error('Fixture exited '+code)));
  });
  browser=await chromium.launch({channel:'chrome',headless:true});
  const page=await browser.newPage({viewport:{width:1380,height:1000}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>{
   window.__equipmentInspectPosts=0;
   window.__fullNativeReads=0;
   const original=window.fetch.bind(window);
   window.fetch=(input,init)=>{
    const url=typeof input==='string'?input:input.url;
    if(url.includes('/inventory/equipment/inspect')&&init?.method==='POST')window.__equipmentInspectPosts++;
    if(url.includes('/inventory/start')&&init?.method==='POST')window.__fullNativeReads++;
    return original(input,init);
   };
  });
  await page.goto('http://127.0.0.1:'+port);
  await page.locator('[data-user-route="role-build-plus"]').click();
  const panel=page.locator('#userRoleBuildPlusRoute');
  await panel.locator('[data-role-build-tab="game"]').waitFor();
  await panel.locator('[data-role-build-tab="game"]').click();
  await panel.locator('[data-cassette-score-role="1003"]').waitFor();
  await panel.locator('[data-cassette-score-role="1003"]').click();
  await panel.locator('[data-build-equip]').waitFor();
  await panel.locator('[data-build-equip]').click();
  await panel.locator('[data-build-execute]').waitFor();
  await panel.locator('[data-build-execute]').click();
  await page.waitForFunction(()=>document.querySelector('#userRoleBuildPlusRoute .rb-operation-status')?.textContent.includes('装配完成'),null,{timeout:20000});
  await panel.locator('[data-role-build-tab="calculate"]').click();
  await page.waitForFunction(()=>{
   const text=document.querySelector('#userRoleBuildPlusRoute .rb-current-gear')?.textContent||'';
   return text.includes('测试装备 3')&&text.includes('测试装备 4')&&text.includes('测试装备 9')&&text.includes('当前驱动 6 块');
  },null,{timeout:10000});
  const final=await page.evaluate(async()=>({status:await(await fetch('/inventory/status')).json(),inspectPosts:window.__equipmentInspectPosts,fullReads:window.__fullNativeReads}));
  assert.equal(final.status.fixture_locked_completion_seen,true,'fixture did not expose the completed-but-locked window');
  assert.equal(final.status.native_operation,null);
  assert.equal(final.status.equipment_job.state,'verified');
  assert.ok(final.inspectPosts>=2,'expected initial inspect and post-equip refresh');
  assert.equal(final.fullReads,0,'post-equip sync must not launch a full five-domain native read');
  assert.deepEqual(errors,[]);
  console.log('Role-build refresh browser passed: saved scheme auto-equip, locked completion wait, fresh current gear after returning to calculation, no full inventory scan.');
 }finally{
  if(browser)await browser.close();
  server.kill();
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
