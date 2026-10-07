/* Admin-only terminal placement tools. Drafts follow the existing role save lifecycle. */
window.TerminalPuzzleEditor = (() => {
  let selectedShape = '', selectedPiece = '', roleId = '';
  const puzzle = () => window.TerminalPuzzle;
  function changed(knowledge,plan) {
    if(!plan) {notify('保留现有驱动后无法满足完整套装；请移除部分驱动或按所选型号重排');return;}
    plan.cassette_id=knowledge.recommended?.cassette?.id;
    knowledge.recommended ||= {};
    knowledge.recommended.terminal_puzzle = plan;
    setText('#draftLabel','草稿未保存');
    setText('#recommendationStatus','摆法已修改，待保存');
    window.dispatchEvent(new Event('keke-role-dirty'));
    renderCassette(knowledge);
    if(document.body.classList.contains('user-mode')) renderUserTabPanel(knowledge);
    render(knowledge);
  }
  function render(knowledge) {
    const root = document.querySelector('#terminalPuzzleEditor');
    if(!root) return;
    const p=puzzle(),terminal=p.terminalOf(knowledge),plan=p.resolve(knowledge);
    if(roleId!==knowledge?.id) { roleId=knowledge?.id; selectedShape=''; selectedPiece=''; }
    if(!plan) { root.innerHTML=`<p class="terminal-editor-note">${p.board(terminal)?'请先配置有完整形状资料的推荐空幕，再计算套装摆法。':'该角色暂无终端槽位资料。'}</p>`; return; }
    if(selectedPiece && !plan.pieces.some(piece=>piece.id===selectedPiece)) selectedPiece='';
    const choice=selectedPiece ? plan.pieces.find(piece=>piece.id===selectedPiece)?.shape_id : selectedShape;
    const shape=p.byId.get(choice);
    root.innerHTML=`<div class="terminal-editor-toolbar"><label>优先型号<select id="terminalPuzzlePreference"><option value="0"${plan.preferred_model===0?' selected':''}>不限型号</option>${[2,3,4].map(m=>`<option value="${m}"${plan.preferred_model===m?' selected':''}>${{2:'Ⅱ',3:'Ⅲ',4:'Ⅳ'}[m]}型</option>`).join('')}</select></label><button type="button" class="outline-button" data-puzzle-action="default">恢复默认摆法</button><button type="button" class="outline-button" data-puzzle-action="auto">按所选型号重排</button><button type="button" class="outline-button" data-puzzle-action="fill">补满空槽</button><button type="button" class="outline-button" data-puzzle-action="clear">清空摆法</button></div><div class="terminal-editor-content"><div class="terminal-editor-board"><div class="terminal-puzzle-title">摆法参考</div>${p.svg(terminal,plan,{interactive:true,selected:selectedPiece,prefix:'editor-board'})}<div class="terminal-editor-stats">${p.summary(terminal,plan)}</div>${p.statusMarkup(knowledge,plan)}</div><div class="terminal-shape-palette" aria-label="选择驱动形状">${p.definitions.map(s=>{
      const maxRow=Math.max(...s.cells.map(c=>c[0]))+1,maxColumn=Math.max(...s.cells.map(c=>c[1]))+1;
      const preview=`<svg viewBox="0 0 ${maxColumn*16} ${maxRow*16}" aria-hidden="true">${s.cells.map(([r,c])=>`<rect x="${c*16+1}" y="${r*16+1}" width="14" height="14" rx="2"/>`).join('')}</svg>`;
      return `<button type="button" draggable="true" class="terminal-shape-option${choice===s.id?' is-selected':''}" data-puzzle-shape="${s.id}" aria-pressed="${choice===s.id}">${preview}<span>${s.label}</span></button>`;
    }).join('')}</div></div><div class="terminal-editor-selection" role="status">${selectedPiece?`已选 ${selectedPiece} · ${shape.label}，点击空槽移动。`:shape?`已选 ${shape.label}，点击空槽放置。`:'先选择形状，再点击空槽；点击已有驱动可选择并移动。'}<button type="button" class="outline-button" data-puzzle-action="remove"${selectedPiece?'':' disabled'}>移除所选</button><button type="button" class="outline-button" data-puzzle-action="undo"${undoByRole.has(knowledge.id)?'':' disabled'}>撤销一步</button><button type="button" class="primary-button" data-puzzle-action="save">保存摆法</button></div><p class="terminal-editor-note">可点击或拖入形状。点击的格子对应形状最上行的第一个格；固定朝向需选择对应形状。补满保留已摆驱动，恢复默认按角色效果重新计算。保存沿用角色资料保存。</p>`;
    if(root.dataset.bound) return;
    root.dataset.bound='true';
    root.addEventListener('click',handleClick);
    root.addEventListener('change',event=>{
      if(event.target.id!=='terminalPuzzlePreference') return;
      const k=activeKnowledge, plan=structuredClone(puzzle().resolve(k));
      plan.preferred_model=Number(event.target.value); remember(k); changed(k,plan);
    });
    root.addEventListener('keydown',event=>{
      if((event.key==='Enter'||event.key===' ') && event.target.matches('[data-puzzle-row]')) {event.preventDefault();handleClick(event);}
      if(event.key==='Delete' && selectedPiece) {event.preventDefault();remove(activeKnowledge);}
    });
    root.addEventListener('dragstart',event=>{
      const button=event.target.closest('[data-puzzle-shape]');
      if(button) {event.dataTransfer.setData('text/x-keke-drive-shape',button.dataset.puzzleShape);event.dataTransfer.effectAllowed='copy';}
    });
    root.addEventListener('dragover',event=>{if(event.target.closest('[data-puzzle-row]') && [...event.dataTransfer.types].includes('text/x-keke-drive-shape')) event.preventDefault();});
    root.addEventListener('drop',event=>{
      const cell=event.target.closest('[data-puzzle-row]'), id=event.dataTransfer.getData('text/x-keke-drive-shape');
      if(!cell || !puzzle().byId.has(id)) return;
      event.preventDefault();selectedShape=id;selectedPiece='';place(activeKnowledge,Number(cell.dataset.puzzleRow),Number(cell.dataset.puzzleColumn));
    });
  }
  const undoByRole=new Map();
  function remember(k) {undoByRole.set(k.id,structuredClone(puzzle().resolve(k)));}
  function remove(k) {
    if(!selectedPiece) return;
    const plan=structuredClone(puzzle().resolve(k));
    remember(k); plan.pieces=plan.pieces.filter(p=>p.id!==selectedPiece);selectedPiece='';changed(k,plan);
  }
  function place(k,row,column) {
    const p=puzzle(),terminal=p.terminalOf(k),plan=structuredClone(p.resolve(k));
    const current=plan.pieces.find(piece=>p.pieceCells(piece).some(s=>s.row===row&&s.column===column));
    if(current) {selectedPiece=current.id;selectedShape='';render(k);return;}
    const moving=plan.pieces.find(piece=>piece.id===selectedPiece);
    const shape=p.byId.get(moving?.shape_id || selectedShape);
    if(!shape) {notify('请先选择驱动形状');return;}
    let counter=1; while(plan.pieces.some(piece=>piece.id===`D${String(counter).padStart(2,'0')}`)) counter++;
    const candidate={id:moving?.id || `D${String(counter).padStart(2,'0')}`,shape_id:shape.id,row:row-shape.cells[0][0],column:column-shape.cells[0][1]};
    plan.pieces=plan.pieces.filter(piece=>piece.id!==moving?.id).concat(candidate);
    const status=p.validate(terminal,plan);
    if(!status.valid) {notify('此处放不下：请避开其他驱动和不可用槽位');return;}
    remember(k);selectedPiece='';changed(k,plan);
  }
  function handleClick(event) {
    const k=activeKnowledge, p=puzzle();
    if(!k) return;
    const shapeButton=event.target.closest('[data-puzzle-shape]');
    if(shapeButton) {selectedShape=shapeButton.dataset.puzzleShape;selectedPiece='';render(k);return;}
    const cell=event.target.closest('[data-puzzle-row]');
    if(cell) {place(k,Number(cell.dataset.puzzleRow),Number(cell.dataset.puzzleColumn));return;}
    const action=event.target.closest('[data-puzzle-action]')?.dataset.puzzleAction;
    if(!action) return;
    const terminal=p.terminalOf(k), plan=p.resolve(k);
    if(action==='save') {document.querySelector('#saveDraftButton')?.click();return;}
    if(action==='remove') {remove(k);return;}
    if(action==='undo') {const previous=undoByRole.get(k.id);if(previous){undoByRole.delete(k.id);selectedPiece='';changed(k,previous);}return;}
    remember(k);selectedPiece='';
    if(action==='clear') changed(k,{version:1,preferred_model:plan.preferred_model,pieces:[]});
    if(action==='default') changed(k,p.solveFor(k));
    if(action==='auto') changed(k,p.nextFor(k,plan.preferred_model));
    if(action==='fill') changed(k,p.solveFor(k,plan.preferred_model,plan.pieces));
  }
  return {render};
})();
