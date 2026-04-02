import os

import cv2
import numpy as np
import mss
from win32 import win32gui

screenshot_debug_img = os.path.exists("screenshot")
aspect = 16 / 9


def capture_window(hwnd):
    """捕获窗口截图（使用MSS + DXGI），仅抓取客户区"""
    try:
        # title = win32gui.GetWindowText(hwnd)
        ## 获取窗口位置和尺寸
        # left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        # 获取窗口所在监视器的尺寸（兼容多屏）
        # monitor_info = win32api.GetMonitorInfo(win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST))
        # screen_left, screen_top, screen_right, screen_bottom = monitor_info["Monitor"]
        # screen_width = screen_right - screen_left
        # screen_height = screen_bottom - screen_top
        # 获取窗口客户区左上角相对于屏幕的坐标
        client_rect = win32gui.GetClientRect(hwnd)
        if client_rect == (0, 0, 0, 0):
            return None
        left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
        right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
        width = right - left
        height = bottom - top
        if width / height > aspect:
            width2 = int(height * aspect)
            left = int(left + (width - width2) / 2)
            width = width2
        else:
            height2 = int(width / aspect)
            top = int(top + (height - height2) / 2)
            height = height2
        # 在每次捕获时创建新的mss实例，避免线程问题
        sct = mss.mss()

        # 使用MSS截取客户区区域
        monitor = {"top": top, "left": left, "width": width, "height": height}
        screenshot = sct.grab(monitor)

        # 转换为numpy数组（BGRA格式）
        img0 = np.array(screenshot)
        screenshot = None
        # 转换BGRA到BGR
        img1 = cv2.cvtColor(img0, cv2.COLOR_BGRA2BGR)
        img0 = None
        # title_bar_height = GetSystemMetrics(win32con.SM_CYCAPTION) + 4
        # border_width = GetSystemMetrics(win32con.SM_CXSIZEFRAME) + 4
        # border_height = GetSystemMetrics(win32con.SM_CYSIZEFRAME) + 4

        # 保存调试图像
        if screenshot_debug_img:
            cv2.imwrite(f"screenshot/screenshot.png", img1)

        return img1

    except Exception as e:
        return None
