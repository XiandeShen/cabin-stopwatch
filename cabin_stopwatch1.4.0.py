#!/usr/bin/env python3
"""
舱端专用秒表
"""

import sys
import os
import signal
import time
import math
import tempfile
import shutil
from pathlib import Path

# 检查并设置 GTK 版本
try:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import Gtk, Gdk, GLib, AppIndicator3, GdkPixbuf
    import cairo
    GTK_AVAILABLE = True
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装必要的依赖：")
    print("sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-appindicator3-0.1")
    GTK_AVAILABLE = False

class TransparentStopwatch:
    def __init__(self):
        if not GTK_AVAILABLE:
            print("错误: 缺少必要的 GTK 库")
            sys.exit(1)
            
        # 秒表状态
        self.is_running = False
        self.start_time = 0
        self.elapsed_time = 0
        
        # 窗口位置记录
        self.window_position = (0, 0)
        
        # 字体大小设置（固定为18）
        self.font_size = 18
        
        # 图标相关
        self.icon_created = False
        
        # 图标路径
        self.user_icon_path = Path.home() / ".local" / "share" / "icons" / "cabin_stopwatch_samsung_clock.png"
        
        # 创建主窗口
        self.create_main_window()
        
        # 创建时钟图标
        self.create_samsung_clock_icon()
        
        # 创建系统托盘
        self.create_system_tray()
        
        # 开始更新时间（每100毫秒更新一次）
        GLib.timeout_add(10, self.update_timer)
        
        # 初始化时间显示
        self.update_display()
        
        print("舱端专用秒表已启动")
        print("操作说明:")
        print("  - 右键点击时间文本: 开始/暂停秒表")
        print("  - 左键拖动时间文本: 移动窗口")
        print("  - 点击托盘图标: 显示控制菜单")
        print("  - 运行中: 绿色文本")
        print("  - 停止时: 红色文本")
        print("  - 显示格式: 始终显示小时 (hh:mm:ss)")
        print(f"  - 图标路径: {self.user_icon_path}")
    
    def create_main_window(self):
        """创建透明主窗口"""
        try:
            self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
            self.window.set_title("舱端专用秒表")
            # 设置窗口大小为120x15，适合18号字体显示hh:mm:ss
            self.window.set_default_size(120, 15)
            self.window.set_resizable(False)  # 禁止调整窗口大小
            
            # 设置窗口为无边框和可移动
            self.window.set_decorated(False)
            
            # 关键设置：防止窗口在任务栏显示
            # 我们只在系统托盘中显示，不在Dock中显示窗口图标
            self.window.set_skip_taskbar_hint(True)
            self.window.set_skip_pager_hint(True)
            
            # 设置窗口始终保持在最上层
            self.window.set_keep_above(True)
            
            # 关键设置：使用UTILITY窗口类型，这通常不会在Dock中显示
            self.window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
            
            # 设置窗口透明
            self.window.set_app_paintable(True)
            screen = self.window.get_screen()
            visual = screen.get_rgba_visual()
            if visual:
                self.window.set_visual(visual)
            
            # 设置窗口背景为透明
            self.window.connect("draw", self.on_draw)
            
            # 创建时间显示区域
            self.event_box = Gtk.EventBox()
            self.event_box.set_visible_window(False)
            
            # 创建时间标签
            self.time_label = Gtk.Label()
            self.update_display()
            self.time_label.set_justify(Gtk.Justification.CENTER)
            
            # 初始为红色文本（停止状态）
            self.time_label.set_markup(f'<span font="Monospace Bold {self.font_size}" foreground="red">00:00:00</span>')
            
            # 将标签添加到EventBox
            self.event_box.add(self.time_label)
            
            # 设置EventBox只响应右键
            self.event_box.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            self.event_box.connect("button-press-event", self.on_time_click)
            
            # 添加EventBox到窗口
            self.window.add(self.event_box)
            
            # 窗口事件
            self.dragging = False
            self.drag_start_x = 0
            self.drag_start_y = 0
            
            # 窗口点击和拖动事件
            self.window.connect("button-press-event", self.on_window_press)
            self.window.connect("button-release-event", self.on_window_release)
            self.window.connect("motion-notify-event", self.on_window_motion)
            
            # 退出处理
            self.window.connect("destroy", self.quit_application)
            
            # 删除窗口最小化时隐藏的功能
            # self.window.connect("window-state-event", self.on_window_state)
            
            # 显示窗口
            self.window.show_all()
            
            # 移动到左上角
            self.window.move(self.window_position[0], self.window_position[1])
            
        except Exception as e:
            print(f"创建窗口时出错: {e}")
            sys.exit(1)
    
    def create_samsung_clock_icon(self):
        """创建手机UI风格的时钟图标"""
        try:
            # 创建时钟图标
            width, height = 64, 64
            radius = 28  # 时钟半径
            center_x, center_y = width // 2, height // 2
            
            # 使用Cairo创建图像
            surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
            ctx = cairo.Context(surface)
            
            # 透明背景
            ctx.set_source_rgba(0, 0, 0, 0)
            ctx.paint()
            
            # 绘制白色圆形背景
            ctx.arc(center_x, center_y, radius, 0, 2 * math.pi)
            
            # 风格的渐变背景（浅灰色到白色）
            pat = cairo.LinearGradient(0, 0, width, height)
            pat.add_color_stop_rgba(0, 0.95, 0.95, 0.95, 1)  # 浅灰
            pat.add_color_stop_rgba(0.5, 1, 1, 1, 1)  # 白
            pat.add_color_stop_rgba(1, 0.9, 0.9, 0.9, 1)  # 浅灰
            ctx.set_source(pat)
            ctx.fill()
            
            # 绘制深灰色边框
            ctx.arc(center_x, center_y, radius, 0, 2 * math.pi)
            ctx.set_source_rgba(0.3, 0.3, 0.3, 0.8)
            ctx.set_line_width(1.5)
            ctx.stroke()
            
            # 绘制时钟刻度
            for i in range(12):
                angle = (i * math.pi / 6) - math.pi / 2
                # 小时刻度
                if i % 3 == 0:
                    length = 8
                    width = 2.5
                else:
                    length = 5
                    width = 1.5
                
                start_x = center_x + (radius - 3) * math.cos(angle)
                start_y = center_y + (radius - 3) * math.sin(angle)
                end_x = center_x + (radius - length - 3) * math.cos(angle)
                end_y = center_y + (radius - length - 3) * math.sin(angle)
                
                ctx.move_to(start_x, start_y)
                ctx.line_to(end_x, end_y)
                ctx.set_source_rgba(0.2, 0.2, 0.2, 1)
                ctx.set_line_width(width)
                ctx.stroke()
            
            # 绘制时针（指向10点位置）
            hour_angle = (10 * math.pi / 6) - math.pi / 2  # 10点位置
            hour_length = radius * 0.45
            ctx.move_to(center_x, center_y)
            ctx.line_to(
                center_x + hour_length * math.cos(hour_angle),
                center_y + hour_length * math.sin(hour_angle)
            )
            ctx.set_source_rgba(0.1, 0.1, 0.1, 1)
            ctx.set_line_width(3.5)
            ctx.stroke()
            
            # 绘制分针（指向10分钟位置）
            minute_angle = (10 * math.pi / 30) - math.pi / 2  # 10分钟位置
            minute_length = radius * 0.65
            ctx.move_to(center_x, center_y)
            ctx.line_to(
                center_x + minute_length * math.cos(minute_angle),
                center_y + minute_length * math.sin(minute_angle)
            )
            ctx.set_source_rgba(0.1, 0.1, 0.1, 1)
            ctx.set_line_width(2.5)
            ctx.stroke()
            
            # 绘制中心圆点
            ctx.arc(center_x, center_y, 3.5, 0, 2 * math.pi)
            ctx.set_source_rgba(0.1, 0.1, 0.1, 1)
            ctx.fill()
            
            # 保存为PNG
            temp_dir = tempfile.gettempdir()
            self.temp_icon_path = os.path.join(temp_dir, "cabin_stopwatch_samsung_clock.png")
            surface.write_to_png(self.temp_icon_path)
            
            # 同时保存一份到用户目录，用于桌面快捷方式
            os.makedirs(self.user_icon_path.parent, exist_ok=True)
            shutil.copy2(self.temp_icon_path, str(self.user_icon_path))
            
            self.icon_created = True
            
        except Exception as e:
            print(f"创建图标时出错: {e}")
            # 使用简单的白色圆点作为备用
            self.create_fallback_icon()
    
    def create_fallback_icon(self):
        """创建备用图标（简单的白色圆点）"""
        try:
            width, height = 64, 64
            radius = 24
            center_x, center_y = width // 2, height // 2
            
            surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
            ctx = cairo.Context(surface)
            
            # 透明背景
            ctx.set_source_rgba(0, 0, 0, 0)
            ctx.paint()
            
            # 白色圆点
            ctx.arc(center_x, center_y, radius, 0, 2 * math.pi)
            ctx.set_source_rgba(1, 1, 1, 1)
            ctx.fill()
            
            temp_dir = tempfile.gettempdir()
            self.temp_icon_path = os.path.join(temp_dir, "cabin_stopwatch_tray_icon.png")
            surface.write_to_png(self.temp_icon_path)
            self.user_icon_path = Path.home() / ".local" / "share" / "icons" / "cabin_stopwatch_tray_icon.png"
            
        except Exception as e:
            print(f"创建备用图标时出错: {e}")
            self.temp_icon_path = "indicator-messages"
    
    def create_system_tray(self):
        """创建系统托盘"""
        try:
            # 创建应用指示器
            self.indicator = AppIndicator3.Indicator.new(
                "cabin-stopwatch",
                self.temp_icon_path,
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            
            # 创建托盘菜单
            self.create_tray_menu()
            
        except Exception as e:
            print(f"创建系统托盘时出错: {e}")
            # 如果系统托盘失败，程序仍然可以运行
    
    def create_tray_menu(self):
        """创建托盘菜单"""
        try:
            menu = Gtk.Menu()
            
            # 版本信息
            version_item = Gtk.MenuItem(label="舱端专用秒表 v1.4.0")
            version_item.set_sensitive(False)
            menu.append(version_item)
            
            # 分隔符
            separator1 = Gtk.SeparatorMenuItem()
            menu.append(separator1)
            
            # 开始按钮
            self.start_item = Gtk.MenuItem(label="开始")
            self.start_item.connect("activate", self.start_timer)
            menu.append(self.start_item)
            
            # 暂停按钮
            self.pause_item = Gtk.MenuItem(label="暂停")
            self.pause_item.connect("activate", self.pause_timer)
            menu.append(self.pause_item)
            
            # 重置按钮
            reset_item = Gtk.MenuItem(label="重置")
            reset_item.connect("activate", self.reset_timer)
            menu.append(reset_item)
            
            # 分隔符
            separator2 = Gtk.SeparatorMenuItem()
            menu.append(separator2)
            
            # 窗口控制选项放在主菜单中
            # 显示窗口按钮
            self.show_window_item = Gtk.MenuItem(label="显示窗口")
            self.show_window_item.connect("activate", self.show_window)
            menu.append(self.show_window_item)
            
            # 隐藏窗口按钮
            self.hide_window_item = Gtk.MenuItem(label="隐藏窗口")
            self.hide_window_item.connect("activate", self.hide_window)
            menu.append(self.hide_window_item)
            
            # 窗口置顶选项（放在主菜单中）
            self.always_on_top_item = Gtk.CheckMenuItem(label="窗口置顶")
            self.always_on_top_item.set_active(True)  # 默认选中
            self.always_on_top_item.connect("toggled", self.toggle_always_on_top)
            menu.append(self.always_on_top_item)
            
            # 分隔符
            separator3 = Gtk.SeparatorMenuItem()
            menu.append(separator3)
            
            # 退出按钮
            exit_item = Gtk.MenuItem(label="退出程序")
            exit_item.connect("activate", self.quit_application)
            exit_item.get_child().set_markup('<span color="red">退出程序</span>')
            menu.append(exit_item)
            
            menu.show_all()
            self.indicator.set_menu(menu)
            
            # 初始按钮状态
            self.update_tray_button_state()
            
        except Exception as e:
            print(f"创建托盘菜单时出错: {e}")
    
    def start_timer(self, widget=None):
        """开始计时"""
        if not self.is_running:
            self.is_running = True
            if self.start_time == 0:
                self.start_time = time.time()
            else:
                # 继续计时
                self.start_time = time.time() - self.elapsed_time
            
            # 更新显示
            self.update_display()
            # 更新托盘按钮状态
            self.update_tray_button_state()

    def pause_timer(self, widget=None):
        """暂停计时"""
        if self.is_running:
            self.is_running = False
            self.elapsed_time = time.time() - self.start_time
            
            # 更新显示
            self.update_display()
            # 更新托盘按钮状态
            self.update_tray_button_state()

    def show_window(self, widget=None):
        """显示窗口"""
        if not self.window.get_visible():
            self.window.show_all()
            self.window.move(self.window_position[0], self.window_position[1])
            # 确保窗口在顶层显示
            self.window.present()
            # 更新按钮状态
            self.update_tray_button_state()

    def hide_window(self, widget=None):
        """隐藏窗口"""
        if self.window.get_visible():
            # 隐藏窗口前保存当前位置
            x, y = self.window.get_position()
            self.window_position = (x, y)
            self.window.hide()
            # 更新按钮状态
            self.update_tray_button_state()

    def update_tray_button_state(self):
        """更新托盘菜单按钮状态"""
        try:
            # 更新秒表按钮状态
            if self.is_running:
                # 运行中：开始按钮禁用，暂停按钮可用
                self.start_item.set_sensitive(False)
                self.pause_item.set_sensitive(True)
            else:
                # 停止中：开始按钮可用，暂停按钮禁用
                self.start_item.set_sensitive(True)
                self.pause_item.set_sensitive(False)
            
            # 更新窗口按钮状态
            window_visible = self.window.get_visible()
            if window_visible:
                # 窗口可见：显示窗口按钮禁用，隐藏窗口按钮可用
                self.show_window_item.set_sensitive(False)
                self.hide_window_item.set_sensitive(True)
            else:
                # 窗口隐藏：显示窗口按钮可用，隐藏窗口按钮禁用
                self.show_window_item.set_sensitive(True)
                self.hide_window_item.set_sensitive(False)
                
        except Exception as e:
            print(f"更新托盘按钮状态时出错: {e}")
    
    def show_message(self, title, message):
        """显示消息对话框"""
        dialog = Gtk.MessageDialog(
            parent=self.window,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            title=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
    
    def show_question(self, title, message):
        """显示问题对话框"""
        dialog = Gtk.MessageDialog(
            parent=self.window,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            title=title
        )
        dialog.format_secondary_text(message)
        response = dialog.run()
        dialog.destroy()
        return response
    
    def on_draw(self, widget, cr):
        """绘制透明背景"""
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        return False
    
    def on_time_click(self, widget, event):
        """时间文本点击事件 - 右键开始/暂停秒表"""
        if event.button == 3:  # 右键
            if self.is_running:
                self.pause_timer()
            else:
                self.start_timer()
            return True
        return False
    
    def on_window_press(self, widget, event):
        """窗口按下事件 - 开始拖动"""
        if event.button == 1:  # 左键
            self.dragging = True
            # 获取窗口当前位置
            x, y = widget.get_position()
            # 记录鼠标相对窗口的位置
            self.drag_start_x = event.x_root - x
            self.drag_start_y = event.y_root - y
            return True
        return False
    
    def on_window_release(self, widget, event):
        """窗口释放事件 - 结束拖动"""
        if event.button == 1:  # 左键
            self.dragging = False
        return False
    
    def on_window_motion(self, widget, event):
        """窗口移动事件 - 处理拖动"""
        if self.dragging:
            # 计算新位置
            new_x = event.x_root - self.drag_start_x
            new_y = event.y_root - self.drag_start_y
            widget.move(int(new_x), int(new_y))
            # 更新保存的位置
            self.window_position = (int(new_x), int(new_y))
        return False
    
    def toggle_always_on_top(self, widget):
        """切换窗口置顶状态"""
        if widget.get_active():
            self.window.set_keep_above(True)
            print("窗口已置顶")
        else:
            self.window.set_keep_above(False)
            print("窗口取消置顶")
    
    def toggle_timer(self, widget=None):
        """切换秒表状态（开始/暂停）"""
        if not self.is_running:
            # 开始计时
            self.is_running = True
            if self.start_time == 0:
                self.start_time = time.time()
            else:
                # 继续计时
                self.start_time = time.time() - self.elapsed_time
        else:
            # 暂停计时
            self.is_running = False
            self.elapsed_time = time.time() - self.start_time
        
        # 更新显示
        self.update_display()
        # 更新托盘按钮状态
        self.update_tray_button_state()
    
    def reset_timer(self, widget=None):
        """重置秒表"""
        self.is_running = False
        self.start_time = 0
        self.elapsed_time = 0
        # 更新显示
        self.update_display()
        # 更新托盘按钮状态
        self.update_tray_button_state()
    
    def update_timer(self):
        """更新计时器显示 - 总是调用update_display，但只在运行时更新时间"""
        # 总是调用update_display，让它根据当前状态决定显示什么
        self.update_display()
        return True  # 继续定时器
    
    def format_time(self, total_seconds):
        """格式化时间显示，始终显示小时 (hh:mm:ss)"""
        total_seconds = int(total_seconds)  # 移除小数部分
        
        # 始终显示小时、分钟和秒
        hours = total_seconds // 3600
        remaining_seconds = total_seconds % 3600
        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def update_display(self):
        """更新时间显示，运行时绿色，停止时红色"""
        if self.is_running:
            current_elapsed = time.time() - self.start_time
            color = "#00FF00"  # 绿色
        else:
            current_elapsed = self.elapsed_time
            color = "#FF0000"  # 红色
        
        # 格式化时间
        time_str = self.format_time(current_elapsed)
        
        # 设置标签文本和颜色（使用固定的字体大小22）
        self.time_label.set_markup(f'<span font="Monospace Bold {self.font_size}" foreground="{color}">{time_str}</span>')
        
        # 强制刷新标签
        self.time_label.queue_draw()
    
    def toggle_window_visibility(self, widget=None):
        """切换窗口显示/隐藏，保持位置不变"""
        if self.window.get_visible():
            self.hide_window()
        else:
            self.show_window()
    
    def quit_application(self, widget=None):
        """退出应用程序"""
        # 清理临时图标文件
        try:
            if hasattr(self, 'temp_icon_path') and os.path.exists(self.temp_icon_path):
                os.remove(self.temp_icon_path)
        except:
            pass
        
        Gtk.main_quit()
        sys.exit(0)

def main():
    # 设置信号处理
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    try:
        # 创建秒表应用
        stopwatch = TransparentStopwatch()
        # 启动主循环
        Gtk.main()
    except Exception as e:
        print(f"程序运行出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # 检查是否安装了必要的库
    if not GTK_AVAILABLE:
        print("错误: 缺少必要的 GTK 库")
        print("请运行以下命令安装依赖：")
        print("sudo apt update")
        print("sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-appindicator3-0.1")
        print("pip3 install pycairo PyGObject")
        sys.exit(1)
    main()
