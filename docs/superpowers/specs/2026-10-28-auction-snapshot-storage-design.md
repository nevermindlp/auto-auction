# 拍卖行跨服明细快照结构化存储 — 设计规格

> 日期：2026-10-28  
> 状态：已对话确认（含导航修订：逐子类扫描、不用「全部」）  
> 范围：宠物 + 装备全量最细落库；宠物装备后置；不做跨快照追踪

## 1. 目标与非目标

### 1.1 目标

在与游戏同机的 Windows 环境上，通过自动点击/翻页/打开详情，采集交易所**跨服 · 购买**下的：

- **宠物**挂单最细明细  
- **装备**挂单最细明细  

写入本地 **SQLite 单文件**，支持：

1. **组合条件查询**（主场景）  
2. 约 **5 小时**一轮全量刷新  
3. 新热快照就绪后，旧热数据**归档**（同库归档表 + 定期导出备份文件）  
4. 采集/游戏退出后，分析工具仍可**独立连接**数据库  

说明：口语中的「道具」在本范围等同 **装备**，不另建表。

### 1.2 非目标（本版不做）

- 跨快照「同一挂单」业务追踪  
- 宠物 / 装备跨类关联查询或一张宽表揉合  
- 宠物装备明细采集（仅知为大类，后置）  
- 本服；出售页；「全部」子类入口扫描  
- PostgreSQL / 常驻 DB 服务  
- 价格走势聚合视图（有明细后再做）  

## 2. 拍卖行机制理解（设计前提）

| 项 | 约定 |
|----|------|
| 大类 | 只关心：装备、宠物、宠物装备（后置） |
| 服区 | 只采 **跨服**（界面「跨服」，即需求中的全服） |
| 页签 | 购买 |
| 导航层次 | 大类 → **具体子类/系别** → 分页列表 → 详情 |
| 子类策略 | **逐子类扫描，不使用「全部」**（「全部」与各子类为包含关系，点全部会造成重复采集） |
| 列表形态 | 约 8 格/页或列表行；页数可达千级 |
| 详情 | 宠物含成长等；装备含基础/附加/特殊/精灵；关详情后继续 |

## 3. 架构（方案 1）

```text
游戏客户端（同机）
        ↑ 截屏 / 点击 / 翻页
auto-auction 采集进程
        ↓
SQLite  data/auto_auction.db  （WAL）
  ├─ snapshots
  ├─ 字典表（动态增补，遇新即用）
  ├─ pet_listings / equip_listings          （热：当前 hot 轮）
  ├─ pet_listings_archive / equip_listings_archive
  └─ （其它元数据按需）
        ↓ 归档后导出
archive/snapshot_<id>_<timestamp>.db
```

分析：进程退出后用 DB Browser / DBeaver / Python 等直接打开 `.db`。

相对现有工程：复用 ROI/点击/OCR；新增导航状态机、字段解析、字典服务、SQLite 仓储、快照轮转与导出。

## 4. 采集导航

```text
进入交易所
  → 点击「跨服」
  → 「购买」
  → 对大类 ∈ {宠物, 装备}：
       → 枚举该大类下全部「具体子类」（跳过「全部」）
            → 对每一子类：
                 → 进入列表，从第 1 页翻到末页
                 → 每条：读列表字段 → 打开详情采齐 → 关闭详情
       → 下一子类
  → 批次收尾、热/归档轮转、导出备份
```

- 子类列表来源：界面网格/侧栏点选；实现阶段用配置或首次探测缓存。  
- 详情价可与列表价校验，**只存一个 `price`**。  
- 长耗时轮次中 `snapshots.status=running`，已写入行可被只读查询（WAL）。

## 5. 数据模型

### 5.1 `snapshots`

| 字段 | 含义 |
|------|------|
| `id` | 主键；明细中的 `snapshot_id` |
| `started_at` / `finished_at` | 开始/结束时间 |
| `status` | `running` / `hot` / `archived` / `failed` |
| `pet_count` / `equip_count` | 本轮条数（结束回填） |
| `note` | 备注 |

### 5.2 字典表（动态补充）

分表示例：`dict_growth_tier`、`dict_pet_quality`、`dict_extra_attr_type`、`dict_extra_attr_quality`、`dict_special_attr`、`dict_spirit_skill`、`dict_basic_attr_kind`、`dict_item_type`、`dict_subcategory` 等。

统一列：`id`，`code`，`name`，`first_seen_at`，`hit_count`（可选）。

**规则：** OCR/解析得到的值在字典中不存在时，**立即 INSERT 并视为可用**，明细正常引用（可能引入误识别，靠 `hit_count`/人工日后清理）。明细可冗余存显示名以便单表分析。

### 5.3 热表 `pet_listings`

| 字段 | 含义 |
|------|------|
| `id` | 行主键 |
| `snapshot_id` | 批次 |
| `captured_at` | 本条采集时间 |
| `subcategory` | 系别/子类（具体系别名，非「全部」） |
| `page_no` / `slot_index` | 页码、格位 |
| `name` | 名称 |
| `level_text` | 等级原文 |
| `rebirth` | `0` 或 `1`（游戏仅两档） |
| `level` | 等级数字 |
| `level_index` | `rebirth * 131 + level`，**仅排序** |
| `price` | 价格（贝壳） |
| `preorder_count` | 预购人数 |
| `list_status` | 列表状态 |
| `publicity_remain` | 公示剩余时间 |
| `quality` | `彩色` / `红色` / `普通` |
| `growth_total` / `growth_hp` / `growth_atk` / `growth_def` / `growth_agi` | 成长当前值（上限不存） |
| `growth_*_tier` | `大爆` / `小爆` / `常规` / `小残` / `大残` |
| `raw_list_ocr` / `raw_detail_ocr` | OCR 备份 |

**不存：** `server_scope`、`market_tab`、`currency`、成长上限、属性页、技能/突破、详情交易区堆叠字段。

建议索引：`snapshot_id`；`(name, price)`；`(rebirth, level)`；`growth_total`；`preorder_count`；`quality`；`subcategory`。

归档表 `pet_listings_archive`：同结构。

### 5.4 热表 `equip_listings`

| 字段 | 含义 |
|------|------|
| `id` | 行主键 |
| `snapshot_id` / `captured_at` | 批次、时间 |
| `subcategory` / `page_no` / `slot_index` | 具体子类与定位（非「全部」） |
| `list_status` / `publicity_remain` | 公示 |
| `preorder_count` | 预购人数 |
| `name` / `item_type` / `enhance` / `enhance_text` / `price` | 详情基础信息 |
| `basic_attr_kind` | 基础属性模式枚举 |
| `stat_atk` / `stat_agi` / `stat_hp` / `stat_def` | 基础属性当前值（可空；**无区间**） |
| `extra_attr_count` | `0` / `1` / `2` |
| `extra_attr1_type` / `value` / `quality` | 附加词条 1；品质 `红/橙/紫/蓝` |
| `extra_attr2_type` / `value` / `quality` | 附加词条 2（可空） |
| `special_attr` | 特殊属性整项枚举 |
| `spirit_skill` | 精灵技能枚举 |
| `raw_list_ocr` / `raw_detail_ocr` | OCR 备份 |

**不存：** 已装备对比栏；详情交易区独立单价/数量列（价格只保留 `price`）。

建议索引：`snapshot_id`；`(name, enhance, price)`；`extra_attr_count`；`(extra_attr1_type, extra_attr2_type)`；`spirit_skill`；`preorder_count`；`subcategory`。

归档表 `equip_listings_archive`：同结构。

## 6. 快照生命周期

1. 插入 `snapshots`，`status=running`  
2. 按 §4 写入热表  
3. 成功：本轮 `status=hot`，回填计数  
4. 若存在上一 `hot` 轮：其明细 → `*_archive`，热表删除该 `snapshot_id`，该批次 → `archived`  
5. 导出 `archive/snapshot_<id>_<timestamp>.db`（或等价备份）  
6. 失败：`failed`；不自动取代仍有效的上一 `hot`  

查当前盘 → 热表；查历史 → 归档表或备份文件。

## 7. 查询约定（主场景）

- 当前盘：热表 + 当前 `hot` 的 `snapshot_id`  
- 历史：`*_archive` 按批次/时间过滤  
- 宠物：名称、转生+等级、价格、预购、品质、成长与档位、子类  
- 装备：名称、强化、价格、预购、基础属性模式+数值、双附加词条、特殊属性、精灵技能、子类  

## 8. 验收（设计层）

- 独立打开 `.db` 可查热表、归档表、字典动态行  
- 导航逻辑**不进入「全部」子类**，只逐具体子类  
- 新轮完成后热表仅当前 hot；旧数据在归档侧且有导出文件  
- 宠物/装备字段与本文 §5 一致（含 `preorder_count`）  

## 9. 决策记录摘要

| 决策 | 选择 |
|------|------|
| 库 | SQLite 单文件 + WAL |
| 归档 | 同库归档表 + 导出备份（方案 C） |
| 架构 | 单进程采集器直写 SQLite（方案 1） |
| 字典 | DB 字典表，遇新立即插入可用 |
| 追踪 | 本版不做 |
| 子类 | 逐系别/子类，不用「全部」 |
| 等级 | `rebirth`+`level` 主查，`level_index` 排序 |
| 装备基础属性 | kind 枚举 + atk/agi/hp/def 当前值 |
| 附加属性 | 最多 2 条 + `extra_attr_count` |
| 特殊属性/精灵 | 整项枚举 |

---

**文档自检：** 无 TBD；「全部」已排除；预购人数已纳入宠物与装备；确认前不实现业务代码。
