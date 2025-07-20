#!/usr/bin/env python3
# OLED系统监控显示器 - SSD1306专用

import time
import datetime
import socket
import psutil
import os
import argparse
import configparser
import glob
import signal
import logging
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import ImageFont

# ===== 日志配置 =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/oled_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('OLEDMonitor')

# ===== 默认配置 =====
DEFAULT_CONFIG = {
    'i2c_port': 6,
    'i2c_address': 0x3C,
    'refresh_interval': 1,
    'network_interface': 'eth0',
    'font_path': 'NotoMono-Regular.ttf',
    'font_zh_path': 'wqy-microhei.ttc',
    'font_size': 10,
    'display_lines': 3,
    'cpu_temp_path': '/sys/class/thermal/thermal_zone0/temp',
    'cpu_freq_path': '/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq',
    'reset_interval': 3600,
    'horizontal_mirror': 0,   # 0:不翻转, 1:水平翻转
    'vertical_mirror': 1,     # 0:不翻转, 1:垂直翻转
    'x_offset': 0,            # X方向偏移量
    'y_offset': 0             # Y方向偏移量
}

# ===== SOC特定配置 =====
def detect_soc_temp_path():
    """自动检测SOC的温度传感器路径"""
    possible_paths = [
        '/sys/class/thermal/thermal_zone0/temp',
        '/sys/class/thermal/thermal_zone1/temp',
        '/sys/devices/virtual/thermal/thermal_zone0/temp'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

# ===== 配置管理 =====
def load_config():
    """加载配置（命令行参数 > 配置文件 > 默认值）"""
    parser = argparse.ArgumentParser(description='OLED系统监控显示器')
    
    # 添加命令行参数
    parser.add_argument('--config', type=str, default='/etc/oled_monitor.conf', 
                        help='配置文件路径 (默认: /etc/oled_monitor.conf)')
    parser.add_argument('--i2c-port', type=int, 
                        help=f'I2C端口 (默认: {DEFAULT_CONFIG["i2c_port"]})')
    parser.add_argument('--i2c-address', type=lambda x: int(x, 0), 
                        help=f'I2C地址 (十六进制，默认: 0x{DEFAULT_CONFIG["i2c_address"]:02X})')
    parser.add_argument('--refresh', type=int, 
                        help=f'刷新间隔(秒) (默认: {DEFAULT_CONFIG["refresh_interval"]})')
    parser.add_argument('--interface', type=str, 
                        help=f'网络接口 (默认: {DEFAULT_CONFIG["network_interface"]})')
    parser.add_argument('--font', type=str, 
                        help=f'字体文件路径 (默认: {DEFAULT_CONFIG["font_path"]})')
    parser.add_argument('--font_zh', type=str, 
                        help=f'中文字体文件路径 (默认: {DEFAULT_CONFIG["font_zh_path"]})')
    parser.add_argument('--font-size', type=int, 
                        help=f'字体大小 (默认: {DEFAULT_CONFIG["font_size"]})')
    parser.add_argument('--reset-interval', type=int, 
                        help=f'设备重置间隔(秒) (默认: {DEFAULT_CONFIG["reset_interval"]})')
    
    # 新增显示配置参数
    parser.add_argument('--horizontal-mirror', type=int, choices=[0, 1],
                        help=f'水平翻转 (0:不翻转, 1:翻转, 默认: {DEFAULT_CONFIG["horizontal_mirror"]})')
    parser.add_argument('--vertical-mirror', type=int, choices=[0, 1],
                        help=f'垂直翻转 (0:不翻转, 1:翻转, 默认: {DEFAULT_CONFIG["vertical_mirror"]})')
    parser.add_argument('--x-offset', type=int, 
                        help=f'X方向偏移量 (默认: {DEFAULT_CONFIG["x_offset"]})')
    parser.add_argument('--y-offset', type=int, 
                        help=f'Y方向偏移量 (默认: {DEFAULT_CONFIG["y_offset"]})')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 创建配置对象
    config = configparser.ConfigParser()
    config['DEFAULT'] = DEFAULT_CONFIG
    
    # 加载配置文件（如果存在）
    if os.path.exists(args.config):
        config.read(args.config)
        logger.info(f"从 {args.config} 加载配置文件")
    else:
        logger.warning(f"配置文件 {args.config} 不存在，使用默认配置")
    
    # 创建应用配置
    app_config = {}
    
    # 合并配置（命令行 > 配置文件 > 默认值）
    app_config['i2c_port'] = (
        args.i2c_port or
        config.getint('MONITOR', 'i2c_port', fallback=DEFAULT_CONFIG['i2c_port'])
    )
    
    # 获取原始字符串值（可能是十六进制或十进制字符串）
    i2c_address_str = config.get('MONITOR', 'i2c_address', fallback=str(DEFAULT_CONFIG['i2c_address']))
    
    # 转换十六进制或十进制字符串为整数
    try:
        if i2c_address_str.lower().startswith('0x'):
            i2c_address_val = int(i2c_address_str, 16)
        else:
            i2c_address_val = int(i2c_address_str)
    except ValueError:
        logger.error(f"无效的 I2C 地址格式: {i2c_address_str}，使用默认值 0x3C")
        i2c_address_val = 0x3C
    
    app_config['i2c_address'] = args.i2c_address or i2c_address_val

    app_config['refresh_interval'] = (
        args.refresh or
        config.getint('MONITOR', 'refresh_interval', fallback=DEFAULT_CONFIG['refresh_interval'])
    )
    
    app_config['network_interface'] = (
        args.interface or
        config.get('MONITOR', 'network_interface', fallback=DEFAULT_CONFIG['network_interface'])
    )
    
    app_config['font_path'] = (
        args.font or
        config.get('MONITOR', 'font_path', fallback=DEFAULT_CONFIG['font_path'])
    )
    
    app_config['font_zh_path'] = (
        args.font_zh or
        config.get('MONITOR', 'font_zh_path', fallback=DEFAULT_CONFIG['font_zh_path'])
    )
    
    app_config['font_size'] = (
        args.font_size or
        config.getint('MONITOR', 'font_size', fallback=DEFAULT_CONFIG['font_size'])
    )
    
    app_config['reset_interval'] = (
        args.reset_interval or
        config.getint('MONITOR', 'reset_interval', fallback=DEFAULT_CONFIG['reset_interval'])
    )
    
    # 新增显示配置
    app_config['horizontal_mirror'] = (
        args.horizontal_mirror if args.horizontal_mirror is not None else
        config.getint('DISPLAY', 'horizontal_mirror', fallback=DEFAULT_CONFIG['horizontal_mirror'])
    )
    
    app_config['vertical_mirror'] = (
        args.vertical_mirror if args.vertical_mirror is not None else
        config.getint('DISPLAY', 'vertical_mirror', fallback=DEFAULT_CONFIG['vertical_mirror'])
    )
    
    app_config['x_offset'] = (
        args.x_offset if args.x_offset is not None else
        config.getint('DISPLAY', 'x_offset', fallback=DEFAULT_CONFIG['x_offset'])
    )
    
    app_config['y_offset'] = (
        args.y_offset if args.y_offset is not None else
        config.getint('DISPLAY', 'y_offset', fallback=DEFAULT_CONFIG['y_offset'])
    )
    
    # SOC特定配置
    app_config['cpu_temp_path'] = detect_soc_temp_path() or config.get(
        'SOC', 'cpu_temp_path', fallback=DEFAULT_CONFIG['cpu_temp_path'])
    
    app_config['cpu_freq_path'] = config.get(
        'SOC', 'cpu_freq_path', fallback=DEFAULT_CONFIG['cpu_freq_path'])
    
    return app_config

# ===== 屏幕管理 =====
class OLEDManager:
    """OLED显示设备管理器"""
    
    def __init__(self, config):
        self.config = config
        self.device = None
        self.last_reset_time = time.time()
        self.init_display()
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def init_display(self):
        """初始化或重新初始化OLED显示设备"""
        try:
            if self.device:
                # 尝试清理现有设备
                try:
                    self.clear_screen()
                    self.device.cleanup()
                except Exception as e:
                    logger.warning(f"清理现有设备时出错: {e}")
                time.sleep(0.5)  # 给设备重置时间
                
            serial = i2c(port=self.config['i2c_port'], address=self.config['i2c_address'])
            self.device = ssd1306(serial, width=128, height=64)
            
            # 应用镜像设置 (使用配置值)
            hor_cmd = 0xA1 if self.config['horizontal_mirror'] else 0xA0
            ver_cmd = 0xC8 if self.config['vertical_mirror'] else 0xC0
            
            self.device.command(hor_cmd)  # 水平镜像
            self.device.command(ver_cmd)  # 垂直镜像
            
            # 应用边缘偏移 (使用配置值)
            self.device.command(0xD3)  # 设置显示偏移
            self.device.command(self.config['y_offset'])  # Y偏移值
            
            self.last_reset_time = time.time()
            logger.info(f"OLED显示器初始化成功 (I2C-{self.config['i2c_port']} @ 0x{self.config['i2c_address']:02X})")
            logger.info(f"显示设置: 水平镜像={self.config['horizontal_mirror']}, 垂直镜像={self.config['vertical_mirror']}, X偏移={self.config['x_offset']}, Y偏移={self.config['y_offset']}")
            return True
        except Exception as e:
            logger.error(f"显示器初始化失败: {e}")
            self.device = None
            return False
    
    def clear_screen(self):
        """清除屏幕内容"""
        if self.device:
            try:
                # 使用设备的内置方法清除屏幕
                self.device.hide()
                self.device.clear()
                logger.info("屏幕已清除")
            except Exception as e:
                logger.error(f"清除屏幕失败: {e}")
    
    def signal_handler(self, signum, frame):
        """处理终止信号"""
        logger.info(f"接收到信号 {signum}，准备退出...")
        self.cleanup()
        logger.info("资源已清理，程序退出")
        # 直接退出程序，不执行后续代码
        os._exit(0)
    
    def cleanup(self):
        """清理资源"""
        try:
            self.clear_screen()
        except Exception as e:
            logger.error(f"清理屏幕时出错: {e}")
        
        if self.device:
            try:
                self.device.cleanup()
            except Exception as e:
                logger.error(f"清理设备时出错: {e}")
            self.device = None
    
    def check_and_reset(self):
        """检查是否需要重置设备"""
        current_time = time.time()
        if current_time - self.last_reset_time > self.config['reset_interval']:
            logger.info("定期重置显示设备...")
            return self.init_display()
        return True
    
    def display_info(self, font, font_zh):
        """在OLED上显示三行信息（带异常处理）"""
        if not self.device or not self.check_and_reset():
            logger.error("显示设备不可用，尝试重新初始化...")
            if not self.init_display():
                return False
        
        try:
            with canvas(self.device) as draw:
                x_offset = self.config['x_offset']

                # 第1行: IP地址
                ip_address = get_ip_address(self.config['network_interface'])
                net_info = f"{self.config['network_interface']}:{ip_address}"
                draw.text((0 + x_offset, 16), net_info, font=font, fill="white")
                
                # 第2行: CPU温度及频率
                cpu_temp, cpu_freq = get_cpu_info(self.config)
                cpu_info = f"soc:{cpu_temp:.1f}°C"
                draw.text((0 + x_offset, 26), cpu_info, font=font, fill="white")
                cpu_info = f"{cpu_freq:.0f}MHz"
                draw.text((72 + x_offset, 26), cpu_info, font=font, fill="white")

                # 第3行: 当前时间
                time_str = get_current_time()
                draw.text((0 + x_offset, 36), time_str, font=font, fill="white")
                
            return True
        except Exception as e:
            logger.error(f"显示信息失败: {e}")
            # 尝试重置设备
            self.init_display()
            return False

# ===== 数据获取函数 =====
def get_current_time():
    """获取当前时间（精简格式）"""
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")

def get_ip_address(interface):
    """获取指定网络接口的IP地址"""
    try:
        # 获取网络接口信息
        addrs = psutil.net_if_addrs().get(interface, [])
        
        # 查找第一个IPv4地址
        for addr in addrs:
            if addr.family == socket.AF_INET:
                # 返回带前缀的完整IP地址
                return f"{addr.address}"
        
        return "ip:N/A"
    except Exception as e:
        logger.error(f"获取IP地址失败: {e}")
        return "ip:N/A"

def get_cpu_info(config):
    """获取SOC的CPU温度和频率"""
    try:
        # 获取CPU温度
        temp = 0.0
        if os.path.exists(config['cpu_temp_path']):
            with open(config['cpu_temp_path'], 'r') as f:
                temp = float(f.read().strip()) / 1000.0  # 转换为摄氏度
        else:
            logger.warning(f"温度传感器路径不存在: {config['cpu_temp_path']}")
        
        # 获取CPU频率
        freq = 0.0
        if os.path.exists(config['cpu_freq_path']):
            with open(config['cpu_freq_path'], 'r') as f:
                freq = float(f.read().strip()) / 1000.0  # 转换为MHz
        else:
            logger.warning(f"CPU频率路径不存在: {config['cpu_freq_path']}")
        
        return temp, freq
    except Exception as e:
        logger.error(f"获取CPU信息失败: {e}")
        return 0.0, 0.0

# ===== 主程序 =====
def main():
    # 加载配置
    config = load_config()
    
    logger.info("=== OLED监控器配置 ===")
    logger.info(f"I2C端口: {config['i2c_port']}")
    logger.info(f"I2C地址: 0x{config['i2c_address']:02X}")
    logger.info(f"刷新间隔: {config['refresh_interval']}秒")
    logger.info(f"设备重置间隔: {config['reset_interval']}秒")
    logger.info(f"网络接口: {config['network_interface']}")
    logger.info(f"字体: {config['font_path']} (大小: {config['font_size']}px)")
    logger.info(f"字体(中文): {config['font_zh_path']} (大小: {config['font_size']}px)")
    logger.info(f"CPU温度路径: {config['cpu_temp_path']}")
    logger.info(f"CPU频率路径: {config['cpu_freq_path']}")
    logger.info(f"水平镜像: {config['horizontal_mirror']}")
    logger.info(f"垂直镜像: {config['vertical_mirror']}")
    logger.info(f"X偏移: {config['x_offset']}")
    logger.info(f"Y偏移: {config['y_offset']}")
    
    # 检查网络接口是否存在
    if config['network_interface'] not in psutil.net_if_addrs():
        logger.warning(f"网络接口 '{config['network_interface']}' 不存在")
        logger.info("可用接口: %s", list(psutil.net_if_addrs().keys()))
        # 尝试使用第一个可用接口
        interfaces = list(psutil.net_if_addrs().keys())
        if interfaces:
            config['network_interface'] = interfaces[0]
            logger.info(f"使用接口: {config['network_interface']}")
        else:
            logger.error("没有可用的网络接口")
            exit(1)
    
    # 初始化显示管理器
    oled_manager = OLEDManager(config)
    
    # 加载字体
    try:
        font = ImageFont.truetype(config['font_path'], config['font_size'])
        font_zh = ImageFont.truetype(config['font_zh_path'], config['font_size'])
        logger.info("字体加载成功")
    except IOError as e:
        logger.warning(f"无法加载指定字体: {e}，使用默认字体")
        font = ImageFont.load_default()
        font_zh = ImageFont.load_default()
    
    logger.info("开始监控系统...")
    logger.info("按Ctrl+C退出程序...")
    
    # 看门狗计数器
    watchdog_counter = 0
    max_watchdog_errors = 10
    
    try:
        while True:
            start_time = time.time()
            
            # 显示信息
            if not oled_manager.display_info(font, font_zh):
                watchdog_counter += 1
                logger.error(f"显示失败 ({watchdog_counter}/{max_watchdog_errors})")
                
                # 如果连续失败次数过多，退出程序
                if watchdog_counter >= max_watchdog_errors:
                    logger.error("连续显示失败次数过多，程序将退出")
                    raise RuntimeError("显示设备持续失败")
            else:
                watchdog_counter = 0  # 重置计数器
            
            # 计算实际睡眠时间（保持精确的刷新间隔）
            elapsed = time.time() - start_time
            sleep_time = max(0, config['refresh_interval'] - elapsed)
            time.sleep(sleep_time)
            
    except (KeyboardInterrupt, SystemExit):
        logger.info("程序被用户中断")
    except Exception as e:
        logger.exception("程序发生未处理异常")
    finally:
        # 确保退出时清除屏幕
        logger.info("正在清理资源...")
        try:
            # 使用OLEDManager的清理方法
            oled_manager.cleanup()
        except Exception as e:
            logger.error(f"清理资源时出错: {e}")
        logger.info("资源已清理，程序退出")

if __name__ == "__main__":
    # 检查psutil是否安装
    try:
        import psutil
    except ImportError:
        print("错误: 需要安装psutil库")
        print("请运行: sudo pip3 install psutil")
        exit(1)
    
    # 提升进程优先级
    try:
        os.nice(10)  # 降低进程优先级
    except:
        pass
    
    main()
