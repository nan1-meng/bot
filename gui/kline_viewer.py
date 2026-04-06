# 文件路径: gui/kline_viewer.py
import tkinter as tk
from tkinter import ttk
import math

class KlineViewer:
    def __init__(self, parent, title, kline_data, price_precision=6):
        """
        kline_data: 列表，每个元素为 [timestamp, open, high, low, close] 或字典格式
        """
        self.root = tk.Toplevel(parent)
        self.root.title(title)
        self.root.geometry("800x500")
        self.kline_data = kline_data
        self.price_precision = price_precision
        self.create_widgets()
        self.draw_kline()

    def create_widgets(self):
        self.canvas = tk.Canvas(self.root, bg='white', height=400, width=780)
        self.canvas.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        info_frame = ttk.Frame(self.root)
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        self.info_label = ttk.Label(info_frame, text="")
        self.info_label.pack(side=tk.LEFT)

        close_btn = ttk.Button(info_frame, text="关闭", command=self.root.destroy)
        close_btn.pack(side=tk.RIGHT)

    def draw_kline(self):
        if not self.kline_data or len(self.kline_data) < 2:
            self.info_label.config(text="K线数据不足，无法绘制")
            return

        # 计算价格范围
        prices = []
        for k in self.kline_data:
            prices.append(k[1])  # open
            prices.append(k[2])  # high
            prices.append(k[3])  # low
            prices.append(k[4])  # close
        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price
        if price_range == 0:
            price_range = 1

        # 画布尺寸
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width <= 1:
            width = 780
        if height <= 1:
            height = 400

        margin_left = 60
        margin_right = 20
        margin_top = 20
        margin_bottom = 40
        chart_width = width - margin_left - margin_right
        chart_height = height - margin_top - margin_bottom

        candle_width = chart_width / len(self.kline_data) * 0.6
        if candle_width < 2:
            candle_width = 2
        spacing = (chart_width / len(self.kline_data)) - candle_width
        if spacing < 0:
            spacing = 0

        # 绘制坐标轴
        self.canvas.create_line(margin_left, margin_top, margin_left, height - margin_bottom, fill='black')
        self.canvas.create_line(margin_left, height - margin_bottom, width - margin_right, height - margin_bottom, fill='black')

        # 绘制价格刻度
        for i in range(5):
            y = margin_top + (chart_height / 4) * i
            price = max_price - (price_range / 4) * i
            self.canvas.create_line(margin_left - 5, y, margin_left, y, fill='gray')
            self.canvas.create_text(margin_left - 10, y, text=f"{price:.{self.price_precision}f}", anchor='e', font=('Arial', 8))

        for idx, k in enumerate(self.kline_data):
            x = margin_left + idx * (candle_width + spacing) + candle_width / 2
            open_price = k[1]
            high_price = k[2]
            low_price = k[3]
            close_price = k[4]

            # 映射Y坐标
            def y_map(price):
                return margin_top + chart_height - ((price - min_price) / price_range) * chart_height

            y_open = y_map(open_price)
            y_high = y_map(high_price)
            y_low = y_map(low_price)
            y_close = y_map(close_price)

            # 绘制影线
            self.canvas.create_line(x, y_high, x, y_low, fill='black', width=1)

            # 绘制实体
            if close_price >= open_price:
                color = 'red'
                y_top = y_close
                y_bottom = y_open
            else:
                color = 'green'
                y_top = y_open
                y_bottom = y_close
            rect_height = abs(y_close - y_open)
            if rect_height < 1:
                rect_height = 1
            self.canvas.create_rectangle(x - candle_width/2, y_top, x + candle_width/2, y_bottom, fill=color, outline=color)

        # 显示基本信息
        first_time = self.kline_data[0][0]
        last_time = self.kline_data[-1][0]
        self.info_label.config(text=f"K线数量: {len(self.kline_data)}  时间范围: {first_time} - {last_time}")