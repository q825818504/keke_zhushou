const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
async function check(modern) {
  const requests = [];
  const context = {location:{protocol:'http:',hostname:'127.0.0.1'},window:{dispatchEvent:()=>{}},Event,
    fetch:async(path)=>{requests.push(path);return {ok:true,json:async()=>path==='/api/ping'
      ? {service:'keke-admin',version:modern?2:1,capabilities:modern?['character-save']:[]}: {ok:true}};}};
  vm.createContext(context);vm.runInContext(fs.readFileSync('admin_bridge.js','utf8'),context);
  if(modern){await context.window.KekeAdminBridge.saveCharacter('nanali',{},{});assert(requests.includes('/api/characters/save'));}
  else {await assert.rejects(context.window.KekeAdminBridge.saveCharacter('nanali',{},{}),/版本过旧/);assert(!requests.includes('/api/characters/save'));}
}
(async()=>{await check(false);await check(true);console.log('Admin protocol passed: legacy blocked before save, modern endpoint accepted.');})().catch(error=>{console.error(error);process.exitCode=1;});
