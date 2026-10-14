const {chromium}=require('../desktop/node_modules/playwright');
const {spawn}=require('node:child_process');const path=require('node:path');const fs=require('node:fs');const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');const profile=path.join(root,'build/v1-3-ui-profile');fs.mkdirSync(profile,{recursive:true});
fs.rmSync(path.join(profile,'KekeAssistant/release-seen.json'),{force:true});
(async()=>{
 const server=spawn(path.join(root,'.venv-ocr/Scripts/python.exe'),['scripts/check_vision_browser_server.py'],{cwd:root,windowsHide:true,env:{...process.env,LOCALAPPDATA:profile}});let browser;
 try{
  const port=await new Promise((resolve,reject)=>{let text='';server.stdout.on('data',p=>{text+=p;if(text.includes('\n'))resolve(JSON.parse(text.split('\n')[0]).port)});server.stderr.on('data',p=>process.stderr.write(p));server.on('exit',c=>reject(Error('fixture exited '+c)))});
  browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1366,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+port);await page.locator('#releaseNotesDialog').waitFor({state:'visible'});
  assert((await page.locator('#releaseNotesDialog').textContent()).includes('v1.3'));
  await page.screenshot({path:path.join(root,'build/v1-3-update-notes.png')});
  await page.getByRole('button',{name:'开始使用',exact:true}).click();await page.locator('#releaseNotesDialog').waitFor({state:'hidden'});console.log('notes acknowledged');
  await page.reload();await page.locator('.desktop-sidebar nav svg').first().waitFor();await page.waitForTimeout(500);assert.equal(await page.locator('#releaseNotesDialog[open]').count(),0);
  assert.equal(await page.locator('.desktop-sidebar nav svg').count(),7);
  assert(await page.locator('.desktop-app-mark').evaluate(img=>img.complete && img.naturalWidth>0));
  await page.locator('[data-user-team-roster-action=all]').click();
  await page.locator('[data-user-team-generate]').click();
  await page.waitForFunction(()=>document.querySelector('#userTeamRoute').textContent.includes('维护阵容'));
  const plans=await page.evaluate(()=>userTeamRecommendPlans().map(p=>({id:p.id,kind:p.candidateKind,source:!!p.sourceRecord})));
  assert(plans.length>0 && plans.every(p=>p.kind==='source' && p.source && !p.id.startsWith('rule-')));
  assert(!(await page.locator('#userTeamRoute').textContent()).includes('套适配阵容'));
  assert(!(await page.locator('#userTeamRoute').textContent()).includes('本地规则候选'));
  await page.screenshot({path:path.join(root,'build/v1-3-maintained-teams.png')});
  await page.evaluate(()=>{userTeamOwnedNames=new Set([Object.keys(characterData)[0]]);userTeamGenerated=true;renderUserTeamRoute();});
  assert((await page.locator('#userTeamRoute').textContent()).includes('没有匹配到完整的维护阵容'));
  const defects=[];
  for(const width of [1366,900]){
   await page.setViewportSize({width,height:900});
   for(const route of ['team','characters','arc-drives','cassettes','drive-blocks','inventory','vision']){
    await page.locator('[data-user-route="'+route+'"]').click();await page.waitForTimeout(120);
    if(await page.evaluate(()=>document.querySelector('.main-content').scrollWidth>document.querySelector('.main-content').clientWidth+2))defects.push(width+':'+route+': horizontal overflow');
    if(['team','inventory','vision'].includes(route))await page.screenshot({path:path.join(root,`build/v1-3-${route}-${width}.png`)});
   }
  }
  await page.locator('#releaseNotesButton').click();await page.locator('#releaseNotesDialog').waitFor({state:'visible'});
  await page.keyboard.press('Escape');await page.locator('#releaseNotesDialog').waitFor({state:'hidden'});
  assert.deepEqual(errors,[]);assert.deepEqual(defects,[]);console.log('v1.3 browser passed: auto notes, persisted acknowledgement, manual reopen, Escape, mint, 7 SVG icons, 14 route/size checks.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1});
