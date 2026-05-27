# -*- coding: utf-8 -*-
"""
手势交互识别系统

使用 OpenCV-Python 捕获摄像头视频流，借助 MediaPipe HandLandmarker
进行 21 点手部关键点检测，并通过自定义算法识别 7 种常见手势。
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision.hand_landmarker import (
    HandLandmark,
    HandLandmarksConnections
)
import os
import urllib.request
import numpy as np
import time

# MediaPipe 手部关键点检测模型的下载地址
MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task'
# 模型文件本地存储路径（与当前脚本同级目录）
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'hand_landmarker.task')

# 尝试导入 PIL 库用于中文绘制
try:
    from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    print('警告：未安装 PIL 库，中文显示可能不正常，请安装 Pillow')


def put_chinese_text(frame, text, pos, font_size=24, color=(0, 255, 0)):
    """
    在图像帧上绘制中文文本。

    使用 PIL 库绘制中文，避免 OpenCV 默认字体不支持中文的问题。

    参数:
        frame: OpenCV BGR 格式的图像帧（原地修改）
        text: 要绘制的中文文本
        pos: 文本左上角坐标 (x, y)
        font_size: 字体大小，默认 24
        color: 文本颜色 (B, G, R)，默认绿色

    返回:
        修改后的帧
    """
    if _PIL_AVAILABLE:
        from PIL import Image as _Image, ImageDraw as _ImageDraw, ImageFont as _ImageFont

        # 获取系统默认中文字体路径
        font_path = None
        # 尝试常见的中文字体路径
        font_candidates = [
            'C:/Windows/Fonts/simsun.ttc',           # 宋体
            'C:/Windows/Fonts/msyh.ttc',             # 微软雅黑
            'C:/Windows/Fonts/STXINGKA.TTF',         # 华文行楷
            '/Library/Fonts/Songti.ttc',             # macOS 宋体
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',  # Linux 文泉驿
        ]

        for candidate in font_candidates:
            if os.path.exists(candidate):
                font_path = candidate
                break

        try:
            if font_path:
                font = _ImageFont.truetype(font_path, font_size)
            else:
                # 如果找不到字体，使用默认字体
                font = _ImageFont.load_default()

            # OpenCV BGR → PIL RGB
            img_pil = _Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = _ImageDraw.Draw(img_pil)

            # 绘制中文文本
            draw.text(pos, text, font=font, fill=(color[2], color[1], color[0]))

            # PIL RGB → OpenCV BGR
            frame[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        except Exception:
            # 如果 PIL 绘制失败，回退到 OpenCV
            cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX,
                        font_size / 24, color, 2, cv2.LINE_AA)
    else:
        # 没有 PIL，直接使用 OpenCV（中文会显示为方框或问号）
        cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX,
                    font_size / 24, color, 2, cv2.LINE_AA)

    return frame


def download_model():
    """
    下载手部关键点检测模型文件。

    仅在模型文件不存在时执行下载，避免重复下载。
    模型文件大小约 7.8 MB，需确保网络可达 Google Cloud Storage。
    """
    if not os.path.exists(MODEL_PATH):
        print('正在下载手部关键点检测模型...')
        try:
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
            print(f'模型下载完成: {MODEL_PATH}')
        except Exception as e:
            print(f'模型下载失败: {e}')
            print(f'请手动下载模型文件并放置到: {MODEL_PATH}')
            print(f'下载地址: {MODEL_URL}')
            raise


class GestureRecognizer:
    """
    实时手势识别器。

    通过摄像头实时捕获视频帧，使用 MediaPipe HandLandmarker 检测手部
    21 个关键点，根据手指弯曲状态判断当前手势类型，并在画面中渲染
    关键点、骨架连线及手势名称。
    """

    def __init__(self):
        """初始化手势识别器：下载模型 → 创建 HandLandmarker 实例。"""
        download_model()

        # 构建 MediaPipe HandLandmarker 的配置选项
        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,   # 视频模式：逐帧检测并支持帧间追踪
            num_hands=2,                              # 最多同时检测 2 只手
            min_hand_detection_confidence=0.5,        # 手部检测最小置信度
            min_hand_presence_confidence=0.5,         # 手部存在最小置信度
            min_tracking_confidence=0.5               # 跨帧追踪最小置信度
        )
        self.detector = vision.HandLandmarker.create_from_options(options)

        # 手势内部标识 → 中文显示名称的映射
        self.gesture_names = {
            'fist': '拳头',
            'open': '手掌',
            'thumb_up': '点赞',
            'peace': '剪刀手',
            'ok': 'OK',
            'none': '未知手势',
            'point_up': '食指指上'
        }

        # 火球效果相关参数
        self.fireball_enabled = True  # 是否启用火球效果
        self.fireball_size = 40       # 火球基础大小
        self.fireball_particles = []  # 火球粒子列表
        self.last_time = time.time()  # 用于控制粒子生成速率

    def detect_gesture(self, hand_landmarks):
        """
        根据 21 个手部关键点坐标判断当前手势类型。

        判断逻辑：
        - 食指/中指/无名指/小指：比较指尖(TIP)与近端指间关节(PIP)的 Y 坐标，
          指尖 Y 值小于 PIP Y 值（在图像坐标系中 Y 轴向下）表示手指伸直。
        - 拇指：比较拇指指尖(THUMB_TIP)与指间关节(THUMB_IP)的 X 坐标，
          根据左右手分别使用不同的比较方向。

        参数:
            hand_landmarks: MediaPipe 返回的 21 个归一化关键点坐标列表

        返回:
            str: 手势标识字符串，取值范围见 self.gesture_names 的键
        """
        # 获取各手指指尖坐标
        thumb_tip = hand_landmarks[HandLandmark.THUMB_TIP]
        index_tip = hand_landmarks[HandLandmark.INDEX_FINGER_TIP]
        middle_tip = hand_landmarks[HandLandmark.MIDDLE_FINGER_TIP]
        ring_tip = hand_landmarks[HandLandmark.RING_FINGER_TIP]
        pinky_tip = hand_landmarks[HandLandmark.PINKY_TIP]

        # 获取拇指指间关节（用于判断拇指是否伸直）
        thumb_ip = hand_landmarks[HandLandmark.THUMB_IP]
        # 获取其余四指的近端指间关节（用于判断手指是否伸直）
        index_pip = hand_landmarks[HandLandmark.INDEX_FINGER_PIP]
        middle_pip = hand_landmarks[HandLandmark.MIDDLE_FINGER_PIP]
        ring_pip = hand_landmarks[HandLandmark.RING_FINGER_PIP]
        pinky_pip = hand_landmarks[HandLandmark.PINKY_PIP]

        # 列表记录 5 根手指的伸直状态，顺序：拇指、食指、中指、无名指、小指
        fingers_open = []

        # 判断左右手，以适配拇指伸直的正确判别方向
        is_left = self._is_left_hand(hand_landmarks)
        if is_left:
            # 左手：拇指指尖在关节左侧 → 伸直
            fingers_open.append(thumb_tip.x < thumb_ip.x)
        else:
            # 右手：拇指指尖在关节右侧 → 伸直
            fingers_open.append(thumb_tip.x > thumb_ip.x)

        # 其余四指：指尖 Y 值小于 PIP Y 值（在图像中更靠上）→ 伸直
        fingers_open.append(index_tip.y < index_pip.y)
        fingers_open.append(middle_tip.y < middle_pip.y)
        fingers_open.append(ring_tip.y < ring_pip.y)
        fingers_open.append(pinky_tip.y < pinky_pip.y)

        num_open = sum(fingers_open)

        # 根据伸直手指的数量和组合映射到具体手势
        if num_open == 0:
            return 'fist'                                         # 拳头：全部弯曲
        elif num_open == 5:
            return 'open'                                         # 手掌：全部伸直
        elif num_open == 1 and fingers_open[0]:
            return 'thumb_up'                                     # 点赞：仅拇指伸直
        elif num_open == 2 and fingers_open[1] and fingers_open[2]:
            return 'peace'                                        # 剪刀手：食指+中指伸直
        elif num_open == 4 and not fingers_open[4]:
            return 'ok'                                           # OK：四指伸直（不含小指）
        elif num_open == 1 and fingers_open[1]:
            return 'point_up'                                     # 食指指上：仅食指伸直
        else:
            return 'none'                                         # 无法匹配已知手势

    def _is_left_hand(self, hand_landmarks):
        """
        根据手部关键点位置判断是否为左手。

        判断依据：左手的手腕 X 坐标 > 中指掌指关节 X 坐标，
        因为左手掌在摄像头画面中手腕更靠右（大拇指在左侧）。

        参数:
            hand_landmarks: 21 个归一化关键点坐标列表

        返回:
            bool: True 表示左手，False 表示右手
        """
        wrist_x = hand_landmarks[HandLandmark.WRIST].x
        middle_mcp_x = hand_landmarks[HandLandmark.MIDDLE_FINGER_MCP].x
        return wrist_x > middle_mcp_x

    def _draw_landmarks(self, frame, hand_landmarks):
        """
        在图像帧上绘制手部关键点和骨架连线。

        - 骨架连线：绿色线段，连接相邻关键点
        - 关键点：红色实心圆，标记 21 个手部关键位置

        参数:
            frame: OpenCV BGR 格式的图像帧（原地修改）
            hand_landmarks: 归一化坐标的关键点列表
        """
        height, width = frame.shape[:2]

        # 绘制手部骨架连线（绿色）
        connections = HandLandmarksConnections.HAND_CONNECTIONS
        for conn in connections:
            start = hand_landmarks[conn.start]
            end = hand_landmarks[conn.end]
            pt1 = (int(start.x * width), int(start.y * height))
            pt2 = (int(end.x * width), int(end.y * height))
            cv2.line(frame, pt1, pt2, (0, 255, 0), 2)

        # 绘制 21 个关键点（红色实心圆）
        for lm in hand_landmarks:
            cx, cy = int(lm.x * width), int(lm.y * height)
            cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

    def _draw_fireball(self, frame, hand_landmarks):
        """
        在手掌中心绘制火球效果。

        火球由多层渐变圆形和动态粒子组成，模拟火焰效果。

        参数:
            frame: OpenCV BGR 格式的图像帧（原地修改）
            hand_landmarks: 归一化坐标的关键点列表
        """
        if not self.fireball_enabled:
            return

        height, width = frame.shape[:2]

        # 计算手掌中心位置（使用掌心关键点或多个指尖的平均值）
        # 取食指、中指、无名指、小指的指尖坐标计算中心
        finger_tips = [
            hand_landmarks[HandLandmark.INDEX_FINGER_TIP],
            hand_landmarks[HandLandmark.MIDDLE_FINGER_TIP],
            hand_landmarks[HandLandmark.RING_FINGER_TIP],
            hand_landmarks[HandLandmark.PINKY_TIP]
        ]
        center_x = sum(tip.x for tip in finger_tips) / 4
        center_y = sum(tip.y for tip in finger_tips) / 4

        # 添加手腕位置作为参考，使火球更靠近手掌中心
        wrist = hand_landmarks[HandLandmark.WRIST]
        center_x = (center_x * 3 + wrist.x) / 4
        center_y = (center_y * 3 + wrist.y) / 4

        # 转换为像素坐标
        cx = int(center_x * width)
        cy = int(center_y * height)

        # 动态大小，根据时间轻微变化模拟火焰跳动
        size = self.fireball_size + int(5 * np.sin(time.time() * 10))

        # 生成火焰粒子
        current_time = time.time()
        if current_time - self.last_time > 0.05:  # 每50ms生成一个粒子
            self.last_time = current_time
            self.fireball_particles.append({
                'x': cx + np.random.randint(-10, 10),
                'y': cy + np.random.randint(-10, 10),
                'size': np.random.randint(5, 15),
                'speed_y': -np.random.uniform(2, 5),
                'speed_x': np.random.uniform(-2, 2),
                'alpha': 1.0,
                'decay': np.random.uniform(0.02, 0.05)
            })

        # 更新和绘制粒子
        new_particles = []
        for particle in self.fireball_particles:
            particle['x'] += particle['speed_x']
            particle['y'] += particle['speed_y']
            particle['alpha'] -= particle['decay']
            particle['size'] *= 0.98  # 粒子逐渐变小

            if particle['alpha'] > 0:
                # 根据粒子大小决定颜色（大粒子偏白，小粒子偏红）
                if particle['size'] > 10:
                    color = (0, 200, 255)  # 白色核心
                elif particle['size'] > 5:
                    color = (0, 100, 255)  # 黄色
                else:
                    color = (0, 0, 255)    # 红色

                cv2.circle(frame,
                           (int(particle['x']), int(particle['y'])),
                           int(particle['size']),
                           color,
                           -1)
                new_particles.append(particle)
        self.fireball_particles = new_particles[:50]  # 限制粒子数量

        # 绘制火球主体（多层渐变）
        # 最外层：红色光晕
        cv2.circle(frame, (cx, cy), size + 15, (0, 0, 100), -1)
        # 外层：橙色
        cv2.circle(frame, (cx, cy), size + 8, (0, 80, 200), -1)
        # 中层：黄色
        cv2.circle(frame, (cx, cy), size, (0, 150, 255), -1)
        # 内层：白色核心
        cv2.circle(frame, (cx, cy), size // 2, (50, 200, 255), -1)
        # 中心亮点
        cv2.circle(frame, (cx, cy), size // 4, (255, 255, 255), -1)

    def process_frame(self, frame, timestamp_ms):
        """
        处理单帧图像：检测手部 → 绘制可视化 → 识别手势 → 标注结果。

        参数:
            frame: OpenCV BGR 格式的原始帧（原地修改）
            timestamp_ms: 帧的时间戳（毫秒），用于视频模式的帧间追踪

        返回:
            tuple: (标注后的帧, 检测到的手势列表)
        """
        # BGR → RGB 转换，并封装为 MediaPipe Image 对象
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        # 调用 MediaPipe 手部关键点检测
        result = self.detector.detect_for_video(mp_image, timestamp_ms)

        gestures = []

        if result.hand_landmarks:
            for i, hand_landmarks in enumerate(result.hand_landmarks):
                # 在帧上绘制关键点和骨架
                self._draw_landmarks(frame, hand_landmarks)

                # 在手掌中心绘制火球效果
                self._draw_fireball(frame, hand_landmarks)

                # 识别当前手势
                gesture = self.detect_gesture(hand_landmarks)
                gestures.append(gesture)

                # 获取手腕关键点坐标，作为手势标签的显示位置
                wrist = hand_landmarks[HandLandmark.WRIST]
                x = int(wrist.x * frame.shape[1])
                y = int(wrist.y * frame.shape[0])

                # 获取左右手信息并添加中文前缀
                handedness = ''
                if result.handedness and i < len(result.handedness):
                    category = result.handedness[i][0]
                    handedness = '左手-' if category.category_name == 'Left' else '右手-'

                # 在手腕附近显示手势名称标签（使用自定义中文绘制函数）
                label = f'{handedness}{self.gesture_names[gesture]}'
                put_chinese_text(frame, label, (x - 40, y - 30), font_size=20, color=(0, 255, 0))

        return frame, gestures

    def run(self):
        """
        主循环：打开摄像头 → 逐帧处理 → 实时显示 → 等待用户退出。

        按 'q' 键退出程序，按 'r' 键重置帧计数器（用于长时间运行）。
        """
        # 打开默认摄像头（索引 0）
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print('错误：无法打开摄像头，请检查摄像头是否可用。')
            return

        print('手势识别已启动，按 "q" 键退出程序，按 "f" 键切换火球效果。')

        # 获取摄像头帧率，若获取失败则默认 30 FPS
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30
        frame_count = 0

        while cap.isOpened():
            # 读取一帧画面
            success, frame = cap.read()
            if not success:
                print('错误：无法读取视频帧。')
                break

            # 水平镜像翻转，模拟照镜子效果（左手动 → 画面左手动）
            frame = cv2.flip(frame, 1)

            # 根据帧序号和 FPS 计算时间戳（毫秒）
            timestamp_ms = int((frame_count / fps) * 1000)
            frame_count += 1

            # 处理当前帧：检测手部、识别手势、绘制标注
            frame, gestures = self.process_frame(frame, timestamp_ms)

            # 在画面左上角显示操作提示（使用自定义中文绘制函数）
            put_chinese_text(frame, '手势识别中 - 按 "q" 键退出', 
                            (10, 35), font_size=24, color=(255, 100, 0))

            # 显示可视化窗口（使用英文标题避免窗口标题乱码）
            cv2.imshow('Gesture Recognition', frame)

            # 检测键盘输入
            key = cv2.waitKey(5) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                # 按 'r' 键重置帧计数器（避免长时间运行时间戳溢出）
                frame_count = 0
            elif key == ord('f'):
                # 按 'f' 键切换火球效果开关
                self.fireball_enabled = not self.fireball_enabled
                status = '开启' if self.fireball_enabled else '关闭'
                print(f'火球效果已{status}')

        # 释放资源
        cap.release()
        cv2.destroyAllWindows()
        self.detector.close()
        print('手势识别已停止。')


if __name__ == '__main__':
    recognizer = GestureRecognizer()
    recognizer.run()
