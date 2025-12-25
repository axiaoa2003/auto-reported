#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
健康打卡助手 - Windows启动器
负责设置工作目录和启动GUI应用
"""

import os
import sys
import traceback

# 设置工作目录 - 确保在正确的目录中运行
if getattr(sys, 'frozen', False):
    # 打包环境下，切换到可执行文件所在目录
    os.chdir(os.path.dirname(sys.executable))
else:
    # 开发环境下，使用脚本所在目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
print(f"工作目录: {os.getcwd()}")

# 添加当前目录到Python路径，确保可以导入所需模块
sys.path.insert(0, os.getcwd())

def setup_windows_logging():
    """设置基本日志配置"""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

def main():
    """
    主入口函数
    """
    try:
        print("启动健康打卡助手...")
        
        # 设置Windows专用日志
        setup_windows_logging()
        
        # 导入并启动原始GUI代码
        from health_check_gui import HealthCheckGUI
        
        # 显示启动信息
        print("正在初始化界面...")
        print("提示: 请确保已安装Microsoft Edge浏览器")
        print("如需帮助，请查看使用说明")
        print("="*50)
        
        # 启动GUI应用
        app = HealthCheckGUI()
        app.run()
        
    except ImportError as e:
        print("错误: 导入模块失败")
        print(f"请检查是否安装了所有必要的依赖: {str(e)}")
        print("建议运行: pip install selenium")
        traceback.print_exc()
        
    except Exception as e:
        print(f"错误: 应用程序运行时出错: {str(e)}")
        traceback.print_exc()
    finally:
        # 移除等待用户按键的逻辑，确保程序能够立即退出
        pass

if __name__ == "__main__":
    main()