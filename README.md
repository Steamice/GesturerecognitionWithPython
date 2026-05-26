# Gesture Recognition With Python

基于摄像头的实时手势交互识别系统，使用 **OpenCV-Python** 处理视频流，**MediaPipe** 深度学习框架进行手部关键点检测与手势分类。

## 功能特性

- **实时摄像头手势识别**：通过摄像头实时捕获视频帧，毫秒级识别手势
- **7 种预定义手势**：拳头、手掌、点赞、剪刀手、OK、食指指上、未知手势
- **双手同时检测**：支持同时识别两只手，并自动标注左右手（L/R 前缀）
- **21 点手部关键点标注**：每个检测到的手会渲染 21 个关键点及骨架连线
- **镜像画面显示**：自动水平翻转画面，交互体验更自然
- **自动模型下载**：首次运行时自动下载 MediaPipe 手部关键点检测模型

## 支持的手势

| 手势名称 | 内部标识 | 判断逻辑 |
|---------|---------|---------|
| 拳头 (Fist) | `fist` | 所有手指弯曲（0 指张开） |
| 手掌 (Open Palm) | `open` | 所有手指伸直（5 指张开） |
| 点赞 (Thumb Up) | `thumb_up` | 仅拇指张开 |
| 剪刀手 (Peace) | `peace` | 仅食指和中指张开 |
| OK | `ok` | 除拇指外其余四指张开 |
| 食指指上 (Point Up) | `point_up` | 仅食指张开 |
| 未知 (Unknown) | `none` | 无法匹配以上任一手势 |

## 项目结构

```
GesturerecognitionWithPython/
├── gesture_recognition.py   # 主程序入口，手势识别核心逻辑
├── requirements.txt         # Python 依赖包列表
├── .gitignore               # Git 忽略规则（含 *.task 模型文件）
├── hand_landmarker.task     # MediaPipe 手部关键点模型（首次运行自动下载）
└── README.md                # 本文件
```

## 环境要求

- Python 3.10+
- 可用的摄像头设备

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd GesturerecognitionWithPython
```

### 2. 创建并激活虚拟环境

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 运行程序

```bash
python gesture_recognition.py
```

首次运行会自动从 Google 服务器下载手部关键点检测模型文件（约 7.8 MB），请确保网络连接正常。

### 5. 操作说明

- 将手部置于摄像头前方
- 做出相应手势，画面会实时显示识别结果
- 按 **`q`** 键退出程序

## 技术架构

### 核心依赖

| 库 | 版本 | 用途 |
|---|------|------|
| opencv-python | ≥4.5.5 | 摄像头视频流捕获、图像渲染 |
| mediapipe | ≥0.10.30 | 手部关键点深度学习检测（HandLandmarker） |
| numpy | ≥1.21.0 | 图像数据处理 |

### 技术方案

```
┌────────────────────────────────────────────────────┐
│  摄像头 (Camera)                                    │
│      │                                               │
│      ▼                                               │
│  cv2.VideoCapture                                   │
│      │                                               │
│      ▼                                               │
│  cv2.flip() ─── 水平镜像翻转                           │
│      │                                               │
│      ▼                                               │
│  mp.Image ─── BGR → SRGB 格式转换                     │
│      │                                               │
│      ▼                                               │
│  HandLandmarker.detect_for_video()                   │
│  MediaPipe 手部关键点深度学习推理                        │
│      │                                               │
│      ▼                                               │
│  ┌─────────────────────────┐                         │
│  │ Result:                  │                         │
│  │  - hand_landmarks (21点)  │                         │
│  │  - handedness (左/右手)   │                         │
│  └─────────────────────────┘                         │
│      │                                               │
│      ▼                                               │
│  自定义手指弯曲判断算法                                 │
│  detect_gesture()                                    │
│      │                                               │
│      ▼                                               │
│  OpenCV 渲染                                          │
│  - 21个关键点 (红色圆点)                               │
│  - 骨架连线 (绿色线条)                                 │
│  - 手势名称标签 (绿色文字)                              │
│      │                                               │
│      ▼                                               │
│  cv2.imshow() ─── 显示给用户                          │
└────────────────────────────────────────────────────┘
```

### 手势识别算法

通过分析 MediaPipe 输出的 21 个手部关键点坐标，判断每根手指的弯曲状态：

- **食指、中指、无名指、小指**：比较指尖 (TIP) 与近端指间关节 (PIP) 的 Y 坐标。指尖高于 PIP 视为伸直，反之弯曲
- **拇指**：比较拇指指尖 (THUMB_TIP) 与指间关节 (THUMB_IP) 的 X 坐标，并根据左右手方向调整判定逻辑

最终根据伸直手指的**数量**和**组合**映射到对应手势类别。

## API 说明

### `GestureRecognizer` 类

| 方法 | 说明 |
|-----|------|
| `__init__()` | 初始化识别器，下载模型并创建 HandLandmarker 实例 |
| `detect_gesture(hand_landmarks)` | 根据 21 个关键点坐标判断手势类型，返回手势标识字符串 |
| `process_frame(frame, timestamp_ms)` | 处理单帧图像：检测手部 → 绘制关键点 → 手势识别 → 返回标注帧 |
| `run()` | 主循环：打开摄像头 → 逐帧处理 → 显示结果 → 等待退出 |
| `_draw_landmarks(frame, hand_landmarks)` | 在帧上绘制 21 个关键点和骨架连线 |
| `_is_left_hand(hand_landmarks)` | 根据关键点坐标判断是否为左手 |

### 手势返回值

`detect_gesture()` 返回以下字符串之一：

```python
'fist'      # 拳头
'open'      # 手掌
'thumb_up'  # 点赞
'peace'     # 剪刀手
'ok'        # OK
'point_up'  # 食指指上
'none'      # 未知手势
```

## 配置参数

在 `GestureRecognizer.__init__()` 中可调整以下参数：

| 参数 | 默认值 | 说明 |
|-----|-------|------|
| `num_hands` | 2 | 最大检测手数 |
| `min_hand_detection_confidence` | 0.5 | 手部检测置信度阈值 (0.0-1.0) |
| `min_hand_presence_confidence` | 0.5 | 手部存在置信度阈值 (0.0-1.0) |
| `min_tracking_confidence` | 0.5 | 追踪置信度阈值 (0.0-1.0) |

## 许可证

MIT License

## 致谢

- [OpenCV](https://opencv.org/) - 开源计算机视觉库
- [Google MediaPipe](https://developers.google.com/mediapipe) - 跨平台机器学习解决方案
