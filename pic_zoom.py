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
        print(f"DEBUG: ImageProcessorTask.run - 任务开始执行。")
        if self.original_image_pil is None:
            print(f"DEBUG: ImageProcessorTask.run - 错误：没有加载图片。")
            self.signals.error.emit("没有加载图片，无法处理。")
            self.signals.finished.emit()
            return

        try:
            # 确保新尺寸的宽高都是正整数
            width, height = self.new_size
            print(f"DEBUG: ImageProcessorTask.run - 目标新尺寸: {width}x{height}")
            if width < 1: width = 1
            if height < 1: height = 1
            
            # 使用 LANCZOS 算法进行高质量缩放
            scaled_image_pil = self.original_image_pil.resize((width, height), Image.Resampling.LANCZOS)
            print(f"DEBUG: ImageProcessorTask.run - PIL图片缩放完成，尺寸: {scaled_image_pil.size}")

            # 将 PIL Image 转换为 QPixmap
            qimage = scaled_image_pil.toqimage()
            print(f"DEBUG: ImageProcessorTask.run - PIL Image 转换为 QImage 完成，有效性: {not qimage.isNull()}, 格式: {qimage.format()}, 尺寸: {qimage.size().width()}x{qimage.size().height()}")
            
            pixmap = QPixmap.fromImage(qimage)
            print(f"DEBUG: ImageProcessorTask.run - QImage 转换为 QPixmap 完成，有效性: {not pixmap.isNull()}, 尺寸: {pixmap.size().width()}x{pixmap.size().height()}")

            self.signals.image_processed.emit(pixmap) # 发送处理结果
            print(f"DEBUG: ImageProcessorTask.run - 发送 image_processed 信号。")

        except Exception as e:
            print(f"DEBUG: ImageProcessorTask.run - 捕获到异常: {e}")
            self.signals.error.emit(f"图片处理失败: {e}")
        finally:
            self.signals.finished.emit() # 无论成功或失败，都发出完成信号
            print(f"DEBUG: ImageProcessorTask.run - 发送 finished 信号。")

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
        
        self.scroll_area = QScrollArea() # 将 scroll_area 设为实例属性，方便在其他方法中访问
        self.scroll_area.setWidgetResizable(True) # 允许滚动区域调整其内部 widget 的大小
        self.scroll_area.setWidget(self.image_label)
        main_layout.addWidget(self.scroll_area)

        print(f"DEBUG: init_ui - QLabel 初始尺寸: {self.image_label.size().width()}x{self.image_label.size().height()}")
        print(f"DEBUG: init_ui - QScrollArea 初始尺寸: {self.scroll_area.size().width()}x{self.scroll_area.size().height()}")
        print(f"DEBUG: init_ui - QScrollArea 内部 Widget 初始尺寸: {self.scroll_area.widget().size().width()}x{self.scroll_area.widget().size().height()}")
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
        
        # 将缩放滑块和输入框放入一个垂直布局，以便在其下方添加标识
        zoom_control_v_layout = QVBoxLayout()
        zoom_control_h_layout = QHBoxLayout() # 包含 "缩放:", slider, input

        zoom_control_h_layout.addWidget(QLabel("缩放:"))
        zoom_control_h_layout.addWidget(self.zoom_slider)
        zoom_control_h_layout.addWidget(self.zoom_input)

        zoom_control_v_layout.addLayout(zoom_control_h_layout)

        # 添加缩放标识
        zoom_labels_layout = QHBoxLayout()
        labels_data = [
            ("10%", 10),
            ("50%", 50),
            ("100%", 100),
            ("200%", 200),
            ("300%", 300),
            ("400%", 400),
            ("500%", 500)
        ]

        prev_value = self.zoom_slider.minimum()
        for i, (text, value) in enumerate(labels_data):
            if i == 0:
                # 第一个标签，前面没有 stretch
                pass
            else:
                # 添加一个 stretch，其因子与前一个标签到当前标签的距离成比例
                stretch_factor = value - prev_value
                zoom_labels_layout.addStretch(stretch_factor)
            
            label = QLabel(text)
            label.setAlignment(Qt.AlignCenter) # 居中对齐
            zoom_labels_layout.addWidget(label)
            prev_value = value

        # 最后一个标签后面添加一个 stretch，以填充剩余空间
        zoom_labels_layout.addStretch(self.zoom_slider.maximum() - prev_value)

        zoom_control_v_layout.addLayout(zoom_labels_layout)
        controls_layout.addLayout(zoom_control_v_layout) # 将这个垂直布局添加到主控制布局中
        
        main_layout.addLayout(controls_layout)

    def set_zoom_factor(self, factor: float):
        """
        API: 设置图片的缩放倍率。
        factor: 缩放倍率，例如 1.0 代表 100%，0.5 代表 50%。
        """
        # 将浮点数因子转换为滑块的整数值 (100% -> 100)
        slider_value = int(factor * 100)
        # 限制在滑块的有效范围内
        slider_value = max(self.zoom_slider.minimum(), min(self.zoom_slider.maximum(), slider_value))
        self.zoom_slider.setValue(slider_value) # 这会触发 update_zoom_from_slider 和 display_image
        print(f"DEBUG: set_zoom_factor - 外部调用设置缩放倍率到: {factor} (滑块值: {slider_value})")

    def open_image(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "选择图片", "", 
                                                    "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.tiff);;所有文件 (*.*)")
        if file_path:
            print(f"DEBUG: open_image - 选择的文件路径: {file_path}")
            try:
                self.original_image_pil = Image.open(file_path)
                print(f"DEBUG: open_image - PIL图片加载成功，尺寸: {self.original_image_pil.size}, 模式: {self.original_image_pil.mode}, 格式: {self.original_image_pil.format}")
                self.current_zoom_factor = 1.0 # 重置缩放比例
                self.zoom_slider.setValue(100) # 重置滑块
                self.zoom_input.setText("100%") # 重置输入框
                self.display_image() # 触发初始显示和处理
            except Exception as e:
                print(f"DEBUG: open_image - 无法加载图片: {e}")
                self.image_label.setText(f"无法加载图片: {e}")
                self.original_image_pil = None
                self.image_label.setPixmap(QPixmap()) # 清空任何之前的图片
        else:
            print(f"DEBUG: open_image - 未选择文件。")

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
        print(f"DEBUG: display_image - 进入 display_image 函数。")
        if self.original_image_pil:
            print(f"DEBUG: display_image - 原始图片已加载。")
            original_width, original_height = self.original_image_pil.size
            
            # 根据当前缩放比例计算新尺寸
            new_width = int(original_width * self.current_zoom_factor)
            new_height = int(original_height * self.current_zoom_factor)
            print(f"DEBUG: display_image - 计算新尺寸: {new_width}x{new_height} (缩放因子: {self.current_zoom_factor})")

            # 创建一个新的任务实例
            task = ImageProcessorTask(self.original_image_pil, (new_width, new_height))
            print(f"DEBUG: display_image - 创建 ImageProcessorTask 实例。")
            
            # 连接任务的信号到主线程的槽函数
            task.signals.image_processed.connect(self._update_image_display)
            task.signals.error.connect(self._handle_processing_error)
            task.signals.finished.connect(self._processing_finished) # 任务完成时重新启用控件
            print(f"DEBUG: display_image - 连接任务信号到槽函数。")

            self.thread_pool.start(task) # 提交任务到线程池
            print(f"DEBUG: display_image - 任务已提交到线程池。")

            # 在任务处理期间显示“正在处理”消息，并清空旧图片
            self.image_label.setText("正在处理图片，请稍候...")
            self.image_label.setPixmap(QPixmap()) 
            self._set_controls_enabled(False) # 禁用控件，防止用户在处理期间再次操作
            print(f"DEBUG: display_image - UI更新为'正在处理'并禁用控件。")

        else:
            print(f"DEBUG: display_image - 原始图片未加载，显示提示信息。")
            self.image_label.setText("请点击 '打开图片' 加载图片")
            self.image_label.setPixmap(QPixmap()) # 清空图片
            self._set_controls_enabled(True) # 确保在没有图片时控件是启用的

    @pyqtSlot(QPixmap)
    def _update_image_display(self, pixmap):
        """槽函数：接收工作线程处理完成的 QPixmap 并更新 UI。"""
        print(f"DEBUG: _update_image_display - 接收到 QPixmap 信号，QPixmap 有效性: {not pixmap.isNull()}, 尺寸: {pixmap.size().width()}x{pixmap.size().height()}")
        self.image_label.setPixmap(pixmap)
        self.image_label.adjustSize() # 调整 QLabel 的大小以适应新的 QPixmap
        
        print(f"DEBUG: _update_image_display - 图片已更新到 QLabel。")
        print(f"DEBUG: _update_image_display - QLabel 最终尺寸: {self.image_label.size().width()}x{self.image_label.size().height()}")
        print(f"DEBUG: _update_image_display - QLabel 内部 Pixmap 有效性: {not self.image_label.pixmap().isNull()}")
        print(f"DEBUG: _update_image_display - QLabel 可见性: {self.image_label.isVisible()}")
        print(f"DEBUG: _update_image_display - QLabel 父控件 (QScrollArea) 可见性: {self.image_label.parentWidget().isVisible()}")
        print(f"DEBUG: _update_image_display - QScrollArea 最终尺寸: {self.scroll_area.size().width()}x{self.scroll_area.size().height()}")
        print(f"DEBUG: _update_image_display - QScrollArea 内部 Widget (QLabel) 最终尺寸: {self.scroll_area.widget().size().width()}x{self.scroll_area.widget().size().height()}")
        
        # 强制更新布局，确保所有尺寸变化生效
        self.scroll_area.widget().updateGeometry()
        self.scroll_area.updateGeometry()
        self.updateGeometry()
        print(f"DEBUG: _update_image_display - 强制更新布局完成。")
    @pyqtSlot(str)
    def _handle_processing_error(self, error_message):
        """槽函数：处理工作线程发出的错误信息。"""
        print(f"DEBUG: _handle_processing_error - 接收到错误信息: {error_message}")
        self.image_label.setText(f"错误: {error_message}")
        self.image_label.setPixmap(QPixmap()) # 错误时清空图片

    @pyqtSlot()
    def _processing_finished(self):
        """槽函数：图片处理任务完成（无论成功或失败）时调用。"""
        print(f"DEBUG: _processing_finished - 图片处理任务完成，重新启用控件。")
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
