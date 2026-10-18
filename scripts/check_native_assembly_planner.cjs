const assert=require('node:assert/strict');
const engine=require('../drive_layout_solver.js');
const planner=require('../native_assembly_planner.js');
const catalog=require('../desktop/inventory/equipment-layouts.json');
const shapes=Object.entries(catalog.shapes).map(([geometry,cells],i)=>({id:'i'+i,category:'drive',cells,geometry}));
assert.equal(new Set(shapes.map(i=>planner.shapeOf(i)?.id)).size,12);
for(const [cid,entry]of Object.entries(catalog.characters))for(const item of shapes){
 const info={characters:[{character_id:Number(cid),board:entry.cells}],items:[item]};
 const result=planner.plan(info,Number(cid),[item.id]);
 const terminal={layout:{rows:5,columns:5,active_slots:entry.cells.map(([row,column])=>({row,column}))}};
 assert.equal(engine.validate(terminal,{version:1,preferred_model:0,pieces:result.map(p=>({id:'D01',shape_id:planner.shapeOf(item).id,row:p.row,column:p.column}))}).valid,true);
}
const selected=shapes.filter(i=>['Hen2','ZhiJiao1','ZhiJiao3','Shu4'].includes(i.geometry));
const info={characters:[{character_id:1051,board:catalog.characters['1051'].cells}],items:selected};
const layout=planner.plan(info,1051,selected.map(i=>i.id));
assert.equal(layout.length,4);assert.equal(new Set(layout.map(p=>p.id)).size,4);
assert.throws(()=>planner.plan(info,1051,[selected[0].id,selected[0].id]),/重复/);
assert.throws(()=>planner.plan(info,1051,['unknown']));
assert.throws(()=>planner.plan(info,9999,[selected[0].id]));
console.log('Native shared layout adapter passed: all 12 shape orientations, 300 character/shape placements, four-piece native loadout, duplicate/unknown instance rejection.');
