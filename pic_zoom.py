import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QSlider, QFileDialog, QHBoxLayout, QPushButton, QLineEdit, QScrollArea
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QSize, QThreadPool, QRunnable, pyqtSignal, pyqtSlot, QObject

# 导入 PIL 库
from PIL import Image
class ImageProcessorSignals(QObject):
    """
    定义工作线程可发出的信号。
    """
    image_processed = pyqtSignal(QPixmap) # 处理完成的 QPixmap
    error = pyqtSignal(str)              # 错误信息
    finished = pyqtSignal()              # 任务完成（无论成功或失败）

class ImageProcessorTask(QRunnable):
    """
    用于在单独线程中处理图片缩放的 QRunnable 任务。
    """
    def __init__(self, original_image_pil, new_size):
        super().__init__()
        self.original_image_pil = original_image_pil
        self.new_size = new_size
        self.signals = ImageProcessorSignals() # 每个任务实例都有自己的信号发射器

    @pyqtSlot()
    def run(self):
        """
        实际的图片处理逻辑，在工作线程中执行。
        """
        if self.original_image_pil is None:
            self.signals.error.emit("没有加载图片，无法处理。")
            self.signals.finished.emit()
            return

        try:
            # 确保新尺寸的宽高都是正整数
            width, height = self.new_size
            if width < 1: width = 1
            if height < 1: height = 1
            
            # 使用 LANCZOS 算法进行高质量缩放
            scaled_image_pil = self.original_image_pil.resize((width, height), Image.Resampling.LANCZOS)

            # 将 PIL Image 转换为 QPixmap
            qimage = scaled_image_pil.toqimage()
            pixmap = QPixmap.fromImage(qimage)

            self.signals.image_processed.emit(pixmap) # 发送处理结果

        except Exception as e:
            self.signals.error.emit(f"图片处理失败: {e}")
        finally:
            self.signals.finished.emit() # 无论成功或失败，都发出完成信号

class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python 图片缩放工具 (优化版)")
        self.setGeometry(100, 100, 1000, 700)

        self.original_image_pil = None # 存储原始 PIL 图片对象
        self.current_zoom_factor = 1.0 # 当前缩放比例

        # 初始化 QThreadPool 用于后台处理
        self.thread_pool = QThreadPool()
        # 设置最大线程数为1，确保一次只处理一个图片任务，避免CPU过载
        self.thread_pool.setMaxThreadCount(1) 

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 图片显示区域 (放在滚动区域内，以便查看大图)
        self.image_label = QLabel("请点击 '打开图片' 加载图片")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(False) # 关键：我们自己缩放 QPixmap，而不是让 QLabel 缩放
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True) # 允许滚动区域调整其内部 widget 的大小
        scroll_area.setWidget(self.image_label)
        main_layout.addWidget(scroll_area)

        # 控制面板
        controls_layout = QHBoxLayout()

        # 打开图片按钮
        open_button = QPushButton("打开图片")
        open_button.clicked.connect(self.open_image)
        controls_layout.addWidget(open_button)

        # 缩放滑块
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setMinimum(10) # 0.1x (10%)
        self.zoom_slider.setMaximum(500) # 5.0x (500%)
        self.zoom_slider.setValue(100) # 1.0x (100%)
        self.zoom_slider.setTickInterval(10)
        self.zoom_slider.setTickPosition(QSlider.TicksBelow)
        self.zoom_slider.valueChanged.connect(self.update_zoom_from_slider)
        controls_layout.addWidget(QLabel("缩放:"))
        controls_layout.addWidget(self.zoom_slider)

        # 缩放百分比输入框
        self.zoom_input = QLineEdit("100%")
        self.zoom_input.setFixedWidth(80)
        self.zoom_input.returnPressed.connect(self.update_zoom_from_input)
        controls_layout.addWidget(self.zoom_input)
        
        main_layout.addLayout(controls_layout)

    def open_image(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "选择图片", "", 
                                                    "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.tiff);;所有文件 (*.*)")
        if file_path:
            try:
                self.original_image_pil = Image.open(file_path)
                self.current_zoom_factor = 1.0 # 重置缩放比例
                self.zoom_slider.setValue(100) # 重置滑块
                self.zoom_input.setText("100%") # 重置输入框
                self.display_image() # 触发初始显示和处理
            except Exception as e:
                self.image_label.setText(f"无法加载图片: {e}")
                self.original_image_pil = None
                self.image_label.setPixmap(QPixmap()) # 清空任何之前的图片

    def update_zoom_from_slider(self, value):
        """根据滑块值更新缩放比例并触发图片显示。"""
        self.current_zoom_factor = value / 100.0
        self.zoom_input.setText(f"{value}%")
        self.display_image() # 触发图片处理

    def update_zoom_from_input(self):
        """根据输入框值更新缩放比例并触发图片显示。"""
        try:
            text = self.zoom_input.text().strip()
            if text.endswith('%'):
                value = float(text[:-1])
            else:
                value = float(text) * 100 # 假设用户输入 1.5 代表 150%
            
            # 将值限制在滑块的有效范围内
            if 10 <= value <= 500:
                self.zoom_slider.setValue(int(value)) # 这会触发 update_zoom_from_slider
            else:
                # 输入无效，恢复到当前值
                self.zoom_input.setText(f"{int(self.current_zoom_factor * 100)}%") 
        except ValueError:
            self.zoom_input.setText(f"{int(self.current_zoom_factor * 100)}%") # 输入无效，恢复

    def display_image(self):
        """
        计算新尺寸，创建并提交图片处理任务到线程池。
        """
        if self.original_image_pil:
            original_width, original_height = self.original_image_pil.size
            
            # 根据当前缩放比例计算新尺寸
            new_width = int(original_width * self.current_zoom_factor)
            new_height = int(original_height * self.current_zoom_factor)

            # 创建一个新的任务实例
            task = ImageProcessorTask(self.original_image_pil, (new_width, new_height))
            
            # 连接任务的信号到主线程的槽函数
            task.signals.image_processed.connect(self._update_image_display)
            task.signals.error.connect(self._handle_processing_error)
            task.signals.finished.connect(self._processing_finished) # 任务完成时重新启用控件

            self.thread_pool.start(task) # 提交任务到线程池

            # 在任务处理期间显示“正在处理”消息，并清空旧图片
            self.image_label.setText("正在处理图片，请稍候...")
            self.image_label.setPixmap(QPixmap()) 
            self._set_controls_enabled(False) # 禁用控件，防止用户在处理期间再次操作

        else:
            self.image_label.setText("请点击 '打开图片' 加载图片")
            self.image_label.setPixmap(QPixmap()) # 清空图片
            self._set_controls_enabled(True) # 确保在没有图片时控件是启用的

    @pyqtSlot(QPixmap)
    def _update_image_display(self, pixmap):
        """槽函数：接收工作线程处理完成的 QPixmap 并更新 UI。"""
        self.image_label.setPixmap(pixmap)
        self.image_label.adjustSize() # 调整 QLabel 的大小以适应新的 QPixmap

    @pyqtSlot(str)
    def _handle_processing_error(self, error_message):
        """槽函数：处理工作线程发出的错误信息。"""
        self.image_label.setText(f"错误: {error_message}")
        self.image_label.setPixmap(QPixmap()) # 错误时清空图片

    @pyqtSlot()
    def _processing_finished(self):
        """槽函数：图片处理任务完成（无论成功或失败）时调用。"""
        self._set_controls_enabled(True) # 重新启用控件

    def _set_controls_enabled(self, enabled):
        """辅助函数：启用/禁用 UI 控件。"""
        self.zoom_slider.setEnabled(enabled)
        self.zoom_input.setEnabled(enabled)
        # 如果需要，也可以禁用“打开图片”按钮，但通常打开图片操作可以独立进行。

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec_())
