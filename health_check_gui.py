#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
健康打卡助手 - GUI界面模块（系统托盘版）
作者: MiniMax Agent、AI助手、@EpsilonLux
版本: 5.1
Windows专用，仅支持EDGE浏览器
"""

import sys
import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import threading
import time
# 已移除schedule库，使用threading.Timer实现轻量级调度
from datetime import datetime
from logger_config import info, warning, error
# 在第22行后添加
def _get_config_path():
    """获取配置文件绝对路径 - 始终从可执行文件或脚本同目录读取"""
    if getattr(sys, 'frozen', False):
        # 在PyInstaller打包环境中 - 从可执行文件所在目录读取
        base_path = os.path.dirname(sys.executable)
    else:
        # 在开发环境中 - 从脚本所在目录读取
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    config_path = os.path.join(base_path, 'health_config.json')
    return config_path
# Selenium功能已移至health_check_core.py
SELENIUM_AVAILABLE = False

# Windows系统托盘支持
try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    # Windows环境下优先确保托盘功能


class HealthCheckGUI:
    """健康打卡助手GUI界面 - 系统托盘版"""

    def __init__(self):
        self.root = tk.Tk()
        # 创建窗口后立即隐藏，避免空白窗口闪烁
        self.root.withdraw()
        
        # 运行状态标志
        self._running = True
        
        # 配置文件相关变量
        self.config_file = _get_config_path()
        self.status_text = None  # 状态显示框 - 必须在 create_widgets 之前初始化
        self.config = self.load_config()  # 程序首次启动时读取配置文件
        
        # 确保配置中自动打卡始终启用
        if "schedule" not in self.config:
            self.config["schedule"] = {}
        self.config["schedule"]["enabled"] = True
        self.tray_icon = None
        self.driver = None
        
        # 初始化健康检查器变量
        self.health_checker = None
        self._core_instance = None
        self._core_scheduler_available = False
        self._local_scheduler_running = False
        
        # 托盘图标初始化标志，防止重复初始化
        self._tray_initialized = False
        
        # 进行所有设置和组件创建
        self.setup_window()
        self.create_widgets()
        self.load_settings()
        self.setup_tray_icon()
        
        # 注册GUI日志处理器的回调函数
        from logger_config import gui_log_handler
        gui_log_handler.set_gui_callback(self.add_status_message)
        

        
        # 显示初始消息
        self.root.after(400, self.show_initial_messages)
        
        # 应用启动时自动设置定时打卡任务
        self.root.after(1000, self.schedule_auto_checkin)

    def setup_window(self):
        """设置主窗口、协议和位置"""
        self.root.title("健康打卡助手 v5.1 👾实现每日定时打卡")
        self.root.geometry("550x600")
        self.root.resizable(True, True)
        
        # 设置窗口协议，处理关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        # 添加最小化到托盘的事件绑定
        self.root.bind("<Unmap>", self.on_window_minimized)
        
        # 启用窗口属性处理（适用于Linux环境下的窗口管理器）
        if sys.platform.startswith('linux'):
            try:
                self.root.attributes('-type', 'normal')
            except Exception as e:
                info(f"设置窗口属性失败（Linux）: {str(e)}")
        
        # 窗口居中
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")





    def setup_tray_icon(self):
        """设置系统托盘图标，防止重复初始化"""
        # 检查是否已初始化过托盘图标
        if hasattr(self, '_tray_initialized') and self._tray_initialized:
            info("托盘图标已初始化，跳过重复初始化")
            return
            
        if not TRAY_AVAILABLE:
            error ( "系统托盘功能不可用，请安装 pystray 和 pillow 库" )
            self.add_status_message ( "⚠️ 系统托盘功能不可用，请安装 pystray 和 pillow 库" )
            return

        try:
            # 创建托盘图标
            self.create_tray_icon ()
            # 标记托盘图标已初始化
            self._tray_initialized = True
        except Exception as e:
            error(f"创建托盘图标失败: {str(e)}")
            self.add_status_message(f"⚠️ 创建托盘图标失败: {str(e)}")


    def create_tray_icon(self):
        """创建系统托盘图标，防止重复创建"""
        # 检查是否已存在托盘图标，如果存在则停止旧图标
        if hasattr(self, 'tray_icon') and self.tray_icon:
            try:
                self.tray_icon.stop()
                info("已停止旧的托盘图标")
            except Exception as e:
                warning(f"停止旧托盘图标时出错: {e}")
            # 将托盘图标引用设为None，确保彻底清理
            self.tray_icon = None
        
        # 创建表情符号图标图像
        icon_image = self.create_icon_image ()

        # 创建托盘菜单（使用中文提高用户体验）
        menu = pystray.Menu (
            pystray.MenuItem ( "显示窗口", self.show_window ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem ( "退出程序", self.quit_from_tray )
        )

        # 创建托盘图标，使用中文名称提高辨识度
        self.tray_icon = pystray.Icon (
            "HealthCheck",
            icon_image,
            "健康打卡助手 v5.1 👾 实现每日定时打卡",
            menu
        )

        # 优化托盘图标配置，确保在不同主题下的显示效果
        # 设置图标大小和缩放选项
        self.tray_icon.icon_size = (32, 32)
        
        # 在新线程中运行托盘图标，捕获可能的错误
        def run_tray():
            try:
                self.tray_icon.run ()
            except Exception as e:
                # 托盘运行失败，记录但不抛出异常
                warning ( f"托盘图标运行失败: {e}" )

        tray_thread = threading.Thread ( target=run_tray, daemon=True )
        tray_thread.start ()

    def create_icon_image(self):
        """创建托盘图标图像"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(script_dir, 'alien.png')
        image = Image.open(image_path)
        image = image.resize((32, 32), Image.Resampling.LANCZOS)
        
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        info(f"成功加载托盘图标: {image_path}")
        return image



    def quit_from_tray(self, icon=None, item=None):
        """从托盘退出程序"""
        self.quit ()

    def on_window_minimized(self, event):
        """窗口最小化时的处理"""
        if str ( self.root.state () ) == "iconic":
            self.hide_to_tray ()

    def show_window(self):
        """显示窗口"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.add_status_message("🖥️ 主菜单已显示")

    def hide_to_tray(self):
        """隐藏窗口到系统托盘"""
        self.root.withdraw()
        if self.tray_icon:
            self.add_status_message("💤 程序已最小化到系统托盘，右键点击托盘图标可显示菜单")
        else:
            self.add_status_message("💤 程序已隐藏（托盘功能不可用）")

    def quit(self):
        """完全退出程序 - 资源优化版"""
        try:
            # 1. 设置运行标志为False，停止后台线程
            self._running = False
            
            # 2. 清除定时任务（快速操作）
            if hasattr(self, '_local_timer') and self._local_timer is not None:
                self._local_timer.cancel()
                self._local_timer = None
            
            # 3. 停止合并的线程（如果存在）
            for checker_attr in ['health_checker', '_core_instance']:
                if hasattr(self, checker_attr):
                    checker = getattr(self, checker_attr)
                    if checker and hasattr(checker, 'stop_combined_thread'):
                        try:
                            checker.stop_combined_thread()
                        except Exception:
                            pass  # 静默失败，继续清理其他资源
            
            # 4. 关闭窗口（优先级高）
            if self.root:
                try:
                    self.root.quit()
                    self.root.update_idletasks()  # 确保所有GUI事件都被处理
                except Exception:
                    pass
            
            # 5. 等待调度器线程终止，设置超时
            if hasattr(self, 'scheduler_thread') and self.scheduler_thread and self.scheduler_thread.is_alive():
                try:
                    self.scheduler_thread.join(timeout=0.5)
                except Exception:
                    pass
            
            # 6. 确保关闭浏览器实例（如果存在）
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                    self.driver = None
                except Exception:
                    pass
            
            # 7. 在独立线程中停止托盘图标，避免阻塞
            if self.tray_icon:
                try:
                    # 使用简单方式停止，避免创建额外线程
                    self.tray_icon.stop()
                except Exception:
                    pass
            
            # 8. 最后确保窗口被销毁
            if self.root:
                try:
                    self.root.destroy()
                except Exception:
                    pass
            
            # 9. 清理循环引用，帮助GC回收内存
            for attr in ['root', 'tray_icon', 'health_checker', '_core_instance', 'status_text']:
                if hasattr(self, attr):
                    setattr(self, attr, None)
                    
            info("程序已完全退出")
            
        except Exception as e:
            # 简化异常处理，只记录不打印详细堆栈
            error(f"退出程序时出错: {str(e)}")
            
        finally:
            # 强制终止进程，确保程序完全退出
            import sys
            sys.exit(0)

    def create_widgets(self):
        """创建界面组件"""
        # 创建主框架
        main_frame = ttk.Frame ( self.root, padding="10" )
        main_frame.pack ( fill=tk.BOTH, expand=True )

        # 创建顶部功能按钮（只有两个）
        self._create_function_buttons ( main_frame )

        # 创建功能页面容器
        self._create_function_pages ( main_frame )

        # 初始显示状态页面
        self._show_function ( 'status' )



    def _create_function_buttons(self, parent):
        """创建顶部功能按钮"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        # 配置按钮样式
        style = ttk.Style()
        style.configure('Function.TButton', font=('微软雅黑', 10))
        style.configure('Active.TButton', font=('微软雅黑', 10, 'bold'))

        # 创建按钮
        self.status_btn = ttk.Button(button_frame, text="状态",
                                       command=lambda: self._show_function('status'),
                                       style='Function.TButton')
        self.settings_btn = ttk.Button(button_frame, text="设置",
                                         command=lambda: self._show_function('settings'),
                                         style='Function.TButton')

        # 布局按钮
        self.status_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.settings_btn.pack(side=tk.LEFT)

        # 当前激活按钮
        self.current_button = None

    def _create_function_pages(self, parent):
        """创建功能页面"""
        # 状态页面
        self.status_page = ttk.Frame ( parent )
        self._create_status_page ( self.status_page )

        # 设置页面
        self.settings_page = ttk.Frame ( parent )
        self._create_settings_page ( self.settings_page )

        # 页面字典
        self.pages = {
            'status': self.status_page,
            'settings': self.settings_page
        }

    def _create_status_page(self, parent):
        """创建状态页面 - 简化版"""
        # 使用网格布局的主框架
        main_frame = ttk.Frame(parent, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧状态信息面板
        left_frame = ttk.LabelFrame(main_frame, text="基本信息", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 用户信息显示（紧凑布局）
        info_frame = ttk.Frame(left_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(info_frame, text="姓名: ").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.display_name_label = ttk.Label(info_frame, text="未设置", foreground='gray', width=15)
        self.display_name_label.grid(row=0, column=1, sticky=tk.W, pady=3)
        
        ttk.Label(info_frame, text="电话: ").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.display_phone_label = ttk.Label(info_frame, text="未设置", foreground='gray', width=15)
        self.display_phone_label.grid(row=1, column=1, sticky=tk.W, pady=3)
        
        ttk.Label(info_frame, text="单位: ").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.display_unit_label = ttk.Label(info_frame, text="未设置", foreground='gray', width=15)
        self.display_unit_label.grid(row=2, column=1, sticky=tk.W, pady=3)
        
        # 自动打卡信息（紧凑布局）
        auto_frame = ttk.Frame(left_frame)
        auto_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(auto_frame, text="自动打卡: ").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.auto_checkin_label = ttk.Label(auto_frame, text="关闭", foreground='red', width=8)
        self.auto_checkin_label.grid(row=0, column=1, sticky=tk.W, pady=3)
        
        ttk.Label(auto_frame, text="打卡时间: ").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.checkin_time_label = ttk.Label(auto_frame, text="10:30", foreground='blue', width=8)
        self.checkin_time_label.grid(row=1, column=1, sticky=tk.W, pady=3)
        
        ttk.Label(auto_frame, text="后台模式: ").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.headless_label = ttk.Label(auto_frame, text="开启", foreground='green', width=8)
        self.headless_label.grid(row=2, column=1, sticky=tk.W, pady=3)
        
        # 立即打卡按钮（突出显示）
        self.manual_checkin_btn = ttk.Button(left_frame, text="立即打卡",
                                              command=self.manual_checkin, style='Accent.TButton')
        self.manual_checkin_btn.pack(fill=tk.X, pady=(10, 0))
        
        # 右侧状态显示面板
        right_frame = ttk.LabelFrame(main_frame, text="运行日志", padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # 创建滚动文本框（高度调整为8行，更紧凑）
        self.status_text = tk.Text(right_frame, height=8, wrap=tk.WORD, font=('微软雅黑', 9))
        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=scrollbar.set)
        
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 初始显示信息（延迟到所有控件创建完成后）

    def _create_settings_page(self, parent):
        """创建设置页面"""
        # 使用Canvas和Scrollbar的滚动框架
        canvas = tk.Canvas ( parent, highlightthickness=0 )
        scrollbar = ttk.Scrollbar ( parent, orient="vertical", command=canvas.yview )
        scrollable_frame = ttk.Frame ( canvas, padding="5" )

        # 配置滚动
        scrollable_frame.bind ( 
            "<Configure>",
            lambda e: canvas.configure ( scrollregion=canvas.bbox ( "all" ) )
        )

        canvas.create_window ( (0, 0), window=scrollable_frame, anchor="nw" )
        canvas.configure ( yscrollcommand=scrollbar.set )
        
        # 布局滚动组件
        canvas.pack ( side=tk.LEFT, fill=tk.BOTH, expand=True )
        scrollbar.pack ( side=tk.RIGHT, fill=tk.Y )

        # 用户信息设置
        user_info_frame = ttk.LabelFrame ( scrollable_frame, text="用户信息", padding="10" )
        user_info_frame.pack ( fill=tk.X, pady=5, padx=5 )

        # 用户信息输入框（紧凑双列布局）
        user_grid_frame = ttk.Frame ( user_info_frame )
        user_grid_frame.pack ( fill=tk.X )

        ttk.Label ( user_grid_frame, text="姓名: ", width=8 ).grid ( row=0, column=0, sticky=tk.E, pady=3 )
        self.name_var = tk.StringVar ( value=self.config.get ( "user_info", {} ).get ( "name", "" ) )
        name_entry = ttk.Entry ( user_grid_frame, textvariable=self.name_var, width=20 )
        name_entry.grid ( row=0, column=1, sticky=tk.W, padx=5, pady=3 )

        ttk.Label ( user_grid_frame, text="电话: ", width=8 ).grid ( row=1, column=0, sticky=tk.E, pady=3 )
        self.phone_var = tk.StringVar ( value=self.config.get ( "user_info", {} ).get ( "phone", "" ) )
        phone_entry = ttk.Entry ( user_grid_frame, textvariable=self.phone_var, width=20 )
        phone_entry.grid ( row=1, column=1, sticky=tk.W, padx=5, pady=3 )
        
        # 添加电话号码输入验证
        def validate_phone(new_value):
            # 检查是否为数字且长度不超过11位
            if new_value == "":  # 允许空输入
                phone_entry.configure(foreground="black", style="")
                return True
            elif new_value.isdigit() and len(new_value) <= 11:
                # 根据输入长度提供视觉反馈
                if len(new_value) == 11:
                    # 11位数字时显示为绿色，表示输入正确
                    phone_entry.configure(foreground="green", style="")
                else:
                    # 少于11位数字时显示为黑色
                    phone_entry.configure(foreground="black", style="")
                return True
            else:
                # 非数字或超过11位时不接受输入
                return False
        
        # 注册验证函数
        vcmd = (self.root.register(validate_phone), '%P')
        phone_entry.config(validate="key", validatecommand=vcmd)
        
        # 添加焦点离开时的验证和错误提示
        def on_phone_entry_leave(event):
            phone_value = self.phone_var.get()
            if phone_value and len(phone_value) != 11:
                # 输入了内容但不是11位数字时，显示错误提示
                messagebox.showwarning("输入错误", "请输入有效的11位电话号码")
                phone_entry.configure(foreground="red", style="")
        
        phone_entry.bind("<FocusOut>", on_phone_entry_leave)

        ttk.Label ( user_grid_frame, text="单位: ", width=8 ).grid ( row=0, column=2, sticky=tk.E, pady=3 )
        self.unit_var = tk.StringVar ( value=self.config.get ( "user_info", {} ).get ( "unit", "" ) )
        unit_entry = ttk.Entry ( user_grid_frame, textvariable=self.unit_var, width=20 )
        unit_entry.grid ( row=0, column=3, sticky=tk.W, padx=5, pady=3 )

        ttk.Label ( user_grid_frame, text="体温: ", width=8 ).grid ( row=1, column=2, sticky=tk.E, pady=3 )
        self.temperature_var = tk.StringVar ( value=self.config.get ( "user_info", {} ).get ( "temperature", "36.5" ) )
        temp_entry = ttk.Entry ( user_grid_frame, textvariable=self.temperature_var, width=20 )
        temp_entry.grid ( row=1, column=3, sticky=tk.W, padx=5, pady=3 )

        # 自动打卡设置
        schedule_frame = ttk.LabelFrame ( scrollable_frame, text="打卡设置", padding="10" )
        schedule_frame.pack ( fill=tk.X, pady=5, padx=5 )

        schedule_grid_frame = ttk.Frame ( schedule_frame )
        schedule_grid_frame.pack ( fill=tk.X )

        # 显示自动打卡状态提示（始终启用）
        ttk.Label ( schedule_grid_frame, text="自动打卡: ", width=10 ).grid ( row=0, column=0, sticky=tk.W, pady=3 )
        ttk.Label ( schedule_grid_frame, text="已启用", foreground="green" ).grid ( row=0, column=1, sticky=tk.W, padx=5, pady=3 )

        # 打卡时间设置
        ttk.Label ( schedule_grid_frame, text="打卡时间: ", width=10 ).grid ( row=1, column=0, sticky=tk.W, pady=3 )
        time_frame = ttk.Frame ( schedule_grid_frame )
        time_frame.grid ( row=1, column=1, sticky=tk.W, padx=5, pady=3 )

        self.hour_var = tk.IntVar ( value=self.config.get ( "schedule", {} ).get ( "hour", 10 ) )
        hour_spinbox = ttk.Spinbox ( time_frame, from_=0, to=23, textvariable=self.hour_var, width=4 )
        hour_spinbox.pack ( side=tk.LEFT )
        ttk.Label ( time_frame, text=" : " ).pack ( side=tk.LEFT, padx=2 )

        self.minute_var = tk.IntVar ( value=self.config.get ( "schedule", {} ).get ( "minute", 30 ) )
        minute_spinbox = ttk.Spinbox ( time_frame, from_=0, to=59, textvariable=self.minute_var, width=4 )
        minute_spinbox.pack ( side=tk.LEFT )

        # 浏览器设置（Windows专用 - 仅支持EDGE浏览器）
        browser_frame = ttk.LabelFrame ( scrollable_frame, text="浏览器设置", padding="10" )
        browser_frame.pack ( fill=tk.X, pady=5, padx=5 )

        browser_grid_frame = ttk.Frame ( browser_frame )
        browser_grid_frame.pack ( fill=tk.X )

        self.headless_var = tk.BooleanVar ( value=self.config.get ( "browser", {} ).get ( "headless", True ) )
        headless_check = ttk.Checkbutton ( browser_grid_frame, text="后台运行模式",
                                           variable=self.headless_var )
        headless_check.grid ( row=0, column=0, sticky=tk.W, padx=5, pady=3 )
        
        # Windows系统EDGE浏览器提示
        edge_label_frame = ttk.Frame(browser_frame)
        edge_label_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(edge_label_frame, text="Windows系统下仅支持Microsoft Edge浏览器", 
                 foreground="blue", font=('微软雅黑', 9)).grid(row=1, column=0, sticky=tk.W, padx=5)

        # 操作按钮
        button_frame = ttk.Frame ( scrollable_frame )
        button_frame.pack ( fill=tk.X, pady=10, padx=5 )

        self.save_settings_btn = ttk.Button ( button_frame, text="保存设置", 
                                             command=self.save_settings,
                                             style='Accent.TButton' )
        self.save_settings_btn.pack ( fill=tk.X )

        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            canvas.yview_scroll ( int ( -1 * (event.delta / 120) ), "units" )

        canvas.bind_all ( "<MouseWheel>", _on_mousewheel )

    def _show_function(self, function_name):
        """显示指定功能页面"""
        # 隐藏所有页面
        for page in self.pages.values():
            page.pack_forget()

        # 显示指定页面
        self.pages[function_name].pack(fill=tk.BOTH, expand=True)
        self.current_button = function_name

        # 更新按钮样式并添加状态消息
        if function_name == 'status':
            self.status_btn.configure(style='Active.TButton')
            self.settings_btn.configure(style='Function.TButton')
            self.add_status_message("📊 正在显示状态界面")
        elif function_name == 'settings':
            self.settings_btn.configure(style='Active.TButton')
            self.status_btn.configure(style='Function.TButton')
            self.add_status_message("⚙️ 正在显示设置界面")

    def show_initial_messages(self):
        """显示初始消息（Windows系统专用）"""
        self.add_status_message ( "✅ 健康打卡助手系统托盘版已启动" )
        if TRAY_AVAILABLE:
            self.add_status_message ( "📋 程序将在后台运行，点击关闭按钮可最小化到托盘" )
            self.add_status_message ( "🖱️ 右键点击托盘图标可显示主菜单或退出程序" )
        else:
            self.add_status_message ( "⚠️ 系统托盘功能不可用，请安装 pystray 和 pillow 库" )
            self.add_status_message ( "📋 点击关闭按钮将隐藏窗口，程序仍在后台运行" )
        # Windows系统和EDGE浏览器提示
        self.add_status_message ( "🖥️ Windows系统下仅支持Microsoft Edge浏览器" )

    def load_config(self):
        """加载配置文件 - 配置文件不存在时直接报错"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 
                return config
            else:
                error_msg = f"配置文件不存在: {self.config_file}\n请确保配置文件存在于程序目录中"
                # 延迟显示错误消息 - 确保在 GUI 完全初始化后
                self.root.after(300, lambda: self.add_status_message(f"❌ {error_msg}"))
                error(error_msg)
                raise FileNotFoundError(error_msg)
        except FileNotFoundError:
            # 直接重新抛出，不创建默认配置
            raise
        except Exception as e:
            error_msg = f"加载配置文件失败: {e}"
            # 延迟显示错误消息 - 确保在 GUI 完全初始化后
            self.root.after(300, lambda: self.add_status_message(f"❌ {error_msg}"))
            error(error_msg)
            raise

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            self.add_status_message ( f"❌ 保存配置文件失败: {e}" )
            error ( f"保存配置文件失败: {e}" )
            return False

    def add_status_message(self, message):
        """添加状态消息到显示框 - 优化版"""
        if not self.status_text:
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"

        # 使用更高效的方式插入文本
        self.status_text.insert(tk.END, full_message)
        self.status_text.see(tk.END)

        # 优化历史记录清理 - 减少到50行以节省内存
        # 直接计算行数而不分割整个文本
        line_count = int(self.status_text.index('end-1c').split('.')[0])
        if line_count > 50:
            self.status_text.delete("1.0", f"{line_count-50}.0")

    def manual_checkin(self):
        """立即打卡一次 - 调用真实的核心代码"""

        def checkin_thread():
            try:
                self.add_status_message ( "🚀 开始执行健康打卡..." )
                self.manual_checkin_btn.configure ( state='disabled' )

                # 调用核心代码的真实打卡功能
                success, message = self.real_checkin ()

                if success:
                    self.add_status_message ( f"✅ {message}" )
                else:
                    self.add_status_message ( f"❌ {message}" )

            except Exception as e:
                self.add_status_message ( f"❌ 打卡出错: {str ( e )}" )
            finally:
                self.manual_checkin_btn.configure ( state='normal' )

        # 在新线程中执行打卡
        thread = threading.Thread ( target=checkin_thread )
        thread.daemon = True
        thread.start ()


    
    def real_checkin(self):
        """Windows系统下使用核心模块执行打卡（仅支持EDGE浏览器）"""
        try:
            # Windows系统下的延迟导入
            from health_check_core import HealthCheckAutomation
            
            # 使用单例模式获取核心实例（Windows专用配置）
            self._core_instance = HealthCheckAutomation.get_instance()
            self._core_scheduler_available = True
            self.add_status_message("✅ 健康检查核心已初始化并保持活动状态")
            self.add_status_message("🔧 Windows环境下配置EDGE浏览器驱动")

            # 检查并同步调度设置
            if hasattr(self._core_instance, 'schedule_config') and self.config.get('schedule', {}).get('enabled', True):
                # 同步GUI的调度设置到核心模块
                self._core_instance.schedule_config = self.config['schedule']
                # 如果核心模块调度器未启动，则启动它
                if hasattr(self._core_instance, 'start_combined_thread'):
                    self._core_instance.start_combined_thread()
                    self.add_status_message("🔄 核心调度器已启动，将处理自动打卡任务")
                    # 确保本地调度器停止，避免重复执行
                    if self._local_scheduler_running:
                        if hasattr(self, '_local_timer') and self._local_timer is not None:
                            self._local_timer.cancel()
                            self._local_timer = None
                        self._local_scheduler_running = False
                        info("已停止本地调度器，切换到核心调度器")
            
            # 确保使用最新的配置（重新加载配置文件）
            self._core_instance.load_or_create_config()
            self._core_instance.setup_automation()

            # 执行打卡
            success = self._core_instance.run_once()

            if success:
                # 获取用户信息显示成功消息
                user_info = self.config.get("user_info", {})
                name = user_info.get("name", "未设置")
                phone = user_info.get("phone", "未设置")
                unit = user_info.get("unit", "未设置")
                headless_mode = "开启" if self.config.get("browser", {}).get("headless", True) else "关闭"

                message = f"用户 {name} (手机: {phone}, 单位: {unit}) 打卡成功 - Headless模式: {headless_mode}"
                return True, message
            else:
                return False, "打卡失败，请检查网络连接和配置信息"

        except ImportError:
            self._core_scheduler_available = False
            return False, "核心模块导入失败，请确保 health_check_core.py 文件存在"
        except Exception as e:
            self._core_scheduler_available = False
            error(f"执行打卡时出错: {str(e)}")
            return False, f"执行过程中出错: {str(e)}"



    def update_status_display(self):
        """更新状态显示"""
        # 更新用户信息显示
        user_info = self.config.get ( "user_info", {} )
        self.display_name_label.configure ( text=user_info.get ( "name", "未设置" ), foreground='blue' )
        self.display_phone_label.configure ( text=user_info.get ( "phone", "未设置" ), foreground='blue' )
        self.display_unit_label.configure ( text=user_info.get ( "unit", "未设置" ), foreground='blue' )

        # 更新自动打卡信息
        schedule_config = self.config.get ( "schedule", {} )
        auto_enabled = schedule_config.get ( "enabled", False )
        if auto_enabled:
            self.auto_checkin_label.configure ( text="开启", foreground='green' )
        else:
            self.auto_checkin_label.configure ( text="关闭", foreground='red' )

        # 格式化显示打卡时间
        hour = schedule_config.get("hour", 10)
        minute = schedule_config.get("minute", 30)
        self.checkin_time_label.configure(text=f"{hour:02d}:{minute:02d}", foreground='blue')

        # 更新浏览器信息
        browser_config = self.config.get ( "browser", {} )
        headless = browser_config.get ( "headless", True )
        if headless:
            self.headless_label.configure ( text="开启", foreground='green' )
        else:
            self.headless_label.configure ( text="关闭", foreground='red' )

    def save_settings(self):
        """保存设置"""
        try:
            # 验证电话号码格式
            phone_value = self.phone_var.get()
            if phone_value and (not phone_value.isdigit() or len(phone_value) != 11):
                messagebox.showerror("输入错误", "请输入有效的11位电话号码")
                return
            
            # 更新配置
            if "user_info" not in self.config:
                self.config["user_info"] = {}
            if "schedule" not in self.config:
                self.config["schedule"] = {}
            if "browser" not in self.config:
                self.config["browser"] = {}

            # 用户信息
            self.config["user_info"]["name"] = self.name_var.get ()
            self.config["user_info"]["phone"] = phone_value
            self.config["user_info"]["unit"] = self.unit_var.get ()
            self.config["user_info"]["temperature"] = self.temperature_var.get ()

            # 打卡设置 - 自动打卡始终保持启用状态
            self.config["schedule"]["hour"] = self.hour_var.get ()
            self.config["schedule"]["minute"] = self.minute_var.get ()
            self.config["schedule"]["enabled"] = True  # 强制启用自动打卡

            # 浏览器设置
            self.config["browser"]["headless"] = self.headless_var.get ()

            if self.save_config():
                # 保存成功后重新读取配置文件
                self.config = self.load_config()
                self.add_status_message("✅ 设置已保存成功")
                messagebox.showinfo("成功", "所有设置已保存成功")
                self.update_status_display()

                # 重新设置定时任务（自动打卡始终启用）
                self.schedule_auto_checkin()
                self.add_status_message(f"🕒 自动打卡已设置为每天 {self.hour_var.get():02d}:{self.minute_var.get():02d}")
        except Exception as e:
            self.add_status_message ( f"❌ 保存设置失败: {str(e)}" )
            messagebox.showerror ( "错误", f"保存设置失败: {str(e)}" )


    def load_settings(self):
        """加载设置到界面"""
        try:
            # 从配置文件重新加载最新配置
            self.load_config()
            
            # 用户信息
            user_info = self.config.get ( "user_info", {} )
            self.name_var.set ( user_info.get ( "name", "" ) )
            self.phone_var.set ( user_info.get ( "phone", "" ) )
            self.unit_var.set ( user_info.get ( "unit", "" ) )
            self.temperature_var.set ( user_info.get ( "temperature", "36.5" ) )

            # 打卡设置
            schedule_config = self.config.get ( "schedule", {} )
            self.hour_var.set ( schedule_config.get ( "hour", 10 ) )
            self.minute_var.set ( schedule_config.get ( "minute", 30 ) )
            # 自动打卡始终启用，无需设置变量

            # 浏览器设置
            browser_config = self.config.get ( "browser", {} )
            self.headless_var.set ( browser_config.get ( "headless", True ) )

            # 更新状态显示
            self.update_status_display ()

    
            self.add_status_message("🕒 自动打卡功能已启用")
        except Exception as e:
            self.add_status_message(f"⚠️ 加载设置时出现问题: {str(e)}")
            warning(f"加载设置失败: {e}")

    def on_auto_enabled_changed(self):
        """自动打卡功能处理（始终启用）"""
        # 自动打卡功能始终启用，直接设置定时任务
        self.add_status_message ( "🕒 自动打卡已启用" )
        self.schedule_auto_checkin ()

        # 立即更新状态显示
        self.update_status_display ()

    def schedule_auto_checkin(self, hour=None, minute=None):
        """优化版统一调度机制 - 支持核心模块调度器共享和同步"""
        # 获取时间参数
        if hour is None:
            hour = self.hour_var.get()
        if minute is None:
            minute = self.minute_var.get()
            
        try:
            # 更新配置文件中的时间设置
            self._update_schedule_config(hour, minute)
            
            # 添加状态消息
            self.add_status_message(f"⏰ 自动打卡已设置为每天 {hour:02d}:{minute:02d}")
            
            # 检查核心实例是否存在且可用
            if self._core_instance and self._core_scheduler_available:
                # 同步最新的调度设置到核心实例
                self._core_instance.schedule_config = self.config['schedule']
                
                # 检查核心实例是否有running属性和start_combined_thread方法
                if hasattr(self._core_instance, 'running') and hasattr(self._core_instance, 'start_combined_thread'):
                    # 如果核心调度器未运行，则启动它
                    if not self._core_instance.running:
                        self._core_instance.start_combined_thread()
                        info(f"核心调度器已启动，设置时间：{hour:02d}:{minute:02d}")
                    else:
                        # 核心调度器已运行，它会自动检测配置变化
                        info(f"核心调度器已在运行，将使用新设置：{hour:02d}:{minute:02d}")
                
                # 确保本地调度器停止，避免重复执行
                if self._local_scheduler_running:
                    if hasattr(self, '_local_timer') and self._local_timer is not None:
                        self._local_timer.cancel()
                        self._local_timer = None
                    self._local_scheduler_running = False
                    info("已停止本地调度器，统一使用核心调度器")
            else:
                # 如果核心实例不存在或不可用，先尝试延迟创建核心实例
                try:
                    from health_check_core import HealthCheckAutomation
                    self._core_instance = HealthCheckAutomation.get_instance()
                    self._core_scheduler_available = True
                    
                    # 配置并启动核心调度器
                    self._core_instance.schedule_config = self.config['schedule']
                    if hasattr(self._core_instance, 'start_combined_thread'):
                        self._core_instance.start_combined_thread()
                        self.add_status_message("🔄 已启动核心调度器处理自动打卡")
                        self._local_scheduler_running = False
                        if hasattr(self, '_local_timer') and self._local_timer is not None:
                            self._local_timer.cancel()
                            self._local_timer = None
                except Exception as inner_e:
                    # 创建核心实例失败，回退到本地调度器
                    self._core_scheduler_available = False
                    info(f"无法创建核心调度器实例: {str(inner_e)}，回退到本地调度")
                    self._fallback_to_local_scheduler(hour, minute)
        except Exception as e:
            self.add_status_message(f"❌ 设置自动打卡时出错: {str(e)}")
            error(f"设置自动打卡时出错: {str(e)}")
            # 出错时回退到本地调度
            self._fallback_to_local_scheduler(hour, minute)
            
    def _update_schedule_config(self, hour, minute):
        """更新调度配置"""
        if "schedule" not in self.config:
            self.config["schedule"] = {}
        self.config["schedule"]["enabled"] = True
        self.config["schedule"]["hour"] = hour
        self.config["schedule"]["minute"] = minute
        self.save_config()
            
    def _fallback_to_local_scheduler(self, hour, minute):
        """回退到本地threading.Timer实现的辅助方法"""
        # 设置本地调度器运行标志
        self._local_scheduler_running = True
        
        # 创建本地定时器线程
        if not hasattr(self, '_local_timer') or self._local_timer is None:
            self._schedule_local_timer(hour, minute)
            self.add_status_message(f"📌 已回退到本地定时，设置每日 {hour:02d}:{minute:02d} 自动打卡")
            info(f"本地定时器已启用，打卡时间：{hour:02d}:{minute:02d}")
        else:
            # 更新现有定时器
            self._update_local_timer(hour, minute)
    
    def _schedule_local_timer(self, hour, minute):
        """设置本地threading.Timer"""
        # 计算下次执行时间
        now = datetime.now()
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target_time <= now:
            # 如果目标时间已过，设置为明天
            from datetime import timedelta
            target_time += timedelta(days=1)
        
        # 计算延迟时间
        delay = (target_time - now).total_seconds()
        
        # 创建并启动定时器
        self._local_timer = threading.Timer(delay, self._local_timer_callback)
        self._local_timer.daemon = True
        self._local_timer.start()
        
        # 保存当前设置的时间
        self._local_timer_hour = hour
        self._local_timer_minute = minute
    
    def _update_local_timer(self, hour, minute):
        """更新本地定时器"""
        # 取消现有定时器
        if hasattr(self, '_local_timer') and self._local_timer is not None:
            self._local_timer.cancel()
            self._local_timer = None
        
        # 设置新定时器
        self._schedule_local_timer(hour, minute)
    
    def _local_timer_callback(self):
        """本地定时器回调函数"""
        # 执行打卡任务
        self.scheduled_checkin()
        
        # 重新调度下一次执行
        if hasattr(self, '_local_timer_hour') and hasattr(self, '_local_timer_minute'):
            self._schedule_local_timer(self._local_timer_hour, self._local_timer_minute)



    def scheduled_checkin(self):
        """定时打卡任务"""
        # 在新线程中执行打卡，避免阻塞调度器
        thread = threading.Thread(target=self._scheduled_checkin_thread)
        thread.daemon = True
        thread.start()
        
    def _scheduled_checkin_thread(self):
        """定时打卡线程函数 - 支持核心模块共享实例"""
        self.add_status_message("⌛ 开始定时打卡任务...")
        
        try:
            # 检查是否有可用的核心实例
            if self._core_instance and self._core_scheduler_available:
                info("使用已初始化的核心实例执行定时打卡")
                # 确保配置是最新的
                self._core_instance.load_or_create_config()
                
            # 执行打卡（real_checkin方法中已实现延迟导入和核心实例共享）
            success, message = self.real_checkin()
            if success:
                self.add_status_message(f"✅ {message}")
                info(f"定时打卡成功: {message}")
            else:
                self.add_status_message(f"❌ {message}")
                error(f"定时打卡失败: {message}")
            
        except Exception as e:
            error_msg = f"定时打卡线程发生异常: {str(e)}"
            self.add_status_message(f"❌ {error_msg}")
            error(error_msg)
        finally:
            self.add_status_message("✅ 定时打卡任务已完成")



    def run(self):
        """运行应用 - 优化版统一调度机制
        
        智能调度管理：
        1. 优先使用核心模块的调度器（如果可用）
        2. 仅在必要时启动本地调度器线程
        3. 优化资源使用，避免重复的调度线程
        """

        # 记录当前使用的调度器类型
        if self._core_scheduler_available:
            info("应用启动 - 使用核心模块调度器")
        elif self._local_scheduler_running:
            info("应用启动 - 使用本地调度器")
        else:
            info("应用启动 - 等待用户操作或调度设置")
            # 注意：自动打卡任务在__init__方法中已设置，避免循环依赖

        # 本地调度线程已不再需要，因为我们使用threading.Timer

        # 启动GUI
        try:
            self.root.mainloop()
        finally:
            # 确保清理资源
            pass
if getattr(sys, 'frozen', False):
    # 在PyInstaller打包环境中 - 从可执行文件所在目录读取
    base_path = os.path.dirname(sys.executable)


