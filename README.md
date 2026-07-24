# auto-auction

基于**固定屏幕 ROI** 截屏 + **固定坐标点击** + **RapidOCR**（`rapidocr` + `onnxruntime`）的拍卖行宠物「低价捡漏」自动化（优先 Windows）。

MVP：你手动进入「宠物筛选后的结果页」后启动程序，自动扫描最多 N 页；价格低于阈值才打开详情；成长比（当前/总成长）> 0.98 则收藏并继续。

## 风险提示

自动化可能违反游戏服务条款或触发反作弊；请自行评估风险，本项目仅供技术学习与交流。

## 环境

- Python 3.11+
- 分辨率 / 显示缩放须与标定时一致

## 安装

```bash
cd auto-auction
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## 标定（建议顺序）

1. `--pick-roi`：框选游戏结果页区域  
2. `--calibrate-point --key clicks.slots.0` … `clicks.slots.7`：8 个条目中心  
3. `--calibrate-rect --key ocr_regions.slots.0.price` … 各槽价格区  
4. `--calibrate-rect --key ocr_regions.detail.total_growth` / `current_growth`  
5. `--calibrate-point --key clicks.favorite` / `close_detail` / `next_page`  
6. `--probe-ocr`：检查 OCR 是否读出合理数字  

```bash
python -m auto_auction --pick-roi
python -m auto_auction --calibrate-point --key clicks.next_page
python -m auto_auction --calibrate-rect --key ocr_regions.detail.total_growth
python -m auto_auction --probe-ocr
```

## 运行

先手动打开宠物筛选结果页，再：

```bash
python -m auto_auction
# 或
auto-auction
```

CLI：`start` / `stop` / `status` / `quit`（支持中文：开始/暂停/状态/退出）

- `--dry-run`：只打日志不点击  
- `--config path.yaml`：指定配置  

命中彩线截图：`artifacts/hits/`；OCR 失败裁剪：`artifacts/debug/`。

## 配置要点

见 `config/default.yaml`：

- `scan.price_threshold`：低于此价才开详情  
- `scan.color_line_ratio`：默认 `0.98`（严格大于）  
- `scan.max_pages`：最多扫描页数  
- `clicks.*` / `ocr_regions.*`：相对 ROI 的点击点与 OCR 矩形  

## 测试

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

## 本期不做

进入拍卖行/筛选导航、装备扫描、模板匹配、自动购买。

设计规格见同工作区 `auto-arena` 仓库文档：`docs/superpowers/specs/2026-07-24-auto-auction-pet-bargain-design.md`。
