self.window=self;
importScripts('cassette_scoring.js','drive_layout_solver.js','loadout_optimizer.js');
self.onmessage=event=>{
  try{self.postMessage({result:KekeLoadoutOptimizer.optimize(event.data,KekeCassetteScoring)});}
  catch(error){self.postMessage({error:error.message||'计算失败'});}
};
