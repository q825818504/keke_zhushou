// Real desktop HTTP consent gate with fixture data; native reads/deployment are intercepted.
const {chromium}=require('../desktop/node_modules/playwright');
const {spawn}=require('node:child_process');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');

function fixture(){
  const process=spawn(path.join(root,'.venv-ocr/Scripts/python.exe'),['scripts/check_inventory_browser_server.py'],{cwd:root,windowsHide:true});
  const ready=new Promise((resolve,reject)=>{
    let output='';
    process.stdout.on('data',chunk=>{output+=chunk;if(output.includes('\n'))try{resolve(JSON.parse(output.split('\n')[0]).port);}catch(error){reject(error);}});
    process.stderr.on('data',chunk=>global.process.stderr.write(chunk));
    process.once('exit',code=>reject(Error('Fixture exited '+code)));
  });
  return {process,ready};
}

(async()=>{
  let browser;const servers=[];
  try{
    browser=await chromium.launch({channel:'chrome',headless:true});
    const page=await browser.newPage({viewport:{width:1380,height:900}}),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    async function openServer(){
      const server=fixture();servers.push(server);const port=await server.ready;
      await page.goto('http://127.0.0.1:'+port);
      await page.locator('[data-user-route="vision"]').waitFor();
      if(await page.evaluate(async()=>(await(await fetch('/release/status')).json()).show)){
        await page.locator('#releaseNotesDialog').waitFor({state:'visible'});
        await page.locator('#releaseNotesDialog button').click();
      }
    }
    const risk=()=>page.evaluate(async()=>(await(await fetch('/inventory/status')).json()).native_risk);
    const post=(url,body={})=>page.evaluate(async({url,body})=>{
      const status=await(await fetch('/inventory/status')).json();
      const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-Keke-Inventory':status.token},body:JSON.stringify(body)});
      return {status:response.status,data:await response.json()};
    },{url,body});
    await openServer();
    assert.deepEqual(await risk(),{acknowledged:false,enabled:false});
    await page.locator('[data-user-route="role-build-plus"]').click();
    assert.equal(await page.locator('[data-go-read]').isDisabled(),true);
    await page.locator('[data-user-route="vision"]').click();
    const dialog=page.locator('#nativeRiskDialog');await dialog.waitFor({state:'visible'});
    assert.equal(await dialog.locator('button').count(),1);
    assert.match(await dialog.textContent(),/读取游戏数据.*风险/);
    await page.keyboard.press('Escape');assert.equal(await dialog.isVisible(),true);
    assert.equal((await post('/inventory/risk-mode',{enabled:true})).status,400);
    for(const url of ['/inventory/start','/inventory/components/deploy']){
      const result=await post(url);assert.equal(result.status,400);assert.match(result.data.error,/风险模式/);
    }
    await page.screenshot({path:path.join(root,'build/native-risk-dialog-qa.png')});
    await dialog.getByRole('button',{name:'我已了解'}).click();await dialog.waitFor({state:'detached'});
    assert.deepEqual(await risk(),{acknowledged:true,enabled:false});
    assert.equal(await page.locator('#nativeRiskMode').isChecked(),false);
    for(const selector of ['[data-native="start"]','[data-native="deploy"]'])assert.equal(await page.locator(selector).isDisabled(),true);
    assert.equal(await page.locator('[data-native="check"]').isDisabled(),false);
    assert.equal(await page.locator('[data-native="remove"]').isDisabled(),false);
    await page.locator('#visionMode').selectOption('offline');
    assert.equal(await page.locator('[data-vision="start"]').isEnabled(),true);
    await page.locator('#visionMode').selectOption('native');
    await page.locator('#nativeRiskMode').check();
    await page.waitForFunction(()=>!document.querySelector('[data-native="start"]').disabled);
    assert.deepEqual(await risk(),{acknowledged:true,enabled:true});
    let reads=0,deploys=0;
    await page.route('**/inventory/start',async route=>{
      reads++;const status=await(await page.request.get(new URL('/inventory/status',page.url()).href)).json();
      await route.fulfill({json:status});
    });
    await page.route('**/inventory/components/deploy',async route=>{deploys++;await route.fulfill({json:{message:'测试部署完成（未调用游戏组件）'}});});
    await page.locator('[data-native="deploy"]').click();await page.waitForFunction(()=>document.querySelector('#userVisionRoute').textContent.includes('测试部署完成'));
    assert.equal(deploys,1);
    await page.locator('[data-native="start"]').click();await page.waitForFunction(()=>!document.querySelector('[data-native="start"]').disabled);
    assert.equal(reads,1);
    await page.locator('[data-user-route="role-build-plus"]').click();
    await page.waitForFunction(()=>!document.querySelector('[data-go-read]').disabled);
    await page.locator('[data-go-read]').click();
    await page.waitForFunction(()=>document.querySelector('#userRoleBuildPlusRoute').textContent.includes('DLL 原生读取已启动'));
    assert.equal(reads,2);
    await page.evaluate(()=>window.dispatchEvent(new CustomEvent('keke-inventory-synced')));
    await page.locator('[data-user-route="vision"]').click();assert.equal(await dialog.count(),0);
    await page.locator('#nativeRiskMode').uncheck();
    await page.waitForFunction(()=>document.querySelector('[data-native="start"]').disabled);
    assert.deepEqual(await risk(),{acknowledged:true,enabled:false});
    await page.screenshot({path:path.join(root,'build/native-risk-off-qa.png')});
    const rejection=await page.evaluate(()=>window.KekeVision.startNativeRead().then(()=>null,error=>error.message));
    assert.match(rejection,/风险模式/);assert.equal(reads,2);
    await page.locator('[data-user-route="role-build-plus"]').click();
    assert.equal(await page.locator('[data-go-read]').isDisabled(),true);
    await page.unrouteAll({behavior:'wait'});
    await page.reload();await page.locator('[data-user-route="vision"]').click();
    await page.waitForFunction(()=>document.querySelector('[data-native="check"]')?.disabled===false);
    assert.equal(await dialog.count(),0,'same application run must not repeat the notice');
    await openServer();await page.locator('[data-user-route="vision"]').click();
    await dialog.waitFor({state:'visible'});
    assert.deepEqual(await risk(),{acknowledged:false,enabled:false});
    assert.deepEqual(errors,[]);
    console.log('Native risk gate passed: one-button notice, Escape blocked, default off, explicit opt-in, both read entries and deployment gated, HTTP bypass rejected, OCR available, application-session reset.');
  }finally{
    if(browser)await browser.close();
    for(const server of servers)server.process.kill();
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
