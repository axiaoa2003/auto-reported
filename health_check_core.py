#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
健康打卡助手 - 核心功能模块（Windows专用）
实现按需加载机制，最小化资源占用，仅使用EDGE浏览器
使用threading.Timer替代schedule库实现轻量级任务调度
"""

import time
import json
import os
import sys
from datetime import datetime, timedelta
# 导入简化的日志配置模块
from logger_config import getLogger, INFO, debug, info, warning, error
import threading

# Selenium相关模块采用懒加载，仅在需要时导入
_selenium_imported = False
webdriver = None
By = None
WebDriverWait = None
EC = None
Options = None


def _import_selenium():
    """按需导入Selenium模块，仅在需要时才加载"""
    global _selenium_imported, webdriver, By, WebDriverWait, EC, Options
    if not _selenium_imported:
        info("正在加载Selenium模块...")
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.edge.options import Options
        _selenium_imported = True
        info("Selenium模块加载完成")


class HealthCheckAutomation:
    # 单例模式实现
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HealthCheckAutomation, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # 避免重复初始化
        if not hasattr(self, 'initialized'):
            # 仅进行最基本的初始化，不加载任何可能占用资源的组件
            self.setup_logging()
            self.scheduler_running = False
            self.combined_thread = None  # 合并调度和配置监控的线程
            
            # 配置文件监控相关变量
            self.config_last_modified = 0  # 配置文件最后修改时间
            self.config_check_interval = 30  # 优化：延长配置文件检查间隔至30秒
            self.running = False  # 整体运行状态
            
            # 轻量级调度器相关变量
            self.timer = None  # 定时器对象
            self.next_run_time = None  # 下次运行时间

            # 不自动加载配置和启动线程，等待显式调用
            # 只有在实际需要时才加载配置和启动功能
            
            self.initialized = True
    
    @classmethod
    def get_instance(cls):
        """获取单例实例的静态方法"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def setup_logging(self):
        """设置简化版日志系统"""
        # 获取日志记录器并设置基本配置
        self.logger = getLogger(__name__)
        self.logger.setLevel(INFO)

    def _get_config_path(self):
        """获取配置文件绝对路径 - 始终从可执行文件或脚本同目录读取"""
        if getattr(sys, 'frozen', False):
            # 在PyInstaller打包环境中 - 从可执行文件所在目录读取
            base_path = os.path.dirname(sys.executable)
        else:
            # 在开发环境中 - 从脚本所在目录读取
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        config_path = os.path.join(base_path, 'health_config.json')
        return config_path
            
    def load_or_create_config(self):
        """加载配置文件 - 配置文件不存在时直接报错"""
        config_file = self._get_config_path()
        if not os.path.exists(config_file):
            error_msg = f"配置文件不存在: {config_file}\n请确保配置文件存在于程序目录中"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        else:
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            # 记录配置文件的最后修改时间，用于配置监控
            self.config_last_modified = os.path.getmtime(config_file)
            
            # 移除重复的日志输出，配置加载成功信息将由GUI统一显示

    def save_config(self):
        """保存配置到文件"""
        # 使用_get_config_path方法获取配置文件路径，确保读取和保存使用同一个文件
        config_file = self._get_config_path()

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def setup_automation(self):
        """设置自动化参数 - 惰性初始化，仅在需要时调用"""
        # 确保配置文件已加载
        if not hasattr(self, 'config'):
            self.load_or_create_config()
        
        # 惰性设置自动化参数
        self.user_info = self.config.get("user_info", {})
        self.schedule_config = self.config.get("schedule", {})
        self.browser_config = self.config.get("browser", {})

    def setup_driver(self):
        """配置浏览器驱动"""
        # 按需导入Selenium模块
        _import_selenium()
        
        edge_options = Options()

        # 设置为无头模式（后台运行）
        if self.browser_config.get("headless", True):
            edge_options.add_argument('--headless')

        # 设置无头模式下的窗口大小（确保元素可见）
        edge_options.add_argument('--window-size=1280,800')  # 优化：使用较小的窗口尺寸

        # 设置位置权限
        edge_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.geolocation": 1,
            "profile.default_content_setting_values.notifications": 1,
        })

        # 性能优化配置 - 基础配置
        edge_options.add_argument('--disable-gpu')
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-blink-features=AutomationControlled')
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        
        # 高级性能优化配置 - 进一步减少资源占用
        edge_options.add_argument('--disable-features=site-per-process')  # 减少进程数量
        edge_options.add_argument('--disable-extensions')  # 禁用扩展
        edge_options.add_argument('--disable-background-networking')  # 禁用后台网络
        edge_options.add_argument('--disable-background-timer-throttling')  # 禁用后台计时器节流
        edge_options.add_argument('--disable-backgrounding-occluded-windows')  # 禁用后台窗口处理
        edge_options.add_argument('--disable-breakpad')  # 禁用崩溃报告
        edge_options.add_argument('--disable-client-side-phishing-detection')  # 禁用钓鱼检测
        edge_options.add_argument('--disable-component-update')  # 禁用组件更新
        edge_options.add_argument('--disable-features=IsolateOrigins,site-per-process')  # 减少隔离进程
        edge_options.add_argument('--disable-hang-monitor')  # 禁用挂起监控
        edge_options.add_argument('--disable-ipc-flooding-protection')  # 禁用IPC洪水保护
        edge_options.add_argument('--disable-prompt-on-repost')  # 禁用重新提交提示
        edge_options.add_argument('--disable-renderer-backgrounding')  # 禁用渲染器后台处理
        edge_options.add_argument('--disable-sync')  # 禁用同步功能
        edge_options.add_argument('--metrics-recording-only')  # 仅记录指标
        edge_options.add_argument('--no-first-run')  # 禁用首次运行
        edge_options.add_argument('--safebrowsing-disable-auto-update')  # 禁用安全浏览自动更新
        edge_options.add_argument('--disable-features=NetworkPrediction')  # 禁用网络预测，保留基本网络功能

        try:
            driver = webdriver.Edge(options=edge_options)

            # 执行命令允许地理位置
            driver.execute_cdp_cmd("Browser.grantPermissions", {
                "origin": "https://ding.cjfx.cn",
                "permissions": ["geolocation"]
            })

            # 设置模拟地理位置
            driver.execute_cdp_cmd("Emulation.setGeolocationOverride", {
                "latitude": 39.0238,
                "longitude": 88.1663,
                "accuracy": 100
            })

            # 优化：禁用图片加载以提高性能
            driver.execute_cdp_cmd("Page.setWebLifecycleState", {"state": "active"})
            driver.set_page_load_timeout(30)  # 优化：设置页面加载超时

            return driver
        except Exception as e:
            self.logger.error(f"浏览器驱动初始化失败: {e}")
            return None

    def wait_and_click_with_retry(self, driver, element, description, max_retries=2):
        """等待并点击元素，带重试机制"""
        # 确保Selenium模块已导入
        _import_selenium()
        
        for attempt in range(max_retries):
            try:
                # 优化：减少等待时间，使用更精确的等待条件
                WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable(element)
                )
                element.click()
                self.logger.debug(f"{description}")  # 优化：将普通操作改为debug级别日志
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.debug(f"{description}失败，第{attempt + 1}次重试")
                    # 优化：移除不必要的等待
                    continue
                else:
                    self.logger.error(f"{description}失败: {e}")
                    return False
        return False

    def find_and_click_element(self, driver, description, selectors, wait_time=5):
        """通用的元素查找和点击函数"""
        # 确保Selenium模块已导入
        _import_selenium()
        
        try:
            for selector_type, selector_value in selectors:
                try:
                    if selector_type == "xpath":
                        element = WebDriverWait(driver, wait_time).until(
                            EC.element_to_be_clickable((By.XPATH, selector_value))
                        )
                    elif selector_type == "css":
                        element = WebDriverWait(driver, wait_time).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector_value))
                        )

                    # 滚动到元素
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                    time.sleep(0.5)

                    # 使用带重试的点击函数
                    if self.wait_and_click_with_retry(driver, element, description):
                        return True

                except Exception:
                    continue

            self.logger.warning(f"未找到{description}元素")
            return False

        except Exception as e:
            self.logger.warning(f"{description}时遇到问题: {e}")
            return False

    def wait_and_fill(self, driver, xpath, text, description):
        """等待并填写输入框"""
        # 确保Selenium模块已导入
        _import_selenium()
        
        try:
            element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            element.clear()
            element.send_keys(text)
            self.logger.info(f"{description}: {text}")
            time.sleep(self.browser_config["wait_time"])
            return True
        except Exception as e:
            self.logger.warning(f"{description}失败: {e}")
            return False

    def handle_location_and_submit(self, driver):
        """处理地理位置获取和表单提交"""
        # 获取地理位置 - 优化：减少等待时间，使用显式等待
        location_success = self.find_and_click_element(driver, "点击获取地理位置", [
            ("xpath", "//span[contains(text(), '获取地理位置')]"),
            ("xpath", "//button[contains(., '获取地理位置')]"),
            ("xpath", "//div[contains(text(), '获取地理位置')]")
        ], wait_time=2)

        if location_success:
            self.logger.debug("等待位置获取完成...")
            # 优化：使用显式等待替代固定等待
            try:
                WebDriverWait(driver, 3).until(
                    EC.text_to_be_present_in_element((By.XPATH, "//*[contains(text(), '位置')]"), "已获取")
                )
            except:
                pass  # 如果等待超时，继续执行
        else:
            self.logger.warning("未能点击获取地理位置按钮，尝试继续提交...")

        # 提交表单 - 优化：减少等待时间
        submit_success = self.find_and_click_element(driver, "点击提交", [
            ("xpath", "//span[contains(text(), '提交')]"),
            ("xpath", "//button[contains(., '提交')]"),
            ("xpath", "//div[contains(text(), '提交')]")
        ], wait_time=2)

        if submit_success:
            self.logger.debug("等待提交完成...")
            # 优化：使用显式等待替代固定等待
            try:
                WebDriverWait(driver, 3).until(
                    EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "成功")
                )
            except:
                pass  # 如果等待超时，仍然检查结果
            self.check_submission_result(driver)
            return True
        else:
            self.logger.error("未能找到提交按钮")
            return False

    def check_submission_result(self, driver):
        """检查提交结果"""
        try:
            success_indicators = ["提交成功", "提交完成", "success", "成功"]
            page_source = driver.page_source.lower()

            if any(indicator in page_source for indicator in success_indicators):
                self.logger.info("健康打卡提交成功！")
            else:
                self.logger.info("表单提交操作完成")
        except Exception:
            self.logger.info("表单提交操作完成")

    def fill_health_form(self):
        """填写健康打卡表单"""
        self.logger.info("开始执行健康打卡...")
        driver = None

        try:
            # 优化：延迟创建driver直到真正需要时
            driver = self.setup_driver()
            if not driver:
                return False

            # 打开表单页面
            driver.get("https://ding.cjfx.cn/f/vo149oup")
            self.logger.debug("已打开表单页面")  # 优化：将普通操作改为debug级别日志

            # 等待页面加载 - 优化：使用更精确的等待条件和合理的超时时间
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '若羌县志愿者每日健康打卡')]"))
            )
            # 优化：移除不必要的固定等待

            # 填写表单 - 优化：合并输入操作，减少等待次数
            self.wait_and_fill(driver, "//input[@placeholder='请输入姓名']",
                             self.user_info["name"], "填写姓名")
            self.wait_and_fill(driver, "//input[@placeholder='请输入手机号']",
                             self.user_info["phone"], "填写手机号")
            self.wait_and_fill(driver, "//input[@placeholder='请输入内容']",
                             self.user_info["unit"], "填写服务单位")

            # 选择安全健康状况
            health_options = driver.find_elements(By.XPATH, "//span[contains(text(), '安全健康')]")
            if health_options:
                health_option = health_options[1] if len(health_options) > 1 else health_options[0]
                self.wait_and_click_with_retry(driver, health_option, "选择安全健康状况")
                # 优化：移除不必要的固定等待

            # 填写体温 - 优化：使用更精确的XPATH以直接定位体温输入框
            temp_input = driver.find_element(By.XPATH, "//*[contains(text(), '体温')]/following::input[@placeholder='请输入内容'][1]")
            if temp_input:
                temp_input.clear()
                temp_input.send_keys(self.user_info["temperature"])
                self.logger.debug(f"填写体温: {self.user_info['temperature']}")

            # 选择是否上班
            yes_buttons = driver.find_elements(By.XPATH, "//span[contains(text(), '是')]")
            if len(yes_buttons) > 1:
                self.wait_and_click_with_retry(driver, yes_buttons[1], "选择今日是否上班")

            # 选择有无离开
            no_buttons = driver.find_elements(By.XPATH, "//span[contains(text(), '无')]")
            if no_buttons and len(no_buttons) > 1:
                self.wait_and_click_with_retry(driver, no_buttons[1], "选择有无离开")

            # 处理地理位置和提交
            success = self.handle_location_and_submit(driver)
            return success

        except Exception as e:
            self.logger.error(f"执行过程中出错: {e}")
            if driver:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                driver.save_screenshot(f"error_{timestamp}.png")
            return False
        finally:
            # 确保浏览器被正确关闭并释放所有资源
            self._cleanup_resources(driver)
            # 主动删除大对象引用，帮助垃圾回收
            self._unload_non_essential_modules()
            
    def _cleanup_resources(self, driver=None):
        """增强的资源释放机制 - 确保所有占用的系统资源被彻底释放"""
        # 确保浏览器被正确关闭
        if driver:
            try:
                # 增强资源清理：清除所有数据
                driver.delete_all_cookies()
                
                # 使用CDP命令清理浏览器缓存和存储
                try:
                    # 清除浏览器缓存
                    driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                    # 清除所有来源的存储数据
                    driver.execute_cdp_cmd('Storage.clearDataForOrigin', {
                        'origin': '*',
                        'storageTypes': 'appcache,cache,indexeddb,localstorage,serviceworkers,websql'
                    })
                    # 清除网络缓存
                    driver.execute_cdp_cmd('Network.clearBrowserCookies', {})
                    self.logger.debug("浏览器缓存和存储数据已清除")
                except Exception as cdp_error:
                    # CDP命令失败不应阻止浏览器关闭
                    self.logger.warning(f"使用CDP命令清理浏览器数据时出错: {cdp_error}")
                
                # 关闭浏览器
                driver.quit()
                self.logger.info("浏览器已关闭，资源已释放")
                
                # 强制垃圾回收，帮助释放内存
                import gc
                gc.collect()
                
            except Exception as e:
                self.logger.error(f"关闭浏览器时发生错误: {str(e)}")
                
                # 即使出错也尝试垃圾回收
                try:
                    import gc
                    gc.collect()
                except:
                    pass
        
    def _unload_non_essential_modules(self):
        """卸载非必要模块，帮助垃圾回收"""
        import sys
        
        # 移除Selenium相关模块引用，帮助垃圾回收
        selenium_modules = ['selenium']
        for module_name in selenium_modules:
            if module_name in sys.modules:
                try:
                    # 记录日志但不抛出异常，避免在资源清理时出错
                    del sys.modules[module_name]
                    self.logger.debug(f"已移除模块: {module_name}")
                except:
                    pass
                    
        # 重置模块导入标志，允许下次重新导入
        global _selenium_imported
        _selenium_imported = False
        
        # 清空浏览器相关引用
        if hasattr(self, 'options'):
            delattr(self, 'options')
        
        # 清空非必要的配置引用，但保留基本配置
        if hasattr(self, 'user_info'):
            delattr(self, 'user_info')
        if hasattr(self, 'browser_config'):
            delattr(self, 'browser_config')

    # Windows专用：移除了命令行编辑配置功能，由GUI统一处理

    def run_once(self):
        """立即运行一次"""
        return self.fill_health_form()

    def combined_loop(self):
        """优化的合并调度循环，同时处理定时任务和配置文件监控，减少CPU占用"""
        self.logger.info("调度和配置监控线程已启动")
        
        # 安排首次任务执行
        self._schedule_next_run()
        
        last_config_check = time.time()
        
        while self.running:
            try:
                # 获取下次任务执行时间，实现智能睡眠
                next_run_delay = self._get_next_run_delay()
                
                # 如果有即将执行的任务，使用更短的睡眠时间
                if next_run_delay > 0 and next_run_delay <= 5:  # 5秒内有任务
                    time.sleep(0.5)  # 更频繁地检查
                elif next_run_delay > 0:
                    # 计算安全的睡眠时间，确保不超过配置检查间隔
                    safe_sleep_time = min(next_run_delay / 2, self.config_check_interval / 2, 30)
                    time.sleep(safe_sleep_time)
                else:
                    # 没有任务时使用配置检查间隔作为基准，但不超过30秒
                    time.sleep(min(self.config_check_interval, 30))
                
                # 定期检查配置文件变化
                current_time = time.time()
                if current_time - last_config_check >= self.config_check_interval:
                    self.check_config_changes()
                    last_config_check = current_time
                    
            except Exception as e:
                self.logger.error(f"调度循环中的错误: {str(e)}")
                # 简化错误处理，减少不必要的模块导入
                # 出错后短暂暂停再继续
                time.sleep(5)
                
    def _calculate_next_run_time(self):
        """计算下次运行时间"""
        if not self.schedule_config or not self.schedule_config.get("enabled", False):
            return None
            
        hour = self.schedule_config["hour"]
        minute = self.schedule_config["minute"]
        
        now = datetime.now()
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # 如果今天的时间已过，则设置为明天
        if now >= next_run:
            next_run += timedelta(days=1)
            
        # 转换为时间戳
        return next_run.timestamp()
    
    def _schedule_next_run(self):
        """安排下次任务执行"""
        # 先取消现有的定时器（如果有）
        if self.timer:
            self.timer.cancel()
            self.timer = None
            
        # 计算下次运行时间和延迟
        self.next_run_time = self._calculate_next_run_time()
        if not self.next_run_time:
            return
            
        delay = self._get_next_run_delay()
        
        # 记录日志
        now = datetime.now()
        next_run_dt = datetime.fromtimestamp(self.next_run_time)
        hours, remainder = divmod(int(delay), 3600)
        minutes, _ = divmod(remainder, 60)
        
        self.logger.info(f"定时任务已设置，下次执行时间: {next_run_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"距离下次执行还有: {hours}小时{minutes}分钟")
        
        # 创建新的定时器
        self.timer = threading.Timer(delay, self._timer_callback)
        self.timer.daemon = True
        self.timer.start()
    
    def _timer_callback(self):
        """定时器回调函数，执行任务并重新安排下次运行"""
        try:
            # 执行打卡任务
            self.fill_health_form()
        except Exception as e:
            self.logger.error(f"执行定时任务时出错: {str(e)}")
        finally:
            # 重新安排下次运行
            if self.running:
                self._schedule_next_run()
    
    def _get_next_run_delay(self):
        """获取距离下次任务执行的延迟时间（秒）"""
        if self.next_run_time:
            now = time.time()
            delay = self.next_run_time - now
            return max(0, delay)  # 确保不返回负值
        return -1  # 表示没有任务

    def start_combined_thread(self):
        """启动合并的调度和配置监控线程"""
        if not self.schedule_config["enabled"]:
            self.logger.info("定时任务未启用，请修改配置文件")
            return

        hour = self.schedule_config["hour"]
        minute = self.schedule_config["minute"]

        self.logger.info(f"定时任务已启动，每天 {hour:02d}:{minute:02d} 自动执行")

        # 启动合并的线程
        self.running = True
        self.combined_thread = threading.Thread(target=self.combined_loop)
        self.combined_thread.daemon = True
        self.combined_thread.start()

    def stop_combined_thread(self):
        """停止合并的线程并释放相关资源"""
        self.logger.info("准备停止调度和配置监控线程")
        
        # 设置运行标志为False，使线程能够自然退出
        if self.running:
            self.running = False
            # 取消定时器
            if self.timer:
                self.timer.cancel()
                self.timer = None
                self.next_run_time = None
            
            # 等待线程结束
            if self.combined_thread and self.combined_thread.is_alive():
                try:
                    self.combined_thread.join(timeout=5)  # 最多等待5秒
                    self.logger.info("调度和配置监控线程已停止")
                except Exception as e:
                    self.logger.error(f"等待线程停止时出错: {str(e)}")
            
            # 清空任务列表和重置标志
            self.scheduler_running = False
            
            # 释放资源
            self._unload_non_essential_modules()
            
            # 清理配置相关引用，但保留基本的配置修改时间信息
            if hasattr(self, 'config'):
                delattr(self, 'config')
            if hasattr(self, 'schedule_config'):
                delattr(self, 'schedule_config')
            
            self.logger.info("定时任务和配置监控已停止")

    def check_config_changes(self):
        """轻量级配置文件监控，仅在文件实际发生变化时才重新加载"""
        try:
            # 轻量级检查：首先检查文件是否存在
            config_path = self._get_config_path()
            if not os.path.exists(config_path):
                self.logger.warning("配置文件不存在: %s", config_path)
                return
            
            # 轻量级检查：仅检查修改时间，避免不必要的文件读取
            current_modified = os.path.getmtime(config_path)
            
            # 只有当文件确实被修改时，才执行完整的重新加载流程
            if current_modified > self.config_last_modified:
                # 配置文件已更改，记录日志
                self.logger.info("检测到配置文件已更改，正在重新加载...")
                
                try:
                    # 保存新的修改时间（先保存时间戳，避免在加载过程中被再次触发）
                    self.config_last_modified = current_modified
                    
                    # 重新加载配置文件
                    self.load_or_create_config()
                    
                    # 按需更新自动化参数
                    if hasattr(self, 'schedule_config') or hasattr(self, 'user_info'):
                        self.setup_automation()
                    
                    # 仅当调度器正在运行时才更新任务
                    if self.running and hasattr(self, 'schedule_config') and self.schedule_config["enabled"]:
                        # 重新安排定时任务
                        self._schedule_next_run()
                        hour = self.schedule_config["hour"]
                        minute = self.schedule_config["minute"]
                        self.logger.info(f"定时任务已更新，每天 {hour:02d}:{minute:02d} 自动执行")
                    
                    self.logger.info("配置文件已重新加载并应用")
                except Exception as e:
                    self.logger.error(f"重新加载配置文件时出错: {str(e)}")
                    # 记录详细的异常信息
                    # 简化错误处理，减少不必要的模块导入
                    # 不恢复修改时间戳，因为已经更新过了
                    # 下次检查时，如果文件未再次修改，则不会重复触发加载
        except Exception as e:
            self.logger.error(f"轻量级配置监控时出错: {str(e)}")
            # 配置监控错误不应中断主循环，记录错误后继续