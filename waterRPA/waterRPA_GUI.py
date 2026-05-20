import sys
import os
import time
import json
import pyautogui
import pyperclip
import traceback
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QLabel, QComboBox, QLineEdit, QScrollArea, 
                               QFileDialog, QTextEdit, QMessageBox, QFrame, QCheckBox)
from PySide6.QtCore import Qt, QThread, Signal

# 检查是否为 Mac 系统
IS_MAC = sys.platform == 'darwin'

# --------------------------
# 核心逻辑
# --------------------------

def mouseClick(clickTimes, lOrR, img, reTry, timeout=60):
    start_time = time.time()
    
    if reTry == 1:
        while True:
            if timeout and (time.time() - start_time > timeout):
                print(f"等待图片 {img} 超时 ({timeout}秒)")
                return 
            
            try:
                # 提示：如果在 Mac Retina 屏幕上点击位置偏移，可能需要将 location.x 和 location.y 除以 2
                location=pyautogui.locateCenterOnScreen(img,confidence=0.9)
                if location is not None:
                    # 如果你的 Mac 是视网膜屏幕且出现点击偏移，解除下面两行的注释并注释掉原点击代码：
                    # pyautogui.click(location.x / 2, location.y / 2, clicks=clickTimes, interval=0.2, duration=0.2, button=lOrR)
                    pyautogui.click(location.x, location.y, clicks=clickTimes, interval=0.2, duration=0.2, button=lOrR)
                    break
            except pyautogui.ImageNotFoundException:
                pass 
            
            print("未找到匹配图片,0.1秒后重试")
            time.sleep(0.1)
    elif reTry == -1:
        while True:
            if timeout and (time.time() - start_time > timeout):
                print(f"等待图片 {img} 超时 ({timeout}秒)")
                return 

            try:
                location=pyautogui.locateCenterOnScreen(img,confidence=0.9)
                if location is not None:
                    pyautogui.click(location.x, location.y, clicks=clickTimes, interval=0.2, duration=0.2, button=lOrR)
            except pyautogui.ImageNotFoundException:
                pass

            time.sleep(0.1)
    elif reTry > 1:
        i = 1
        while i < reTry + 1:
            if timeout and (time.time() - start_time > timeout):
                print(f"操作超时 ({timeout}秒)")
                return

            try:
                location=pyautogui.locateCenterOnScreen(img,confidence=0.9)
                if location is not None:
                    pyautogui.click(location.x, location.y, clicks=clickTimes, interval=0.2, duration=0.2, button=lOrR)
                    print("重复")
                    i += 1
            except pyautogui.ImageNotFoundException:
                pass
            
            time.sleep(0.1)

def mouseMove(img, reTry, timeout=60):
    start_time = time.time()
    while True:
        if timeout and (time.time() - start_time > timeout):
            print(f"等待图片 {img} 超时 ({timeout}秒)")
            return

        try:
            location = pyautogui.locateCenterOnScreen(img, confidence=0.9)
            if location is not None:
                pyautogui.moveTo(location.x, location.y, duration=0.2)
                break
        except pyautogui.ImageNotFoundException:
            pass

        print("未找到匹配图片,0.1秒后重试")
        time.sleep(0.1)
        if reTry == 1: 
            pass 

class RPAEngine:
    def __init__(self):
        self.is_running = False
        self.stop_requested = False

    def stop(self):
        self.stop_requested = True
        self.is_running = False

    def run_tasks(self, tasks, loop_forever=False, callback_msg=None):
        self.is_running = True
        self.stop_requested = False
        
        try:
            while True:
                for idx, task in enumerate(tasks):
                    if self.stop_requested:
                        if callback_msg: callback_msg("任务已停止")
                        return

                    cmd_type = task.get("type")
                    cmd_value = task.get("value")
                    retry = task.get("retry", 1)

                    if callback_msg:
                        callback_msg(f"执行步骤 {idx+1}: 类型={cmd_type}, 内容={cmd_value}")

                    if cmd_type == 1.0: 
                        mouseClick(1, "left", cmd_value, retry)
                        if callback_msg: callback_msg(f"单击左键: {cmd_value}")
                    
                    elif cmd_type == 2.0: 
                        mouseClick(2, "left", cmd_value, retry)
                        if callback_msg: callback_msg(f"双击左键: {cmd_value}")
                    
                    elif cmd_type == 3.0: 
                        mouseClick(1, "right", cmd_value, retry)
                        if callback_msg: callback_msg(f"右键单击: {cmd_value}")
                    
                    elif cmd_type == 4.0: 
                        pyperclip.copy(str(cmd_value))
                        # 核心适配：Mac 使用 command+v
                        if IS_MAC:
                            pyautogui.hotkey('command', 'v')
                        else:
                            pyautogui.hotkey('ctrl', 'v')
                        time.sleep(0.5)
                        if callback_msg: callback_msg(f"输入文本: {cmd_value}")
                    
                    elif cmd_type == 5.0: 
                        sleep_time = float(cmd_value)
                        time.sleep(sleep_time)
                        if callback_msg: callback_msg(f"等待 {sleep_time} 秒")
                    
                    elif cmd_type == 6.0: 
                        scroll_val = int(cmd_value)
                        pyautogui.scroll(scroll_val)
                        if callback_msg: callback_msg(f"滚轮滑动 {scroll_val}")

                    elif cmd_type == 7.0: 
                        keys = str(cmd_value).lower().split('+')
                        keys = [k.strip() for k in keys]
                        pyautogui.hotkey(*keys)
                        if callback_msg: callback_msg(f"按键组合: {cmd_value}")

                    elif cmd_type == 8.0: 
                        mouseMove(cmd_value, retry)
                        if callback_msg: callback_msg(f"鼠标悬停: {cmd_value}")

                    elif cmd_type == 9.0: 
                        path = str(cmd_value)
                        if os.path.isdir(path):
                            timestamp = time.strftime("%Y%m%d_%H%M%S")
                            filename = os.path.join(path, f"screenshot_{timestamp}.png")
                        else:
                            filename = path
                            if not filename.endswith(('.png', '.jpg', '.bmp')):
                                filename += '.png'
                        
                        pyautogui.screenshot(filename)
                        if callback_msg: callback_msg(f"截图已保存: {filename}")

                if not loop_forever:
                    break
                
                if callback_msg: callback_msg("等待 0.1 秒进入下一轮循环...")
                time.sleep(0.1)
                
        except Exception as e:
            if callback_msg: callback_msg(f"执行出错: {e}")
            traceback.print_exc()
        finally:
            self.is_running = False
            if callback_msg: callback_msg("任务结束")

# --------------------------
# GUI 界面
# --------------------------

CMD_TYPES = {
    "左键单击": 1.0,
    "左键双击": 2.0,
    "右键单击": 3.0,
    "输入文本": 4.0,
    "等待(秒)": 5.0,
    "滚轮滑动": 6.0,
    "系统按键": 7.0,
    "鼠标悬停": 8.0,
    "截图保存": 9.0
}
CMD_TYPES_REV = {v: k for k, v in CMD_TYPES.items()}

class WorkerThread(QThread):
    log_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, engine, tasks, loop_forever):
        super().__init__()
        self.engine = engine
        self.tasks = tasks
        self.loop_forever = loop_forever

    def run(self):
        self.engine.run_tasks(self.tasks, self.loop_forever, self.log_callback)
        self.finished_signal.emit()

    def log_callback(self, msg):
        self.log_signal.emit(msg)

class TaskRow(QFrame):
    def __init__(self, parent_layout, delete_callback):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(CMD_TYPES.keys()))
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        self.layout.addWidget(self.type_combo)
        
        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("参数值 (如图片路径、文本、时间)")
        self.layout.addWidget(self.value_input)
        
        self.file_btn = QPushButton("选择图片")
        self.file_btn.clicked.connect(self.select_file)
        self.layout.addWidget(self.file_btn)
        
        self.retry_input = QLineEdit()
        self.retry_input.setPlaceholderText("重试次数 (1=一次, -1=无限)")
        self.retry_input.setText("1")
        self.retry_input.setFixedWidth(100)
        self.layout.addWidget(self.retry_input)
        
        self.del_btn = QPushButton("X")
        self.del_btn.setStyleSheet("color: red; font-weight: bold;")
        self.del_btn.setFixedWidth(30)
        self.del_btn.clicked.connect(lambda: delete_callback(self))
        self.layout.addWidget(self.del_btn)
        
        parent_layout.addWidget(self)

    def on_type_changed(self, text):
        cmd_type = CMD_TYPES[text]
        
        if cmd_type in [1.0, 2.0, 3.0, 8.0]:
            self.file_btn.setVisible(True)
            self.file_btn.setText("选择图片")
            self.retry_input.setVisible(True)
            self.value_input.setPlaceholderText("图片路径")
        elif cmd_type == 4.0:
            self.file_btn.setVisible(False)
            self.retry_input.setVisible(False)
            self.value_input.setPlaceholderText("请输入要发送的文本")
        elif cmd_type == 5.0:
            self.file_btn.setVisible(False)
            self.retry_input.setVisible(False)
            self.value_input.setPlaceholderText("等待秒数 (如 1.5)")
        elif cmd_type == 6.0:
            self.file_btn.setVisible(False)
            self.retry_input.setVisible(False)
            self.value_input.setPlaceholderText("滚动距离 (正数向上，负数向下)")
        elif cmd_type == 7.0:
            self.file_btn.setVisible(False)
            self.retry_input.setVisible(False)
            # 适配 Mac 占位符提示
            placeholder = "组合键 (如 command+s, option+tab)" if IS_MAC else "组合键 (如 ctrl+s, alt+tab)"
            self.value_input.setPlaceholderText(placeholder)
        elif cmd_type == 9.0:
            self.file_btn.setVisible(True)
            self.file_btn.setText("选择保存文件夹")
            self.retry_input.setVisible(False)
            placeholder = "保存目录 (如 /Users/用户名/Desktop)" if IS_MAC else "保存目录 (如 D:\\Screenshots)"
            self.value_input.setPlaceholderText(placeholder)

    def set_data(self, data):
        cmd_type = data.get("type")
        value = data.get("value", "")
        retry = data.get("retry", 1)

        if cmd_type in CMD_TYPES_REV:
            self.type_combo.setCurrentText(CMD_TYPES_REV[cmd_type])
        
        self.value_input.setText(str(value))
        self.retry_input.setText(str(retry))

    def select_file(self):
        cmd_type = CMD_TYPES[self.type_combo.currentText()]
        
        if cmd_type == 9.0:
            folder = QFileDialog.getExistingDirectory(self, "选择保存文件夹", os.path.expanduser("~"))
            if folder:
                self.value_input.setText(folder)
        else:
            filename, _ = QFileDialog.getOpenFileName(self, "选择图片", os.path.expanduser("~"), "Image Files (*.png *.jpg *.bmp)")
            if filename:
                self.value_input.setText(filename)

    def get_data(self):
        cmd_type = CMD_TYPES[self.type_combo.currentText()]
        value = self.value_input.text()
        
        try:
            if cmd_type in [5.0, 6.0]:
                if not value: value = "0"
            retry = 1
            if self.retry_input.isVisible():
                retry_text = self.retry_input.text()
                if retry_text: retry = int(retry_text)
        except ValueError:
            pass

        return {"type": cmd_type, "value": value, "retry": retry}

class RPAWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("不高兴就喝水 RPA 配置工具 (Mac 兼容版)")
        self.resize(800, 600)
        
        self.engine = RPAEngine()
        self.worker = None
        self.rows = []

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        top_bar = QHBoxLayout()
        self.add_btn = QPushButton("+ 新增指令")
        self.add_btn.clicked.connect(self.add_row)
        top_bar.addWidget(self.add_btn)

        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self.save_config)
        top_bar.addWidget(self.save_btn)

        self.load_btn = QPushButton("导入配置")
        self.load_btn.clicked.connect(self.load_config)
        top_bar.addWidget(self.load_btn)
        
        top_bar.addStretch()
        
        self.loop_check = QComboBox()
        self.loop_check.addItems(["执行一次", "循环执行"])
        top_bar.addWidget(self.loop_check)
        
        start_container = QWidget()
        start_layout = QVBoxLayout(start_container)
        start_layout.setContentsMargins(0, 0, 0, 0)
        
        self.start_btn = QPushButton("开始运行")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.start_btn.clicked.connect(self.start_task)
        start_layout.addWidget(self.start_btn)
        
        self.minimize_check = QCheckBox("运行时最小化")
        self.minimize_check.setChecked(True) 
        start_layout.addWidget(self.minimize_check)
        
        top_bar.addWidget(start_container)
        
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.stop_btn.clicked.connect(self.stop_task)
        self.stop_btn.setEnabled(False)
        top_bar.addWidget(self.stop_btn)
        
        main_layout.addLayout(top_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.addStretch()
        scroll.setWidget(self.task_container)
        main_layout.addWidget(scroll)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(150)
        main_layout.addWidget(QLabel("运行日志:"))
        main_layout.addWidget(self.log_area)

        self.add_row()

    def add_row(self, data=None):
        self.task_layout.takeAt(self.task_layout.count() - 1)
        row = TaskRow(self.task_layout, self.delete_row)
        if data: row.set_data(data)
        self.rows.append(row)
        self.task_layout.addStretch()

    def delete_row(self, row_widget):
        if row_widget in self.rows:
            self.rows.remove(row_widget)
            row_widget.deleteLater()
            
    def save_config(self):
        tasks = [row.get_data() for row in self.rows]
        if not tasks:
            QMessageBox.warning(self, "警告", "没有可保存的配置")
            return

        filename, _ = QFileDialog.getSaveFileName(self, "保存配置", os.path.expanduser("~"), "JSON Files (*.json);;Text Files (*.txt)")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(tasks, f, indent=4, ensure_ascii=False)
                QMessageBox.information(self, "成功", "配置已保存！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def load_config(self):
        filename, _ = QFileDialog.getOpenFileName(self, "导入配置", os.path.expanduser("~"), "JSON Files (*.json);;Text Files (*.txt)")
        if not filename: return
            
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                tasks = json.load(f)
            
            if not isinstance(tasks, list): raise ValueError("文件格式不正确")

            for row in self.rows: row.deleteLater()
            self.rows.clear()
            
            for task in tasks: self.add_row(task)
            QMessageBox.information(self, "成功", f"成功导入 {len(tasks)} 条指令！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败: {e}")

    def start_task(self):
        tasks = []
        for row in self.rows:
            data = row.get_data()
            if not data['value']:
                QMessageBox.warning(self, "警告", "请检查有空参数的指令！")
                return
            tasks.append(data)
            
        if not tasks:
            QMessageBox.warning(self, "警告", "请至少添加一条指令！")
            return

        self.log_area.clear()
        self.log("任务开始...")
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.add_btn.setEnabled(False)
        
        loop = (self.loop_check.currentText() == "循环执行")
        
        self.worker = WorkerThread(self.engine, tasks, loop)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

        if self.minimize_check.isChecked():
            self.showMinimized()

    def stop_task(self):
        self.engine.stop()
        self.log("正在停止...")

    def on_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.add_btn.setEnabled(True)
        self.log("任务已结束")
        
        if self.minimize_check.isChecked() or self.isMinimized():
            self.showNormal()
            self.activateWindow()

    def log(self, msg):
        self.log_area.append(msg)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.engine.stop()
            self.worker.quit()
            self.worker.wait()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = RPAWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
