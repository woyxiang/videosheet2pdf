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
    "KEEP_TEMP": False,
}

# ================= 逻辑区  =================

def get_crop_params(video_path, config):
    """计算 crop 参数，增加边缘内缩和偶数对齐"""
    vid = cv.VideoCapture(video_path)
    
    # 记录原始视频尺寸作为备选尺寸
    config["ORIGINAL_SIZE"] = (
        int(vid.get(cv.CAP_PROP_FRAME_WIDTH)), 
        int(vid.get(cv.CAP_PROP_FRAME_HEIGHT))
    )

    if not config["ENABLE_CROP"]:
        vid.release()
        return None

    if config["START_TIME"]:
        try:
            # 只处理简单的秒数，如果是 HH:MM:SS 格式则跳过
            ss_float = float(config["START_TIME"])
            vid.set(cv.CAP_PROP_POS_MSEC, ss_float * 1000)
        except ValueError:
            pass 

    vid.set(cv.CAP_PROP_POS_FRAMES, config["SAMPLE_FRAME_INDEX"])
    ret, frame = vid.read()
    vid.release()

    if not ret:
        print("[!] 警告：无法读取采样帧，将跳过裁剪。")
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

    # 保存计算后的尺寸用于补齐空白页
    config["CROP_SIZE"] = (w, h)
    return f"{w}:{h}:{x}:{y}"

def extract_frames(video_path, crop_params, config):
    """FFmpeg 场景检测抽帧"""
    if not os.path.exists(config["TEMP_DIR"]):
        os.makedirs(config["TEMP_DIR"])
    else:
        for f in glob.glob(os.path.join(config["TEMP_DIR"], "*.png")):
            os.remove(f)

    output_pattern = os.path.join(config["TEMP_DIR"], "frame_%03d.png")
    
    filters = []
    if crop_params:
        filters.append(f"crop={crop_params}")
    filters.append(f"select='not(n)+gt(scene,{config['SCENE_THRESHOLD']})'")
    filters.append("setpts=N/FRAME_RATE/TB")
    
    vf_param = ",".join(filters)
    
    cmd = ["ffmpeg", "-loglevel", "warning", "-hide_banner"]
    if config["START_TIME"]: cmd.extend(["-ss", config["START_TIME"]])
    if config["END_TIME"]: cmd.extend(["-to", config["END_TIME"]])
        
    cmd.extend([
        "-i", video_path,
        "-vf", vf_param,
        "-fps_mode", "vfr", 
        output_pattern, "-y"
    ])
    
    print(f"[*] 执行抽帧命令: {' '.join(cmd)}")
    subprocess.run(cmd)

def build_pdf(output_pdf, config):
    """Magick 合成 PDF，并自动补齐空白帧以统一页面大小"""
    input_files = sorted(glob.glob(os.path.join(config["TEMP_DIR"], "*.png")))
    if not input_files:
        print("[!] 没有提取到任何帧，跳过 PDF 生成。")
        return

    # 1. 计算补齐数量
    try:
        # 兼容 1x5 或 2x3 这种格式
        cols, rows = map(int, config["TILE_LAYOUT"].lower().split('x'))
        frames_per_page = cols * rows
    except:
        frames_per_page = 1

    num_files = len(input_files)
    remainder = num_files % frames_per_page
    padding_needed = (frames_per_page - remainder) if remainder != 0 else 0

    # 2. 获取补齐块的尺寸 (优先使用 crop 后的尺寸，否则使用原图尺寸)
    w, h = config.get("CROP_SIZE") or config.get("ORIGINAL_SIZE") or (1920, 1080)

    # 3. 构建 Magick 命令
    # 注意：在 Windows 下通配符和括号需要小心处理，这里我们直接展开文件列表最稳妥
    cmd = ["magick", "montage"]
    
    # 添加现有的图片
    cmd.extend([f'"{f}"' for f in input_files])

    # 如果需要补齐，直接在命令行添加虚拟画布
    if padding_needed > 0:
        print(f"[*] 最后一页缺 {padding_needed} 帧，正在使用 {w}x{h} 的空白块补齐...")
        # 设置接下来生成的 xc:white 的尺寸
        cmd.append(f"-size {w}x{h}")
        for _ in range(padding_needed):
            cmd.append("xc:white")

    cmd.extend([
        "-tile", config["TILE_LAYOUT"],
        "-geometry", "+0+0",
        "-compress", config["COMPRESS_METHOD"],
        "-density", config["DENSITY"],
        f'"{output_pdf}"'
    ])
    
    cmd_str = " ".join(cmd)
    print(f"[*] 执行合成命令: {cmd_str}")
    subprocess.run(cmd_str, shell=True)

# ================= 入口区  =================

def main():
    parser = argparse.ArgumentParser(description="视频乐谱转 PDF 工具")
    parser.add_argument("video", help="输入视频文件路径")
    parser.add_argument("-o", "--output", help="输出 PDF 路径")
    parser.add_argument("-ss", dest="start_time", help="开始时间")
    parser.add_argument("-to", dest="end_time", help="结束时间")
    parser.add_argument("--no-crop", action="store_false", dest="enable_crop", help="禁用自动裁剪")
    parser.add_argument("--keep", action="store_true", dest="keep_temp", help="保留临时文件")
    parser.add_argument("--thresh", type=int, default=DEFAULT_CONFIG["THRESH_VALUE"], help="二值化阈值")
    parser.add_argument("--scene", type=float, default=DEFAULT_CONFIG["SCENE_THRESHOLD"], help="场景变动阈值")
    parser.add_argument("--tile", default=DEFAULT_CONFIG["TILE_LAYOUT"], help="PDF 布局 (如 1x5)")
    parser.add_argument("--density", default=DEFAULT_CONFIG["DENSITY"], help="PDF 像素密度")

    args = parser.parse_args()
    config = DEFAULT_CONFIG.copy()
    config.update({
        "START_TIME": args.start_time, "END_TIME": args.end_time,
        "ENABLE_CROP": args.enable_crop, "KEEP_TEMP": args.keep_temp,
        "THRESH_VALUE": args.thresh, "SCENE_THRESHOLD": args.scene,
        "TILE_LAYOUT": args.tile, "DENSITY": args.density
    })

    if not os.path.exists(args.video):
        print(f"错误: 找不到文件 '{args.video}'")
        sys.exit(1)

    try:
        # 获取裁剪参数并暂存尺寸
        crop_params = get_crop_params(args.video, config)
        extract_frames(args.video, crop_params, config)
        
        output_pdf = args.output if args.output else f"{os.path.splitext(args.video)[0]}.pdf"
        build_pdf(output_pdf, config)
        
        if not config["KEEP_TEMP"]:
            shutil.rmtree(config["TEMP_DIR"], ignore_errors=True)
        print(f"=== 成功！PDF 已生成: {output_pdf} ===")
    except Exception as e:
        print(f"工作流异常: {e}")

if __name__ == "__main__":
    main()