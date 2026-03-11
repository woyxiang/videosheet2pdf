# /// script
# dependencies = [
#   "opencv-python",
# ]
# ///

import os
import sys
import glob
import shutil
import subprocess
import argparse
import cv2 as cv

# ================= 默认配置 =================
DEFAULT_CONFIG = {
    "TEMP_DIR": "temp_frames",
    "SAMPLE_FRAME_INDEX": 50,
    "THRESH_VALUE": 240,
    "THRESH_MAX": 255,
    "SCENE_THRESHOLD": 0.01,
    "TILE_LAYOUT": "1x5",
    "DENSITY": "300",
    "COMPRESS_METHOD": "Group4",
    "ENABLE_CROP": True,
    "KEEP_TEMP": False,  # 默认不保留临时文件
}

# ================= 逻辑区  =================

def get_crop_params(video_path, config):
    """计算 crop 参数，增加边缘内缩和偶数对齐"""
    if not config["ENABLE_CROP"]:
        return None

    vid = cv.VideoCapture(video_path)
    vid.set(cv.CAP_PROP_POS_FRAMES, config["SAMPLE_FRAME_INDEX"])
    ret, frame = vid.read()
    vid.release()

    if not ret:
        print("[!] 警告：无法读取视频帧，将跳过裁剪。")
        return None

    gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
    gray = cv.medianBlur(gray, 3)
    
    thresh = cv.threshold(gray, config["THRESH_VALUE"], config["THRESH_MAX"], cv.THRESH_BINARY)[1]
    contours, _ = cv.findContours(thresh, cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    contours = sorted(contours, key=cv.contourArea, reverse=True)
    h_img, w_img = frame.shape[:2]
    x, y, w, h = cv.boundingRect(contours[0])
    
    if w == w_img and h == h_img and len(contours) > 1:
        x, y, w, h = cv.boundingRect(contours[1])

    padding = 1 
    x, y, w, h = x + padding, y + padding, w - (padding * 2), h - (padding * 2)
    w, h, x, y = w & ~1, h & ~1, x & ~1, y & ~1

    return f"{w}:{h}:{x}:{y}"

def extract_frames(video_path, crop_params, config):
    """FFmpeg 场景检测抽帧"""
    if not os.path.exists(config["TEMP_DIR"]):
        os.makedirs(config["TEMP_DIR"])
    else:
        # 清理旧的残余文件
        for f in glob.glob(os.path.join(config["TEMP_DIR"], "*.png")):
            os.remove(f)

    output_pattern = os.path.join(config["TEMP_DIR"], "frame_%03d.png")
    
    filters = []
    if crop_params:
        filters.append(f"crop={crop_params}")
    filters.append(f"select='not(n)+gt(scene,{config['SCENE_THRESHOLD']})'")
    filters.append("setpts=N/FRAME_RATE/TB")
    
    vf_param = ",".join(filters)
    
    cmd = [
        "ffmpeg", "-loglevel", "warning", "-hide_banner", 
        "-i", video_path,
        "-vf", vf_param,
        "-fps_mode", "vfr", 
        output_pattern, "-y"
    ]
    print(f"[*] 执行命令: {' '.join(cmd)}")
    subprocess.run(cmd)

def build_pdf(output_pdf, config):
    """Magick 合成 PDF"""
    input_pattern = os.path.join(config["TEMP_DIR"], "*.png")
    
    cmd = [
        "magick", "montage", f'"{input_pattern}"',
        "-tile", config["TILE_LAYOUT"],
        "-geometry", "+0+0",
        "-compress", config["COMPRESS_METHOD"],
        "-density", config["DENSITY"],
        f'"{output_pdf}"'
    ]
    
    cmd_str = " ".join(cmd)
    print(f"[*] 执行命令: {cmd_str}")
    subprocess.run(cmd_str, shell=True)

# ================= 入口区  =================

def main():
    parser = argparse.ArgumentParser(description="视频乐谱转 PDF 工具")
    
    parser.add_argument("video", help="输入视频文件路径")
    parser.add_argument("-o", "--output", help="输出 PDF 路径")

    # 参数开关
    parser.add_argument("--no-crop", action="store_false", dest="enable_crop", help="禁用自动裁剪")
    parser.add_argument("--keep", action="store_true", dest="keep_temp", help="保留临时生成的图片文件")
    
    # 调节参数
    parser.add_argument("--thresh", type=int, default=DEFAULT_CONFIG["THRESH_VALUE"], help="二值化阈值")
    parser.add_argument("--scene", type=float, default=DEFAULT_CONFIG["SCENE_THRESHOLD"], help="场景变动阈值")
    parser.add_argument("--tile", default=DEFAULT_CONFIG["TILE_LAYOUT"], help="PDF 布局 (如 1x5)")
    parser.add_argument("--index", type=int, default=DEFAULT_CONFIG["SAMPLE_FRAME_INDEX"], help="采样帧索引")
    parser.add_argument("--density", default=DEFAULT_CONFIG["DENSITY"], help="PDF 像素密度")

    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()
    config.update({
        "ENABLE_CROP": args.enable_crop,
        "KEEP_TEMP": args.keep_temp,
        "THRESH_VALUE": args.thresh,
        "SCENE_THRESHOLD": args.scene,
        "TILE_LAYOUT": args.tile,
        "SAMPLE_FRAME_INDEX": args.index,
        "DENSITY": args.density
    })

    video_file = args.video
    output_pdf = args.output if args.output else f"{os.path.splitext(video_file)[0]}.pdf"

    if not os.path.exists(video_file):
        print(f"错误: 找不到文件 '{video_file}'")
        sys.exit(1)

    print("=== 视频乐谱转 PDF 工作流启动 ===")
    try:
        crop_params = get_crop_params(video_file, config)
        if crop_params:
            print(f"[*] 自动计算 Crop 参数: {crop_params}")
        
        extract_frames(video_file, crop_params, config)
        build_pdf(output_pdf, config)
        
        # 自动删除临时文件夹
        if not config["KEEP_TEMP"]:
            print(f"[*] 正在清理临时文件: {config['TEMP_DIR']}")
            shutil.rmtree(config["TEMP_DIR"], ignore_errors=True)
        
        print(f"=== 成功！PDF 已生成: {output_pdf} ===")
    except Exception as e:
        print(f"工作流异常: {e}")

if __name__ == "__main__":
    main()