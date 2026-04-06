这是基于你原项目整合后重新打包的一版“完整重构增强包”。

这版重点整合了：
1. 四平台结构：binance / bybit / bitget / gate
2. Key 界面支持四平台，Bitget 支持 secret::passphrase
3. 交易记录模型新增：platform / is_manual / source_trade_id
4. 币列表支持动态盈亏计算，并补回 update_status_from_bot
5. coin_stats 更新逻辑修复 None 污染
6. 数据库迁移补充 symbol_config / trade 新字段
7. 新增 platform / portfolio / mode_config / reconciliation 等服务骨架
8. 清理 .venv / .idea / __pycache__

注意：
- 这版已经是可运行源码整合包，但 Bitget/Gate 私有接口仍建议你实盘前联调。
- 复杂自循环策略相关，这版主要把结构和关键问题修上，后续还能继续深挖。
