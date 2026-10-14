# 调查

用户当前启动弹窗和手动入口共用release_status，均只读当前release-notes.json。需要独立历史数组，手动版本切换；自动提示不包含历史。

同版本重新构建需在签名清单/release-info增加内部revision，程序对外仍1.3；已读键包括version+revision。构建patch保留配置编号与程序版本，publisher只允许递增revision。
