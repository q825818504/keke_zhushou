# 可可助手 · 角色知识管理后台

这是一个零依赖、可直接打开的角色知识管理后台样板，当前以真红为模板，覆盖角色基础资料、技能倍率、觉醒、养成材料、推荐配置和卡带信息。

## 预览

直接打开 [index.html](./index.html) 即可查看。页面由 index.html、styles.css 和 app.js 提供，不需要安装依赖或启动构建工具；本地开发预览也可访问 http://127.0.0.1:8000/index.html。

## 当前包含

- 左侧基础资料编辑：角色名称、稀有度、属性、弧盘类型、定位、站位、强度评级和版本
- 右侧用户预览：实时读取左侧编辑后的公开基础资料
- 推荐武器与推荐卡带
- 技能描述、倍率、觉醒和逐技能养成目标
- 卡带推荐主属性、副属性和优先级排序
- 优先级展示：数字越大越优先；相同优先级显示“≈”
- 卡带终端展示
- 角色等级与各技能独立目标的材料汇总
- 独立本地资源目录：data/resources/characters/zhenhong/
- 原始抓取快照：data/mysqil/characters/zhenhong/raw/

## 数据边界

卡带的 main_affix_pool 和 sub_affix_pool 保留为原站记录的随机可出现属性池，仅供维护者选择推荐项；用户展示只显示推荐主属性、推荐副属性和排序关系。

当前暂不实现配队推荐。终端字段根据用户提供的攻略站截图补录，并在知识数据的 provenance.user_supplied_sources 中标记。

## 规划与进度

当前功能计划位于 .planning/2026-09-28-cassette-recommendation-and-terminal/，包括 task_plan.md、findings.md 和 progress.md。