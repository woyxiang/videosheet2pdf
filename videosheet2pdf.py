# /// script
# dependencies = [
#   "opencv-python",
# ]
# ///

import os
import sys
import glob
import subprocess
import cv2 as cv

# ================= 配置区 =================
CONFIG = {
    "TEMP_DIR": "temp_frames",
    "SAMPLE_FRAME_INDEX": 50,
    "THRESH_VALUE": 240,
    "THRESH_MAX": 255,
    "SCENE_THRESHOLD": 0.01,
    "TILE_LAYOUT": "1x5",
    "DENSITY": "300",
    "COMPRESS_METHOD": "Group4",
}

# ================= 逻辑区  =================

def get_crop_params(video_path):
    """计算 crop 参数，增加边缘内缩和偶数对齐"""
    vid = cv.VideoCapture(video_path)
    vid.set(cv.CAP_PROP_POS_FRAMES, CONFIG["SAMPLE_FRAME_INDEX"])
    ret, frame = vid.read()
    vid.release()

    if not ret:
        raise ValueError("无法读取视频帧。")

    gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
    gray = cv.medianBlur(gray, 3)
    
    thresh = cv.threshold(gray, CONFIG["THRESH_VALUE"], CONFIG["THRESH_MAX"], cv.THRESH_BINARY)[1]
    contours, _ = cv.findContours(thresh, cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE)

    if not contours:
        return "0:0:0:0"

    contours = sorted(contours, key=cv.contourArea, reverse=True)
    h_img, w_img = frame.shape[:2]
    x, y, w, h = cv.boundingRect(contours[0])
    
    if w == w_img and h == h_img and len(contours) > 1:
        x, y, w, h = cv.boundingRect(contours[1])

    # 内缩与对齐
    padding = 1 
    x, y, w, h = x + padding, y + padding, w - (padding * 2), h - (padding * 2)
    w, h, x, y = w & ~1, h & ~1, x & ~1, y & ~1

    return f"{w}:{h}:{x}:{y}"

def extract_frames(video_path, crop_params):
    """FFmpeg 场景检测抽帧"""
    if not os.path.exists(CONFIG["TEMP_DIR"]):
        os.makedirs(CONFIG["TEMP_DIR"])
    
    for f in glob.glob(os.path.join(CONFIG["TEMP_DIR"], "*.png")):
        os.remove(f)

    output_pattern = os.path.join(CONFIG["TEMP_DIR"], "frame_%03d.png")
    vf_param = f"crop={crop_params},select='not(n)+gt(scene,{CONFIG['SCENE_THRESHOLD']})',setpts=N/FRAME_RATE/TB"
    
    # 使用列表传参，并对关键路径加引号
    cmd = [
        "ffmpeg", "-loglevel", "warning", "-hide_banner", 
        "-i", video_path,
        "-vf", vf_param,
        "-fps_mode", "vfr", 
        output_pattern, "-y"
    ]
    print(f"[*] 执行命令: {' '.join(cmd)}")
    subprocess.run(cmd)

def build_pdf(output_pdf):
    """Magick 合成 PDF"""
    input_pattern = os.path.join(CONFIG["TEMP_DIR"], "*.png")
    
    # 针对 Windows shell 处理引号
    cmd = [
        "magick", "montage", f'"{input_pattern}"',
        "-tile", CONFIG["TILE_LAYOUT"],
        "-geometry", "+0+0",
        "-compress", CONFIG["COMPRESS_METHOD"],
        "-density", CONFIG["DENSITY"],
        f'"{output_pdf}"'
    ]
    
    cmd_str = " ".join(cmd)
    print(f"[*] 执行命令: {cmd_str}")
    subprocess.run(cmd_str, shell=True)

# ================= 入口区  =================

def main():
    if len(sys.argv) < 2:
        print("用法: uv run sheet2pdf.py <输入视频路径> [输出PDF路径]")
        sys.exit(1)

    video_file = sys.argv[1]
    output_pdf = sys.argv[2] if len(sys.argv) > 2 else f"{os.path.splitext(video_file)[0]}.pdf"

    if not os.path.exists(video_file):
        print(f"错误: 找不到文件 '{video_file}'")
        sys.exit(1)

    print("=== 视频乐谱转 PDF 工作流启动 ===")
    try:
        crop_params = get_crop_params(video_file)
        print(f"[*] 自动计算 Crop 参数: {crop_params}")
        
        extract_frames(video_file, crop_params)
        build_pdf(output_pdf)
        
        print(f"=== 成功！PDF 已生成: {output_pdf} ===")
    except Exception as e:
        print(f"工作流异常: {e}")

if __name__ == "__main__":
    main()