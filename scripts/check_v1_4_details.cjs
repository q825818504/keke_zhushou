const {chromium}=require('../desktop/node_modules/playwright');const {spawn}=require('node:child_process');const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),profile=path.join(root,'build/v1-4-detail-profile');fs.mkdirSync(profile,{recursive:true});fs.rmSync(path.join(profile,'KekeAssistant/release-seen.json'),{force:true});
(async()=>{let browser;const server=spawn(path.join(root,'.venv-ocr/Scripts/python.exe'),['scripts/check_vision_browser_server.py'],{cwd:root,windowsHide:true,env:{...process.env,LOCALAPPDATA:profile}});
try{
const port=await new Promise((resolve,reject)=>{let out='';server.stdout.on('data',data=>{out+=data;if(out.includes('\n'))resolve(JSON.parse(out.split('\n')[0]).port)});server.on('exit',code=>reject(Error('server exit '+code)))});
browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1366,height:950}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:'+port);await page.getByRole('button',{name:'开始使用',exact:true}).click();
const stable=async(selector,action)=>{const el=page.locator(selector);await el.scrollIntoViewIfNeeded();const before=await page.locator('.user-team-roster-grid').evaluate(e=>e.scrollTop);assert(before>0,'exercise scrolled roster');await action(el);await page.waitForTimeout(70);const after=await page.locator('.user-team-roster-grid').evaluate(e=>e.scrollTop);assert(Math.abs(before-after)<=1,selector+': '+before+' -> '+after);};
await stable('[data-user-team-roster="哈尼娅"]',el=>el.click());await stable('[data-user-team-roster="薄荷"]',el=>el.click());
await stable('[data-user-team-investment-toggle="哈尼娅"]',el=>el.click());await stable('[data-user-team-resonance="哈尼娅"]',el=>el.selectOption('2'));await stable('[data-user-team-signature="哈尼娅"]',el=>el.click());
await stable('[data-user-team-pin="薄荷"]',el=>el.click());
await page.screenshot({path:path.join(root,'build/v1-4-roster-scroll-kept.png')});
await page.locator('[data-user-route="characters"]').click();await page.locator('[data-user-tab="constellation"]').click();
const expected=await page.evaluate(()=>({awake:activeKnowledge.awakenings,res:activeKnowledge.resonance}));
assert.equal(await page.locator('.user-constellation-section').count(),2);assert.equal(await page.locator('.user-constellation-list li').count(),expected.awake.length+expected.res.length);
for(const n of [...expected.awake,...expected.res])if(n.description)assert((await page.locator('#userTabPanel').textContent()).includes(n.description));
await page.evaluate(()=>applyCharacter('达芙蒂尔',{silent:true}));assert((await page.locator('#userTabPanel').textContent()).includes('觉醒与共鸣'));
for(const width of [1366,900]){await page.setViewportSize({width,height:950});await page.locator('#userTabNav').scrollIntoViewIfNeeded();assert.equal(await page.evaluate(()=>document.querySelector('.main-content').scrollWidth>document.querySelector('.main-content').clientWidth+2),false);await page.screenshot({path:path.join(root,`build/v1-4-constellation-${width}.png`)});}
await page.evaluate(()=>{const k={...activeKnowledge,awakenings:[],resonance:[]};renderUserTabPanel(k)});assert((await page.locator('#userTabPanel').textContent()).includes('暂无觉醒资料'));assert((await page.locator('#userTabPanel').textContent()).includes('暂无共鸣资料'));
await page.evaluate(()=>renderUserTabPanel({...activeKnowledge,awakenings:[{name:'<img src=x onerror=alert(1)>',description:'<script>bad()</script>\n完整效果'}],resonance:[]}));assert.equal(await page.locator('#userTabPanel script,#userTabPanel img').count(),0);assert((await page.locator('#userTabPanel').textContent()).includes('<script>bad()</script>'));
assert.deepEqual(errors,[]);console.log('Roster scroll maintained for selection, pin, expansion, resonance and signature; constellation nodes match full source, follow character, handle empty and escaped content; 2 desktop sizes passed.');
}finally{if(browser)await browser.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1});
