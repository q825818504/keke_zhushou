"""Local-only management labels for saved backpack snapshots."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import secrets


MAX_ANNOTATION_BYTES = 16 * 1024 * 1024
MAX_UPDATES = 262144


class BackpackManagement:
    """Store reversible local labels without changing captured game data."""

    def __init__(self, inventory):
        self.inventory = inventory
        self.directory = inventory.directory

    def path_for(self, account):
        return self.directory / ('backpack-management-' + hashlib.sha256(account.encode()).hexdigest() + '.json')

    def _read(self, account):
        path = self.path_for(account)
        if path.is_symlink():
            raise ValueError('背包管理数据路径无效，请保留文件检查')
        try:
            if path.stat().st_size > MAX_ANNOTATION_BYTES:
                raise ValueError('背包管理数据过大，请保留文件检查')
            value = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {'schema_version': 1, 'account': account, 'sources': {}}
        if (not isinstance(value, dict) or value.get('schema_version') != 1
                or value.get('account') != account or not isinstance(value.get('sources'), dict)
                or len(value['sources']) > 2048):
            raise ValueError('背包管理数据格式无效，请保留文件检查')
        count = 0
        for source, entries in value['sources'].items():
            if not isinstance(source, str) or len(source) > 96 or not isinstance(entries, dict):
                raise ValueError('背包管理来源记录无效，请保留文件检查')
            count += len(entries)
            if count > MAX_UPDATES:
                raise ValueError('背包管理条目过多，请保留文件检查')
            for identity, flags in entries.items():
                if (not isinstance(identity, str) or not identity or len(identity) > 256
                        or not isinstance(flags, dict) or set(flags) - {'locked', 'discarded'}
                        or any(type(flag) is not bool for flag in flags.values())):
                    raise ValueError('背包管理条目标记无效，请保留文件检查')
        return value

    def _write(self, account, value):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(account)
        root = self.directory.resolve()
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('背包管理数据路径无效，已停止保存')
        temporary = path.with_suffix('.' + secrets.token_hex(8) + '.tmp')
        try:
            payload = json.dumps(value, ensure_ascii=False, allow_nan=False)
            if len(payload.encode('utf-8')) > MAX_ANNOTATION_BYTES:
                raise ValueError('背包管理数据超过本机保存上限')
            temporary.write_text(payload, encoding='utf-8')
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def inspect(self, account, source='auto'):
        if not isinstance(account, str) or not account.strip() or len(account) > 80:
            raise ValueError('账号资料无效')
        with self.inventory.lock:
            view = self.inventory.view(account, source)
            selected = view.get('selected_source', 'none')
            annotations = self._read(account).get('sources', {}).get(selected, {}) if selected != 'none' else {}
            records = view.get('inventory', {}).get('equipment', {}).get('records', [])
            available = {row.get('instance_id') for row in records if isinstance(row.get('instance_id'), str)}
            annotations = {key: deepcopy(value) for key, value in annotations.items() if key in available}
            return {'account': account, 'selected_source': selected,
                    'sources': view.get('sources', []), 'annotations': annotations}

    def save(self, account, source, updates):
        if not isinstance(account, str) or not account.strip() or len(account) > 80:
            raise ValueError('账号资料无效')
        if not isinstance(source, str) or len(source) > 96 or source in ('', 'auto', 'none'):
            raise ValueError('请先选择一份有效的背包数据')
        if (not isinstance(updates, dict) or len(updates) > MAX_UPDATES
                or any(not isinstance(key, str) or not key or len(key) > 256 for key in updates)):
            raise ValueError('背包管理修改清单无效')
        for flags in updates.values():
            if (not isinstance(flags, dict) or not flags or set(flags) - {'locked', 'discarded'}
                    or any(type(value) is not bool for value in flags.values())):
                raise ValueError('背包管理标记必须是锁定或弃置状态')
        with self.inventory.lock:
            if self.inventory.native_busy():
                raise ValueError('请等待原生读取或装备操作结束后再保存背包管理标记')
            if self.inventory.vision and self.inventory.vision.job.get('running'):
                raise ValueError('请等待截图识别结束后再保存背包管理标记')
            view = self.inventory.view(account, source)
            if view.get('selected_source') != source:
                raise ValueError('所选背包快照已变化，请重新载入后再保存')
            if source not in {row.get('id') for row in view.get('sources', [])}:
                raise ValueError('当前账号没有这份背包数据')
            records = view.get('inventory', {}).get('equipment', {}).get('records', [])
            available = {row.get('instance_id') for row in records if isinstance(row.get('instance_id'), str)}
            if not set(updates).issubset(available):
                raise ValueError('修改清单包含已过期装备，请重新载入')
            document = self._read(account)
            entries = document.setdefault('sources', {}).setdefault(source, {})
            for identity, flags in updates.items():
                current = entries.setdefault(identity, {})
                current.update(flags)
            document['account'] = account
            self._write(account, document)
            return self.inspect(account, source)['annotations']

    def delete_source(self, account, source):
        with self.inventory.lock:
            document = self._read(account)
            if document.get('sources', {}).pop(source, None) is not None:
                self._write(account, document)
