#!/usr/bin/env python3
"""
舱端专用秒表 - 全面警示版 (v1.5.1)
1. 增强：未检测到工具、停止、暂停录制时，全部统一为红黄交替闪烁提醒
2. 保留：CPU 阈值 2.0，持续 2 秒判定逻辑
3. 保留：右侧边距 5px 优化与右上角初始定位
"""

import sys
import os
import signal
import time
import math
import tempfile
import shutil
import psutil
from pathlib import Path

try:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import Gtk, Gdk, GLib, AppIndicator3, GdkPixbuf
    import cairo
    GTK_AVAILABLE = True
except ImportError as e:
    print(f"导入错误: {e}")
    GTK_AVAILABLE = False

class TransparentStopwatch:
    def __init__(self):
        if not GTK_AVAILABLE:
            sys.exit(1)
            
        self.is_running = False
        self.start_time = 0
        self.elapsed_time = 0
        self.font_size = 18
        self.icon_created = False
        self.user_icon_path = Path.home() / ".local" / "share" / "icons" / "cabin_stopwatch_samsung_clock.png"
        
        self.voko_status = "not_found"
        self.blink_status = False 
        
        # 录制判定缓冲变量
        self.high_load_start_time = None 
        
        self.apply_css()
        self.create_main_window()
        self.create_samsung_clock_icon()
        self.create_system_tray()
        
        # 计时刷新
        GLib.timeout_add(100, self.update_timer)
        # 颜色切换频率 (500ms)
        GLib.timeout_add(500, self.toggle_blink_color)
        
        self.update_display()

    def apply_css(self):
        provider = Gtk.CssProvider()
        css = b"""
            window { background-color: rgba(0,0,0,0); border: none; box-shadow: none; margin: 0; padding: 0; }
            label { margin: 0; padding-right: 5px; }
        """
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def create_main_window(self):
        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_title("舱端专用秒表")
        self.window.set_resizable(False)
        self.window.set_decorated(False)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_keep_above(True)
        self.window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        
        self.window.set_app_paintable(True)
        screen = self.window.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.window.set_visual(visual)
        
        self.window.connect("draw", self.on_draw)
        
        self.event_box = Gtk.EventBox()
        self.event_box.set_visible_window(False)
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        self.time_label = Gtk.Label()
        self.time_label.set_halign(Gtk.Align.END)
        vbox.pack_start(self.time_label, True, True, 0)
        
        self.status_label = Gtk.Label()
        self.status_label.set_halign(Gtk.Align.END)
        vbox.pack_start(self.status_label, True, True, 0)
        
        self.event_box.add(vbox)
        self.event_box.connect("button-press-event", self.on_time_click)
        self.window.add(self.event_box)
        
        self.dragging = False
        self.window.connect("button-press-event", self.on_window_press)
        self.window.connect("button-release-event", self.on_window_release)
        self.window.connect("motion-notify-event", self.on_window_motion)
        self.window.connect("destroy", self.quit_application)
        
        self.window.show_all()
        GLib.idle_add(self.stick_to_edge)

    def stick_to_edge(self):
        screen = self.window.get_screen()
        scr_width = screen.get_width()
        win_width = self.window.get_allocated_width()
        margin_x = 20
        margin_y = 20
        self.window.move(scr_width - win_width - margin_x, margin_y)
        return False

    def create_samsung_clock_icon(self):
        try:
            width, height = 64, 64
            radius = 28
            center_x, center_y = width // 2, height // 2
            surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
            ctx = cairo.Context(surface)
            ctx.set_source_rgba(0, 0, 0, 0)
            ctx.paint()
            ctx.arc(center_x, center_y, radius, 0, 2 * math.pi)
            pat = cairo.LinearGradient(0, 0, width, height)
            pat.add_color_stop_rgba(0, 0.95, 0.95, 0.95, 1)
            pat.add_color_stop_rgba(0.5, 1, 1, 1, 1)
            pat.add_color_stop_rgba(1, 0.9, 0.9, 0.9, 1)
            ctx.set_source(pat)
            ctx.fill()
            ctx.arc(center_x, center_y, radius, 0, 2 * math.pi)
            ctx.set_source_rgba(0.3, 0.3, 0.3, 0.8)
            ctx.set_line_width(1.5)
            ctx.stroke()
            for i in range(12):
                angle = (i * math.pi / 6) - math.pi / 2
                length, width_tick = (8, 2.5) if i % 3 == 0 else (5, 1.5)
                start_x = center_x + (radius - 3) * math.cos(angle)
                start_y = center_y + (radius - 3) * math.sin(angle)
                end_x = center_x + (radius - length - 3) * math.cos(angle)
                end_y = center_y + (radius - length - 3) * math.sin(angle)
                ctx.move_to(start_x, start_y)
                ctx.line_to(end_x, end_y)
                ctx.set_source_rgba(0.2, 0.2, 0.2, 1)
                ctx.set_line_width(width_tick)
                ctx.stroke()
            hour_angle = (10 * math.pi / 6) - math.pi / 2
            hour_length = radius * 0.45
            ctx.move_to(center_x, center_y)
            ctx.line_to(center_x + hour_length * math.cos(hour_angle), center_y + hour_length * math.sin(hour_angle))
            ctx.set_source_rgba(0.1, 0.1, 0.1, 1)
            ctx.set_line_width(3.5)
            ctx.stroke()
            minute_angle = (10 * math.pi / 30) - math.pi / 2
            minute_length = radius * 0.65
            ctx.move_to(center_x, center_y)
            ctx.line_to(center_x + minute_length * math.cos(minute_angle), center_y + minute_length * math.sin(minute_angle))
            ctx.set_source_rgba(0.1, 0.1, 0.1, 1)
            ctx.set_line_width(2.5)
            ctx.stroke()
            ctx.arc(center_x, center_y, 3.5, 0, 2 * math.pi)
            ctx.set_source_rgba(0.1, 0.1, 0.1, 1)
            ctx.fill()
            
            temp_dir = tempfile.gettempdir()
            self.temp_icon_path = os.path.join(temp_dir, "cabin_stopwatch_samsung_clock.png")
            surface.write_to_png(self.temp_icon_path)
            os.makedirs(self.user_icon_path.parent, exist_ok=True)
            shutil.copy2(self.temp_icon_path, str(self.user_icon_path))
            self.icon_created = True
        except Exception as e:
            print(f"图标生成失败: {e}")

    def create_system_tray(self):
        try:
            self.indicator = AppIndicator3.Indicator.new("cabin-stopwatch", self.temp_icon_path, AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self.create_tray_menu()
        except Exception as e:
            print(f"托盘错误: {e}")

    def create_tray_menu(self):
        menu = Gtk.Menu()
        version_item = Gtk.MenuItem(label="舱端专用秒表 v1.5.1")
        version_item.set_sensitive(False)
        menu.append(version_item)
        menu.append(Gtk.SeparatorMenuItem())
        
        self.start_item = Gtk.MenuItem(label="开始")
        self.start_item.connect("activate", self.start_timer)
        menu.append(self.start_item)
        
        self.pause_item = Gtk.MenuItem(label="暂停")
        self.pause_item.connect("activate", self.pause_timer)
        menu.append(self.pause_item)
        
        reset_item = Gtk.MenuItem(label="重置")
        reset_item.connect("activate", self.reset_timer)
        menu.append(reset_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        self.show_window_item = Gtk.MenuItem(label="显示窗口")
        self.show_window_item.connect("activate", self.show_window)
        menu.append(self.show_window_item)
        
        self.hide_window_item = Gtk.MenuItem(label="隐藏窗口")
        self.hide_window_item.connect("activate", self.hide_window)
        menu.append(self.hide_window_item)
        
        self.always_on_top_item = Gtk.CheckMenuItem(label="窗口置顶")
        self.always_on_top_item.set_active(True)
        self.always_on_top_item.connect("toggled", self.toggle_always_on_top)
        menu.append(self.always_on_top_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        exit_item = Gtk.MenuItem(label="退出程序")
        exit_item.connect("activate", self.quit_application)
        exit_item.get_child().set_markup('<span color="red">退出程序</span>')
        menu.append(exit_item)
        
        menu.show_all()
        self.indicator.set_menu(menu)
        self.update_tray_button_state()

    def update_tray_button_state(self):
        self.start_item.set_sensitive(not self.is_running)
        self.pause_item.set_sensitive(self.is_running)
        is_vis = self.window.get_visible()
        self.show_window_item.set_sensitive(not is_vis)
        self.hide_window_item.set_sensitive(is_vis)

    def start_timer(self, widget=None):
        if not self.is_running:
            self.is_running = True
            self.start_time = time.time() - self.elapsed_time if self.start_time != 0 else time.time()
            self.update_tray_button_state()

    def pause_timer(self, widget=None):
        if self.is_running:
            self.is_running = False
            self.elapsed_time = time.time() - self.start_time
            self.update_tray_button_state()

    def reset_timer(self, widget=None):
        self.is_running = False
        self.start_time = 0
        self.elapsed_time = 0
        self.update_tray_button_state()

    def show_window(self, widget=None):
        self.window.show_all()
        self.update_tray_button_state()

    def hide_window(self, widget=None):
        self.window.hide()
        self.update_tray_button_state()

    def toggle_always_on_top(self, widget):
        self.window.set_keep_above(widget.get_active())

    def check_voko_status(self):
        found = False
        for proc in psutil.process_iter(['name']):
            try:
                if "vokoscreen" in proc.info['name'].lower():
                    found = True
                    cpu = proc.cpu_percent(interval=None)
                    
                    if cpu > 2.0:
                        if self.high_load_start_time is None:
                            self.high_load_start_time = time.time()
                        
                        if time.time() - self.high_load_start_time >= 2:
                            self.voko_status = "recording"
                        else:
                            self.voko_status = "paused"
                    else:
                        self.high_load_start_time = None
                        self.voko_status = "paused"
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if not found:
            self.voko_status = "not_found"
            self.high_load_start_time = None

    def update_display(self):
        # 1. 秒表时间显示
        if self.is_running:
            time_color = "#00FF00"
            current_elapsed = time.time() - self.start_time
        else:
            time_color = "#FF0000"
            current_elapsed = self.elapsed_time
        
        time_str = self.format_time(current_elapsed)
        self.time_label.set_markup(f'<span font="Monospace Bold {self.font_size}" foreground="{time_color}">{time_str}</span>')

        # 2. 状态标签显示（红黄交替逻辑）
        warn_color = "#FF0000" if self.blink_status else "#FFFF00"
        
        if self.voko_status == "recording":
            self.status_label.set_markup('<span font="9" foreground="#00FF00">屏幕录制中</span>')
        elif self.voko_status == "paused":
            self.status_label.set_markup(f'<span font="9" foreground="{warn_color}">请检查录屏状态</span>')
        else:
            # 未检测到工具时也使用交替颜色
            self.status_label.set_markup(f'<span font="9" foreground="{warn_color}">录制工具未启动</span>')

    def update_timer(self):
        if int(time.time() * 10) % 10 == 0:
            self.check_voko_status()
        self.update_display()
        return True

    def toggle_blink_color(self):
        self.blink_status = not self.blink_status
        return True

    def on_window_press(self, widget, event):
        if event.button == 1:
            self.dragging = True
            x, y = widget.get_position()
            self.drag_start_x = event.x_root - x
            self.drag_start_y = event.y_root - y
            return True
        return False

    def on_window_release(self, widget, event):
        self.dragging = False
        return False

    def on_window_motion(self, widget, event):
        if self.dragging:
            widget.move(int(event.x_root - self.drag_start_x), int(event.y_root - self.drag_start_y))
        return False

    def on_draw(self, widget, cr):
        cr.set_source_rgba(0, 0, 0, 0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        return False

    def format_time(self, total_seconds):
        total_seconds = int(total_seconds)
        return f"{total_seconds // 3600:02d}:{(total_seconds % 3600) // 60:02d}:{total_seconds % 60:02d}"

    def on_time_click(self, widget, event):
        if event.button == 3:
            self.pause_timer() if self.is_running else self.start_timer()
            return True
        return False

    def quit_application(self, widget=None):
        Gtk.main_quit()
        sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    stopwatch = TransparentStopwatch()
    Gtk.main()
