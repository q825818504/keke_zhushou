"""Explicit single-item native decomposition, fresh guards and no automatic replay."""
from copy import deepcopy
import hashlib
import secrets
import threading
import time
from .decomposition_bridge import BridgeClient
from .equipment import equipment_state, fingerprint
from . import equipment_plans

MATERIALS={'experience':(1,'经验材料'),'rewind':(2,'倒带材料')}
RESULTS=['输入无效','宿主未就绪','不在游戏线程','风险模式未启用','所选物品已变化',
         '游戏版本不匹配','运行时代码已变化','当前角色会话无效','请求已经使用',
         '本次桥接请求数达到上限','分配失败','消息契约异常','已有分解执行中','本次桥接已停止']


class DecompositionService:
    def __init__(self,inventory):
        self.inventory=inventory
        self.bridge=BridgeClient(inventory.directory)
        self.plan=None
        self.job={'running':False,'state':'idle','message':'尚未执行内存分解'}
        self.bridge_view={'ready':False,'message':'尚未加载分解桥接'}

    def status(self):
        with self.inventory.lock:
            return {**deepcopy(self.job),'bridge':deepcopy(self.bridge_view),
                    'available':self.bridge.identity_path.is_file()}

    def _pid(self):
        from native.components import game_processes
        games=game_processes()
        if len(games)!=1: raise ValueError('请只运行一个游戏进程')
        return games[0]['pid']

    def load_bridge(self):
        with self.inventory.lock:
            if self.inventory.native_busy(): raise ValueError('请等待当前读取或装备操作结束')
        result=self.bridge.launch(self._pid())
        self.bridge_view={'ready':False,'message':result['message']}
        return result

    def check_bridge(self):
        result=self.bridge.status(self._pid())
        self.bridge_view=result
        return result

    def _protect(self,account,state,key):
        row=state['items'].get(key)
        if not row or row.get('equipped') is not False or row.get('locked') is not False:
            raise ValueError('物品已装备、已锁定或状态未知，禁止分解')
        if type(row.get('discarded')) is not bool: raise ValueError('物品状态未知，禁止分解')
        reference=equipment_plans.reference(row)
        for plan in equipment_plans.read(self.inventory.directory,account).values():
            if not isinstance(plan,dict): raise ValueError('配装方案损坏，请先检查')
            entries=[plan.get('core'),*plan.get('modules',[])]
            if any(isinstance(entry,dict) and entry.get('ref')==reference for entry in entries):
                raise ValueError('物品被已保存配装方案引用，禁止分解')
        local=self.inventory.management._read(account).get('sources',{}).get('native',{})
        if local.get(f'nte-equipment:{key[0]}:{key[1]}',{}).get('locked') is True:
            raise ValueError('物品有本地锁定保护，禁止分解')
        return row

    def preview(self,account,source,instance_ids,material):
        if not isinstance(account,str) or not account.strip() or len(account)>80: raise ValueError('账号无效')
        if source!='native' or not isinstance(instance_ids,list) or len(instance_ids)!=1:
            raise ValueError('测试版内存分解仅支持一件 DLL 原生装备')
        if material not in MATERIALS: raise ValueError('必须明确选择经验材料或倒带材料')
        with self.inventory.lock:
            if self.inventory.native_busy(): raise ValueError('已有原生操作，请稍候')
            if self.inventory.vision and self.inventory.vision.job.get('running'): raise ValueError('请先停止截图扫描')
            stored=self.inventory.load(account)
            profile=self.inventory.accounts.get(account)
            data=stored.get('inventory',{}).get('equipment',{})
            raw=stored.get('domains',{}).get('equipment')
            session=stored.get('native_sessions',{}).get('equipment',{})
            if (not profile or not profile.get('uid') or profile['uid']!=stored.get('account_uid')
                    or not isinstance(raw,dict) or data.get('source',{}).get('adapter')!='nte-native-v1'
                    or data.get('coverage',{}).get('collection_complete') is not True):
                raise ValueError('请先完整读取并核对当前账号的 DLL 库存')
            header=raw.get('header',{})
            if (type(session.get('pid')) is not int or session['pid']<=0
                    or any(session.get(a)!=header.get(b) for a,b in
                        (('provider_id','providerId'),('domain_key','domainKey'),('revision','revision'),('snapshot_id','snapshotId')))):
                raise ValueError('原生会话已失效，请重新读取库存')
            state=equipment_state(raw,(session['pid'],session['provider_id'],session['domain_key']))
            keys=[key for key in state['items'] if f'nte-equipment:{key[0]}:{key[1]}'==instance_ids[0]]
            if len(keys)!=1: raise ValueError('所选物品已失效')
            row=self._protect(account,state,keys[0])
            self.plan={'token':secrets.token_hex(24),'created':time.monotonic(),'account':account,
                'account_uid':profile['uid'],'pid':session['pid'],'key':keys[0],
                'fingerprint':fingerprint(state),'material':material,
                'name':row.get('names',{}).get('zh_cn') or str(row.get('item_id','装备'))}
            return {'token':self.plan['token'],'name':self.plan['name'],'total':1,
                    'material_name':MATERIALS[material][1],
                    'instruction':'请在游戏空幕分解页仅选中同一件物品；不要点击游戏内分解按钮。'}

    def start(self,token,risk_check):
        with self.inventory.lock:
            if self.inventory.native_busy(): raise ValueError('已有原生操作，请稍候')
            if not risk_check(): raise ValueError('请先启用风险模式')
            plan=self.plan
            if not isinstance(token,str) or not plan or not secrets.compare_digest(plan['token'],token):
                raise ValueError('分解确认已失效')
            self.plan=None
            if time.monotonic()-plan['created']>120: raise ValueError('分解预览已过期')
            if self.inventory.vision and self.inventory.vision.job.get('running'): raise ValueError('请先停止截图扫描')
            self.inventory.native_operation='decomposition'
            self.job={'running':True,'state':'preflight','message':'正在复核账号、装备和桥接状态',
                      'account':plan['account'],'material':plan['material']}
            threading.Thread(target=self._run,args=(plan,risk_check),daemon=True,name='native-decomposition').start()
            return self.status()

    def _set(self,**values):
        with self.inventory.lock: self.job.update(values)

    @staticmethod
    def _quantities(observation):
        result={}
        for row in observation.data.get('records',[]):
            if row.get('definition_id') is None: continue
            key=str(row['definition_id'])
            entry=result.setdefault(key,{'quantity':0,'name':row.get('name')})
            quantity=row.get('quantity')
            if type(quantity) is not int or quantity<0 or entry['quantity'] is None: entry['quantity']=None
            else: entry['quantity']+=quantity
        return result

    def _run(self,plan,risk_check):
        adapter=None
        dispatched=False
        audit={'account':plan['account'],'account_uid':plan['account_uid'],
               'uid':list(plan['key']),'material':plan['material'],'request_id':secrets.randbits(63) or 1}
        path=self.inventory.directory/'decomposition-operations'/(secrets.token_hex(16)+'.json')
        def record(): self.inventory._write(path,{**audit,'job':self.status()})
        try:
            adapter=self.inventory.equipment._open()
            if adapter.pid!=plan['pid']: raise ValueError('游戏进程已变化')
            self.inventory.verify_live_account(plan['account'],adapter.pid)
            state,observation=self.inventory.equipment._capture(adapter)
            if fingerprint(state)!=plan['fingerprint']: raise ValueError('库存与预览不同，请重新读取并生成分解预览')
            self._protect(plan['account'],state,plan['key'])
            baseline=adapter.read('items',lambda:None)
            audit['materials_before']=self._quantities(baseline)
            ready=self.bridge.exchange(adapter.pid)
            if not ready.get('ready') or ready.get('transport'): raise ValueError('分解桥接未就绪：'+ready.get('message',''))
            self.inventory.verify_live_account(plan['account'],adapter.pid)
            state2,observation=self.inventory.equipment._capture(adapter)
            if fingerprint(state2)!=fingerprint(state): raise ValueError('装备状态在分解前已变化，未派发请求')
            self._protect(plan['account'],state2,plan['key'])
            if not risk_check(): raise ValueError('风险模式已关闭，未派发请求')
            revision=int.from_bytes(hashlib.sha256(str(observation.raw_snapshot['header']).encode()).digest()[:8],'little') or 1
            audit.update(state='dispatching',snapshot_revision=revision)
            record()
            dispatched=True
            self._set(state='dispatching',message=f'正在提交单件内存分解，产物为{MATERIALS[plan["material"]][1]}')
            response=self.bridge.exchange(adapter.pid,2,audit['request_id'],revision,plan['key'],MATERIALS[plan['material']][0])
            audit['bridge_response']=response
            if response['transport']: raise ValueError('桥接拒绝或请求结果不明；禁止重发，请重新读取库存')
            if response['sender_result']!=14:
                code=response['sender_result']
                raise ValueError('原生发送器拒绝：'+(RESULTS[code] if code<len(RESULTS) else str(code)))
            self._set(state='observing',message='请求已派发，正在回读装备与材料；不会自动重发')
            removed=False
            for attempt in range(6):
                time.sleep(.5)
                self.inventory.verify_live_account(plan['account'],adapter.pid)
                after,after_observation=self.inventory.equipment._capture(adapter)
                if (after['context'][:2]!=state['context'][:2] or after['characters']!=state['characters']):
                    raise ValueError('回读账号或角色来源已变化，结果待核实')
                if plan['key'] not in after['items']:
                    if set(after['items'])!=set(state['items'])-{plan['key']}:
                        raise ValueError('观察到非目标物品变化，请保留日志核查')
                    self.inventory.equipment._save(plan['account'],after_observation,after['context'])
                    removed=True
                    break
            materials=adapter.read('items',lambda:None)
            audit['materials_after']=self._quantities(materials)
            audit['item_removed']=removed
            audit['material_deltas']={key:{'name':row['name'],'delta':row['quantity']-audit['materials_before'].get(key,{}).get('quantity',0)}
                for key,row in audit['materials_after'].items() if type(row['quantity']) is int
                and type(audit['materials_before'].get(key,{}).get('quantity',0)) is int
                and row['quantity']!=audit['materials_before'].get(key,{}).get('quantity',0)}
            # Material definition IDs have not been confirmed yet. Do not claim
            # success based on unrelated inventory increases or a dispatch return.
            if removed:
                self._set(state='settlement_unconfirmed',message='目标装备已从库存消失，材料变化已记录，产物结算仍待核实；请勿重复分解。')
            else:
                self._set(state='unconfirmed',message='尚未确认目标装备消失，请保留日志并重新读取库存；禁止重发。')
        except Exception as error:
            audit['error']=str(error)
            self._set(state='unconfirmed' if dispatched else 'blocked',message=str(error))
        finally:
            if adapter:
                try: adapter.close()
                except Exception: pass
            self._set(running=False,audit_path=str(path))
            try: record()
            except Exception as error: self._set(message=self.job['message']+'；日志保存失败：'+str(error))
            with self.inventory.lock: self.inventory.native_operation=None
