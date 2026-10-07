/* Terminal reference layouts: fixed catalog orientations, independent numbered pieces. */
window.TerminalPuzzle = (() => {
  const engine=window.DriveLayoutSolver;
  if(!engine) throw new Error("DriveLayoutSolver must load before TerminalPuzzle");
  const {definitions,byId,board,pieceCells,validate,solve,preference,terminalOf}=engine;
  const roman = {2:'Ⅱ',3:'Ⅲ',4:'Ⅳ'};
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function cassetteOf(knowledge) {
    const id=knowledge?.recommended?.cassette?.id;
    return (window.skyCurtainKnowledge?.items || []).find(item=>item.id===id);
  }
  function requirements(knowledge) { return cassetteOf(knowledge)?.set_requirements?.required_drives || null; }
  function setStatus(knowledge,plan) {
    const required=requirements(knowledge),cassette=cassetteOf(knowledge);
    if(!required) return {known:false,complete:false,matched:0,total:4,missing:[],text:'套装形状资料待补齐'};
    const counts=new Map();
    (plan?.pieces || []).forEach(p=>counts.set(p.shape_id,(counts.get(p.shape_id)||0)+1));
    const missing=required.flatMap(r=>Array.from({length:Math.max(0,r.count-(counts.get(r.shape_id)||0))},()=>r.shape_id));
    const total=required.reduce((n,r)=>n+r.count,0),matched=total-missing.length;
    return {known:true,complete:matched===total,matched,total,missing,text:`${cassette.name} · ${matched}/${total} 种套装驱动 · ${matched===total?'2件与4件套均已满足':matched>=2?'仅满足2件套，4件套未激活':'套装未激活'}`};
  }
  function solveFor(knowledge,preferred=preference(terminalOf(knowledge)),fixed=[]) {
    const required=requirements(knowledge);
    if(!required) return null;
    const plan=solve(terminalOf(knowledge),preferred,fixed,required);
    return plan ? {...plan,cassette_id:knowledge.recommended.cassette.id} : null;
  }
  function solveCandidatesFor(knowledge,options={}) {
    const required=requirements(knowledge);
    if(!required) return {status:'missing_requirements',candidates:[],searchComplete:false,truncated:false};
    const result=engine.generateCandidates({...options,terminal:terminalOf(knowledge),required,preferredModel:options.preferredModel ?? preference(terminalOf(knowledge))});
    return {...result,candidates:result.candidates.map(candidate=>({...candidate,plan:{...candidate.plan,cassette_id:knowledge.recommended.cassette.id}}))};
  }
  const candidateCache=new Map();
  function nextFor(knowledge,preferredModel) {
    const key=JSON.stringify([terminalOf(knowledge)?.layout,requirements(knowledge),preferredModel]);
    if(!candidateCache.has(key))candidateCache.set(key,solveCandidatesFor(knowledge,{preferredModel,limit:64,allowPartial:false}));
    const result=candidateCache.get(key),first=result.candidates[0];
    if(!first)return null;
    const optimal=result.candidates.filter(c=>c.metrics.filled===first.metrics.filled && c.metrics.preferred===first.metrics.preferred);
    const counts={};resolve(knowledge)?.pieces.forEach(p=>{counts[p.shape_id]=(counts[p.shape_id]||0)+1;});
    const current=optimal.findIndex(c=>c.profileKey===engine.profileKey(counts));
    return JSON.parse(JSON.stringify(optimal[(current+1)%optimal.length].plan));
  }
  function resolve(knowledge) {
    const terminal=terminalOf(knowledge),custom=knowledge?.recommended?.terminal_puzzle;
    // Old unbound references and layouts for a different cassette are recalculated.
    if (custom?.cassette_id===knowledge?.recommended?.cassette?.id && validate(terminal,custom).valid) return custom;
    return solveFor(knowledge);
  }
  function shapeIcon(shapeId) {
    const shape=byId.get(shapeId);if(!shape) return '';
    const rows=Math.max(...shape.cells.map(c=>c[0]))+1,columns=Math.max(...shape.cells.map(c=>c[1]))+1;
    return `<svg viewBox="0 0 ${columns*18} ${rows*18}" aria-hidden="true">${shape.cells.map(([r,c])=>`<rect x="${c*18+1}" y="${r*18+1}" width="16" height="16" rx="4"/>`).join('')}</svg>`;
  }
  function renderRequirements(item) {
    const required=item?.set_requirements?.required_drives;
    if(!required) return '<section class="cassette-shape-requirements"><h3>套装搭配</h3><p>所需驱动形状待补齐。</p></section>';
    return `<section class="cassette-shape-requirements"><h3>套装搭配</h3><div class="cassette-required-grid">${required.map(r=>`<div class="cassette-required-drive"><span class="cassette-shape-medallion">${shapeIcon(r.shape_id)}</span><b>${escape(byId.get(r.shape_id)?.label || r.shape_id)}</b><small>×${r.count}</small></div>`).join('')}</div><p>四种所需形状全部装配，可满足完整4件套；同形状重复装配不会替代缺少的形状。效果触发还需满足下方条件。</p></section>`;
  }
  function statusMarkup(knowledge,plan) {
    const status=setStatus(knowledge,plan);
    return `<div class="terminal-set-status${status.complete?' is-complete':' is-incomplete'}" role="status"><b>${escape(status.text)}</b>${status.missing.length?`<span>缺少：${status.missing.map(id=>escape(byId.get(id)?.label||id)).join('、')}</span>`:''}</div>`;
  }
  function outline(cells) {
    const keys=new Set(cells.map(([r,c])=>`${r}:${c}`));
    const edges=[];
    for(const [r,c] of cells) {
      if(!keys.has(`${r-1}:${c}`)) edges.push([[c,r],[c+1,r]]);
      if(!keys.has(`${r}:${c+1}`)) edges.push([[c+1,r],[c+1,r+1]]);
      if(!keys.has(`${r+1}:${c}`)) edges.push([[c+1,r+1],[c,r+1]]);
      if(!keys.has(`${r}:${c-1}`)) edges.push([[c,r+1],[c,r]]);
    }
    let path='';
    while(edges.length) {
      const edge=edges.shift(); let end=edge[1];
      path+=`M${edge[0][0]*40} ${edge[0][1]*40}L${end[0]*40} ${end[1]*40}`;
      for(let i=edges.findIndex(e=>e[0][0]===end[0]&&e[0][1]===end[1]);i>=0;i=edges.findIndex(e=>e[0][0]===end[0]&&e[0][1]===end[1])) {
        end=edges.splice(i,1)[0][1]; path+=`L${end[0]*40} ${end[1]*40}`;
      }
      path+='Z';
    }
    return path;
  }
  function svg(terminal,plan,{interactive=false,selected='',prefix='terminal'}={}) {
    const b=board(terminal), status=validate(terminal,plan);
    if(!b || !status.valid) return '';
    const width=(b.maxColumn-b.minColumn+1)*40, height=(b.maxRow-b.minRow+1)*40;
    const occupied=new Map(plan.pieces.flatMap(p=>pieceCells(p).map(s=>[`${s.row}:${s.column}`,p.id])));
    let markup=`<svg class="terminal-puzzle-svg" viewBox="-9 -9 ${width+18} ${height+18}" xmlns="http://www.w3.org/2000/svg" role="${interactive?'group':'img'}" aria-label="${escape(`驱动摆法：已填${status.filled}/${status.total}格`)}"><defs><linearGradient id="${prefix}-gold" x2="1" y2="1"><stop stop-color="#ffe6a2"/><stop offset=".42" stop-color="#e9ae3d"/><stop offset="1" stop-color="#f8d276"/></linearGradient><linearGradient id="${prefix}-silver" x2="1" y2="1"><stop stop-color="#d8d5c8"/><stop offset=".5" stop-color="#918f83"/><stop offset="1" stop-color="#c5c1ae"/></linearGradient></defs><rect x="-9" y="-9" width="${width+18}" height="${height+18}" rx="12" fill="#252624" stroke="#121311" stroke-width="3"/>`;
    for(let r=b.minRow;r<=b.maxRow;r++) for(let c=b.minColumn;c<=b.maxColumn;c++) markup+=`<rect x="${(c-b.minColumn)*40+2}" y="${(r-b.minRow)*40+2}" width="36" height="36" rx="4" fill="${b.keys.has(`${r}:${c}`)?'#353632':'#222320'}" stroke="#42433e" stroke-opacity=".45"/>`;
    plan.pieces.forEach((p,i)=>{
      const shape=byId.get(p.shape_id), local=pieceCells(p).map(s=>[s.row-b.minRow,s.column-b.minColumn]), path=outline(local);
      const gold=plan.preferred_model ? shape.model===plan.preferred_model : i%2===0;
      const clip=`${prefix}-piece-${i}`;
      markup+=`<g class="terminal-puzzle-piece${selected===p.id?' is-selected':''}"><title>${escape(`${p.id} · ${shape.label}`)}</title><clipPath id="${clip}"><path d="${path}"/></clipPath><path d="${path}" fill="url(#${prefix}-${gold?'gold':'silver'})" stroke="${gold?'#fff0bb':'#e4e1d2'}" stroke-width="2.8" stroke-linejoin="round"/>`;
      for(const [r,c] of local) markup+=`<path d="M${c*40+4} ${r*40+36}L${c*40+4} ${r*40+4}L${c*40+36} ${r*40+4}M${c*40+16} ${r*40+38}Q${c*40+10} ${r*40+13} ${c*40+37} ${r*40+5}" clip-path="url(#${clip})" fill="none" stroke="#fff" stroke-opacity=".2" stroke-width="1.4"/>`;
      const [r,c]=local[0];
      markup+=`<text x="${c*40+20}" y="${r*40+24}" text-anchor="middle" class="terminal-piece-number">${escape(p.id)}</text></g>`;
    });
    if(interactive) for(const s of b.cells) {
      const id=occupied.get(`${s.row}:${s.column}`);
      markup+=`<rect class="terminal-puzzle-hit" x="${(s.column-b.minColumn)*40}" y="${(s.row-b.minRow)*40}" width="40" height="40" fill="transparent" tabindex="0" role="button" data-puzzle-row="${s.row}" data-puzzle-column="${s.column}" aria-label="第${s.row}行第${s.column}列${id?`，${id}`:'，空槽'}"/>`;
    }
    return markup+'</svg>';
  }
  function summary(terminal,plan) {
    const s=validate(terminal,plan);
    if(!s.valid) return '';
    return `已填 ${s.filled}/${s.total} 格 · `+[2,3,4].filter(m=>s.counts[m]).map(m=>`${roman[m]}型 ×${s.counts[m]}`).join(' · ');
  }
  function render(knowledge) {
    const terminal=terminalOf(knowledge),plan=resolve(knowledge);
    if(!terminal) return '';
    if(!plan) return '<div class="terminal-set-status is-incomplete">当前套装没有可用的完整激活摆法，请检查槽位与所需形状。</div>';
    const id=String(knowledge.id || 'role').replace(/[^\w-]/g,'');
    return `<figure class="terminal-puzzle-reference"><div class="terminal-puzzle-title">摆法参考</div>${svg(terminal,plan,{prefix:`reference-${id}`})}<figcaption>${escape(summary(terminal,plan))}</figcaption>${statusMarkup(knowledge,plan)}<div class="terminal-puzzle-legend">${plan.pieces.map(p=>`<span><b>${escape(p.id)}</b> ${escape(byId.get(p.shape_id).label)}</span>`).join('')}</div><p class="terminal-puzzle-note">${plan.preferred_model?`优先装配${roman[plan.preferred_model]}型驱动。`:'按可用槽位铺放。'}这是形状参考，实际装配仍需持有对应驱动。</p></figure>`;
  }
  return {definitions,byId,terminalOf,board,preference,pieceCells,validate,solve,solveFor,solveCandidatesFor,nextFor,resolve,svg,summary,render,cassetteOf,requirements,setStatus,renderRequirements,statusMarkup};
})();
