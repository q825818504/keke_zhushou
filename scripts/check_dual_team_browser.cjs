const {chromium}=require('../desktop/node_modules/playwright');
const {spawn}=require('node:child_process');const path=require('node:path');const fs=require('node:fs');const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),profile=path.join(root,'build/v1-4-dual-profile');fs.mkdirSync(profile,{recursive:true});
fs.rmSync(path.join(profile,'KekeAssistant/release-seen.json'),{force:true});
(async()=>{
 const server=spawn(path.join(root,'.venv-ocr/Scripts/python.exe'),['scripts/check_vision_browser_server.py'],{cwd:root,windowsHide:true,env:{...process.env,LOCALAPPDATA:profile}});let browser;
 try{
  const port=await new Promise((resolve,reject)=>{let text='';server.stdout.on('data',p=>{text+=p;if(text.includes('\n'))resolve(JSON.parse(text.split('\n')[0]).port)});server.stderr.on('data',p=>process.stderr.write(p));server.on('exit',c=>reject(Error('fixture exited '+c)))});
  browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1366,height:950}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+port);await page.locator('#releaseNotesDialog').waitFor({state:'visible'});await page.getByRole('button',{name:'开始使用',exact:true}).click();
  await page.locator('[data-user-team-roster-action=all]').click();
  await page.locator('[data-user-team-pin="残虹"]').click();await page.locator('[data-user-team-pin="安魂曲"]').click();
  await page.locator('[data-user-team-count="2"]').click();await page.locator('[data-user-team-roster="阿德勒"]').click();await page.locator('[data-user-team-generate]').click();
  assert((await page.locator('#userTeamRoute').textContent()).includes('双队无解：所有双队组合都存在角色冲突'));
  assert.equal(await page.locator('.user-team-grid .user-team-member').count(),0);
  assert.equal(await page.locator('[data-user-team-pair]').count(),0);
  await page.locator('.user-team-result').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(root,'build/v1-4-no-solution.png')});
  await page.locator('[data-user-team-roster="阿德勒"]').click();await page.locator('[data-user-team-generate]').click();
  assert.equal(await page.locator('[data-user-team-pair]').count(),3);assert.equal(await page.locator('[data-user-team-candidate]').count(),0);
  const validate=async()=>{
   const names=await page.locator('.user-team-grid .user-team-member-copy b').allTextContents();assert.equal(names.length,8);assert.equal(new Set(names).size,8);
   const headings=await page.locator('.user-team-result h2').allTextContents();assert(headings.includes('残虹 的方案'));assert(headings.includes('安魂曲 的方案'));
   return names;
  };
  const original=await validate();
  await page.locator('[data-user-team-pair="1"]').click();const switched=await validate();assert.notDeepEqual(switched,original);
  assert.deepEqual(switched.slice(4).sort(),['安魂曲','白藏','黑羽','阿德勒'].sort());
  assert.equal(await page.locator('[data-user-team-pair="1"]').getAttribute('aria-pressed'),'true');assert(await page.locator('[data-user-team-pair="1"]').evaluate(el=>el===document.activeElement));
  await page.keyboard.press('Tab');await page.keyboard.press('Enter');await validate();
  const defects=[];
  for(const width of [1366,900]){
   await page.setViewportSize({width,height:950});await page.locator('.user-team-result').first().scrollIntoViewIfNeeded();
   if(await page.evaluate(()=>document.querySelector('.main-content').scrollWidth>document.querySelector('.main-content').clientWidth+2))defects.push(width+':overflow');
   await page.screenshot({path:path.join(root,`build/v1-4-combinations-${width}.png`)});
  }
  await page.locator('[data-user-team-count="1"]').click();await page.locator('[data-user-team-generate]').click();
  assert.equal(await page.locator('.user-team-grid .user-team-member').count(),4);assert.equal(await page.locator('[data-user-team-pair]').count(),0);assert((await page.locator('[data-user-team-candidate]').count())>0);
  await page.locator('[data-user-team-count="2"]').click();await page.locator('[data-user-team-pin="残虹"]').click();await page.locator('[data-user-team-pin="安魂曲"]').click();await page.locator('[data-user-team-generate]').click();
  let names=await page.locator('.user-team-grid .user-team-member-copy b').allTextContents();assert.equal(new Set(names).size,8);
  // Empty maintained catalog: show an honest failure and no partial successful team.
  await page.evaluate(()=>{window.teamGuideStore={all:()=>[]};renderUserTeamRoute();});
  assert((await page.locator('#userTeamRoute').textContent()).includes('没有第一队候选'));assert.equal(await page.locator('.user-team-grid .user-team-member').count(),0);
  await page.evaluate(()=>{const core=characterData['残虹'].id;window.teamGuideStore={all:()=>teamTemplateKnowledge.teams.filter(t=>t.source_core_character_id===core)};userTeamPinnedCoreNames=['残虹','安魂曲'];renderUserTeamRoute();});
  assert((await page.locator('#userTeamRoute').textContent()).includes('没有第二队候选'));assert.equal(await page.locator('.user-team-grid .user-team-member').count(),0);
  await page.evaluate(()=>{window.teamGuideStore={all:()=>[]};userTeamPinnedCoreNames=['阿德勒','安魂曲'];renderUserTeamRoute();});
  assert((await page.locator('.user-team-pin-slots').textContent()).includes('阿德勒'));
  assert.equal(await page.locator('[data-user-team-pin="阿德勒"]').getAttribute('aria-pressed'),'true');
  assert((await page.locator('#userTeamRoute').textContent()).includes('没有第一队候选'));
  assert.deepEqual(errors,[]);assert.deepEqual(defects,[]);
  console.log('v1.4 browser passed: actual missing-Adler conflict, valid eight-character pairs, joint switching and keyboard focus, two desktop widths, single team unchanged, no-lock pairing, first/second failure states, no browser errors.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1});
