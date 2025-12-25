# 健康打卡助手

一款基于 Python 和 Selenium 的自动化健康打卡工具，专为若羌县志愿者每日健康打卡表单设计。

## 功能特性

- 自动填写并提交健康打卡表单
- 友好的图形用户界面 (GUI)
- 支持定时任务，每天自动执行打卡
- 配置文件管理，方便修改个人信息和打卡时间
- 系统托盘运行，后台任务不打扰工作
- 自动获取地理位置信息
- 智能重试机制，提高打卡成功率
- 完整的日志记录，便于追踪和调试

## 环境要求

- Windows 操作系统
- Python 3.7 或更高版本
- Microsoft Edge 浏览器（必须安装）

## 安装步骤

### 1. 克隆或下载项目

```bash
git clone https://github.com/axiaoa2003/auto-reported.git
cd auto-reported
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

依赖包包括：
- `pystray==0.19.5` - 系统托盘图标
- `Pillow==12.0.0` - 图像处理
- `selenium==4.39.0` - 浏览器自动化

## 配置说明

在使用前，请编辑 `health_config.json` 文件，配置个人信息和打卡时间：

```json
{
  "user_info": {
    "name": "您的姓名",
    "phone": "您的手机号",
    "unit": "您的服务单位",
    "temperature": "36.5"
  },
  "schedule": {
    "enabled": true,
    "hour": 8,
    "minute": 0
  },
  "browser": {
    "headless": false
  }
}
```

### 配置项说明

**user_info（用户信息）**
- `name`: 姓名
- `phone`: 手机号
- `unit`: 服务单位
- `temperature`: 体温（正常体温范围）

**schedule（定时任务）**
- `enabled`: 是否启用定时任务（true/false）
- `hour`: 打卡小时（0-23，24小时制）
- `minute`: 打卡分钟（0-59）

**browser（浏览器设置）**
- `headless`: 是否使用无头模式（true=后台运行，false=显示浏览器窗口）

## 使用方法

### 方法一：直接运行 Python 脚本

```bash
python gui_launcher.py
```

### 方法二：使用 PyInstaller 打包为可执行文件

1. 安装 PyInstaller：
```bash
pip install pyinstaller
```

2. 打包程序：
```bash
pyinstaller --onefile --windowed --icon=alien.png gui_launcher.py
```

3. 运行生成的 `gui_launcher.exe`

## 程序界面

程序启动后，会显示一个简洁的 GUI 界面，包含以下功能：

- **立即打卡**：手动触发一次打卡操作
- **启动定时任务**：启用定时自动打卡
- **停止定时任务**：停止定时任务
- **最小化到托盘**：将程序最小化到系统托盘
- **查看日志**：实时查看程序运行日志

## 常见问题

### 1. 打卡失败怎么办？

- 检查网络连接是否正常
- 确认 Edge 浏览器已正确安装
- 查看日志了解具体错误信息
- 尝试关闭无头模式，观察浏览器操作过程

### 2. 定时任务不执行？

- 确认配置文件中 `schedule.enabled` 为 `true`
- 检查设置的时间是否正确（24小时制）
- 确保程序保持运行状态

### 3. 浏览器无法启动？

- 确认已安装 Microsoft Edge 浏览器
- 检查 Edge 浏览器版本是否过旧
- 尝试更新 Edge 浏览器到最新版本

### 4. 如何查看详细日志？

程序运行日志会实时显示在 GUI 界面的日志窗口中。如需保存日志，可以在程序目录下找到 `error.log` 文件。

## 注意事项

1. **隐私安全**：配置文件包含个人信息，请注意保护文件安全
2. **网络要求**：打卡操作需要稳定的网络连接
3. **时间设置**：建议设置在合适的打卡时间，避免过早或过晚
4. **浏览器权限**：程序会请求地理位置权限，请允许
5. **资源占用**：程序执行打卡时会启动 Edge 浏览器，完成后会自动关闭

## 文件结构

```
auto-reported/
├── gui_launcher.py          # 主启动器
├── health_check_gui.py      # GUI 界面模块
├── health_check_core.py     # 核心自动化功能
├── logger_config.py         # 日志配置模块
├── health_config.json       # 配置文件（需自行修改）
├── requirements.txt         # Python 依赖
├── .gitignore              # Git 忽略文件
├── alien.png               # 程序图标
├── README.md               # 项目说明文档
└── README_SCHEDULER.md     # 调度器相关说明
```

## 技术栈

- **Python 3.7+**: 主要编程语言
- **Selenium 4.39.0**: 浏览器自动化框架
- **Microsoft Edge WebDriver**: 浏览器驱动
- **Tkinter**: GUI 界面框架
- **Pystray**: 系统托盘功能
- **Threading**: 多线程支持

## 开发者信息

- 开发者：axiaoa2003
- 项目地址：https://github.com/axiaoa2003/auto-reported

## 许可证

本项目仅供学习和个人使用。请勿用于商业用途。

## 更新日志

### Version 5.5
- 优化资源占用和内存管理
- 实现按需加载机制
- 添加系统托盘功能
- 优化调度器性能
- 增强错误处理和重试机制
- 完善日志记录系统

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目。

## 免责声明

本工具仅用于自动化健康打卡，使用本工具产生的任何后果由使用者自行承担。请确保在规定时间内完成打卡，并遵守相关规定。
