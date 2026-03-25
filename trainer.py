"""
Tesseract 训练脚本
根据 assets/images 中的图像训练 Tesseract OCR 模型并生成 .traineddata 文件
"""

import os
import subprocess
import shutil
import zipfile
from pathlib import Path
from PIL import Image


def get_image_size(img_path):
    """获取图像尺寸"""
    with Image.open(img_path) as img:
        return img.size


def create_box_file(img_path, char, box_path):
    """创建 box 文件"""
    width, height = get_image_size(img_path)

    # Tesseract box 格式: <char> <left> <bottom> <right> <top> <page>
    # 坐标系: 左下角为原点 (0,0)
    # 所以 bottom=0, top=height
    with open(box_path, "w", encoding="utf-8") as f:
        f.write(f"{char} 0 0 {width} {height} 0\n")

    return width, height


def create_training_data():
    """创建训练数据"""
    assets_dir = Path("assets")
    images_dir = assets_dir / "images"
    training_dir = assets_dir / "training"

    # 创建目录
    training_dir.mkdir(parents=True, exist_ok=True)

    # 清理旧的训练文件
    for f in training_dir.glob("*"):
        if f.is_file():
            f.unlink()
    # 定义字符映射
    char_map = {}
    for path, dirs, files in images_dir.walk():
        for file in files:
            filePath = path / file
            c = filePath.name[0]
            if c == "A":
                char_map[filePath.name] = "A"
            elif c == "K":
                char_map[filePath.name] = "K"
            elif c == "Q":
                char_map[filePath.name] = "Q"
            elif c == "J":
                char_map[filePath.name] = "J"
            elif c == "T":
                char_map[filePath.name] = "T"
            elif c == "2":
                char_map[filePath.name] = "2"
            elif c == "3":
                char_map[filePath.name] = "3"
            elif c == "4":
                char_map[filePath.name] = "4"
            elif c == "5":
                char_map[filePath.name] = "5"
            elif c == "6":
                char_map[filePath.name] = "6"
            elif c == "7":
                char_map[filePath.name] = "7"
            elif c == "8":
                char_map[filePath.name] = "8"
            elif c == "9":
                char_map[filePath.name] = "9"
            elif c == "♠" or c == "♠️":
                char_map[filePath.name] = "S"
            elif c == "♥" or c == "♥️":
                char_map[filePath.name] = "H"
            elif c == "♣" or c == "♣️":
                char_map[filePath.name] = "C"
            elif c == "♦" or c == "♦️":
                char_map[filePath.name] = "D"

    training_files = []
    all_chars = set()

    # 处理每个图像文件
    for img_file, char in char_map.items():
        img_path = images_dir / img_file
        if not img_path.exists():
            print(f"跳过: {img_file} (文件不存在)")
            continue

        # 生成安全的文件名
        safe_name = (
            img_file.replace(".png", "")
            .replace("♠️", "spade")
            .replace("♠", "spade")
            .replace("♥️", "heart")
            .replace("♥", "heart")
            .replace("♣️", "club")
            .replace("♣", "club")
            .replace("♦️", "diamond")
            .replace("♦", "diamond")
        )
        base_name = f"poker_{safe_name}"

        # 复制图像到训练目录
        train_img = training_dir / f"{base_name}.png"
        shutil.copy(img_path, train_img)

        # 创建 box 文件
        box_file = training_dir / f"{base_name}.box"
        create_box_file(train_img, char, box_file)

        all_chars.add(char)
        training_files.append(base_name)
        try:
            print(f"  处理: {img_file} -> {char}")
        except UnicodeEncodeError:
            print(f"  处理: {safe_name} -> {char}")

    return training_dir, training_files, sorted(all_chars)


def convert_to_tiff(training_dir, base_name):
    """将 PNG 转换为 TIFF 格式"""
    png_file = training_dir / f"{base_name}.png"
    tiff_file = training_dir / f"{base_name}.tif"

    with Image.open(png_file) as img:
        # 转换为灰度图
        if img.mode != "L":
            img = img.convert("L")
        img.save(tiff_file, "TIFF")

    return tiff_file


def train_tesseract_model():
    """训练 Tesseract 模型并生成 traineddata"""
    training_dir, training_files, all_chars = create_training_data()

    if not training_files:
        print("没有找到训练数据!")
        return False

    lang = "poker"

    print(f"\n找到 {len(training_files)} 个训练文件")
    print(f"字符集: {all_chars}")

    # 步骤 1: 转换图像为 TIFF 格式
    print("\n[1/7] 转换图像格式...")
    for base_name in training_files:
        convert_to_tiff(training_dir, base_name)
        print(f"  转换: {base_name}.png -> {base_name}.tif")

    # 步骤 2: 生成 .tr 训练文件
    print("\n[2/7] 生成训练文件 (.tr)...")
    for base_name in training_files:
        tif_file = training_dir / f"{base_name}.tif"
        box_file = training_dir / f"{base_name}.box"

        cmd = ["tesseract", str(tif_file), str(training_dir / base_name), "--psm", "10", "nobatch", "box.train"]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"  训练: {base_name}")
            else:
                print(f"  警告 {base_name}: {result.stderr[:100]}")
        except Exception as e:
            print(f"  错误 {base_name}: {e}")

    # 步骤 3: 生成 unicharset
    print("\n[3/7] 生成字符集 (unicharset)...")
    unicharset_file = training_dir / "unicharset"

    # 使用 Tesseract 的 unicharset_extractor
    box_files = [str(training_dir / f"{name}.box") for name in training_files]

    try:
        cmd = ["unicharset_extractor"] + box_files
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            # 移动生成的 unicharset 到 training 目录
            if Path("unicharset").exists():
                shutil.move("unicharset", unicharset_file)
            print("  unicharset 生成成功")
        else:
            print(f"  警告: {result.stderr[:200]}")
            # 手动创建 unicharset
            create_manual_unicharset(unicharset_file, all_chars)
    except FileNotFoundError:
        print("  unicharset_extractor 未找到，手动创建...")
        create_manual_unicharset(unicharset_file, all_chars)

    # 步骤 4: 创建字体属性文件
    print("\n[4/7] 创建字体属性...")
    font_properties = training_dir / "font_properties"
    with open(font_properties, "w") as f:
        f.write("poker 0 0 0 0 0\n")
    print("  font_properties 创建成功")

    # 步骤 5: 聚类训练
    print("\n[5/7] 聚类训练...")

    # 收集所有 .tr 文件
    tr_files = list(training_dir.glob("*.tr"))
    if not tr_files:
        print("  错误: 没有找到 .tr 训练文件!")
        return False

    # 合并 .tr 文件
    combined_tr = training_dir / f"{lang}.tr"
    with open(combined_tr, "wb") as outfile:
        for tr_file in tr_files:
            with open(tr_file, "rb") as infile:
                outfile.write(infile.read())
    print(f"  合并 {len(tr_files)} 个训练文件")

    # 运行 mftraining
    try:
        cmd = ["mftraining", "-F", "font_properties", "-U", "unicharset", "-O", f"{lang}.unicharset", f"{lang}.tr"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=training_dir)
        if result.returncode == 0:
            print("  mftraining 完成")
        else:
            print(f"  警告 mftraining: {result.stderr[:200]}")
    except FileNotFoundError:
        print("  mftraining 未找到，跳过...")

    # 运行 cntraining
    try:
        cmd = ["cntraining", f"{lang}.tr"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=training_dir)
        if result.returncode == 0:
            print("  cntraining 完成")
        else:
            print(f"  警告 cntraining: {result.stderr[:200]}")
    except FileNotFoundError:
        print("  cntraining 未找到，跳过...")

    # 步骤 6: 重命名文件并创建 traineddata
    print("\n[6/7] 打包 traineddata...")

    # 重命名生成的文件
    files_to_rename = [
        ("inttemp", f"{lang}.inttemp"),
        ("normproto", f"{lang}.normproto"),
        ("pffmtable", f"{lang}.pffmtable"),
        ("shapetable", f"{lang}.shapetable"),
    ]

    for old_name, new_name in files_to_rename:
        old_path = training_dir / old_name
        new_path = training_dir / new_name
        if old_path.exists():
            old_path.rename(new_path)
            print(f"  重命名: {old_name} -> {new_name}")

    # 步骤 7: 创建最终的 traineddata
    print("\n[7/7] 生成 traineddata 文件...")

    traineddata_dir = Path("assets") / "traineddata"
    traineddata_dir.mkdir(parents=True, exist_ok=True)

    # 使用 combine_tessdata 创建 traineddata
    try:
        # 创建文件列表
        tessdata_files = [
            f"{lang}.unicharset",
            f"{lang}.inttemp",
            f"{lang}.normproto",
            f"{lang}.pffmtable",
            f"{lang}.shapetable",
        ]

        # 检查文件是否存在
        for f in tessdata_files:
            fpath = training_dir / f
            if not fpath.exists():
                print(f"  警告: {f} 不存在")

        # 运行 combine_tessdata
        cmd = ["combine_tessdata", f"{lang}."]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=training_dir)

        if result.returncode == 0:
            # 复制到目标目录
            src_traineddata = training_dir / f"{lang}.traineddata"
            dst_traineddata = traineddata_dir / f"{lang}.traineddata"

            if src_traineddata.exists():
                shutil.copy(src_traineddata, dst_traineddata)
                print(f"  成功: {dst_traineddata}")
                return True
            else:
                print(f"  错误: 未生成 traineddata 文件")
                return False
        else:
            print(f"  错误: {result.stderr[:300]}")
            return False

    except FileNotFoundError:
        print("  combine_tessdata 未找到")

        # 尝试手动打包
        return create_manual_traineddata(training_dir, traineddata_dir, lang, tessdata_files)


def create_manual_unicharset(unicharset_file, chars):
    """手动创建 unicharset 文件"""
    with open(unicharset_file, "w", encoding="utf-8") as f:
        f.write(f"{len(chars)}\n")
        for i, char in enumerate(sorted(chars)):
            # 格式: <char> <script> <id> <properties>
            f.write(f"{char} 0 0,0,0,0,0,0,0,0,0,0 Common {i}\n")
    print(f"  手动创建 unicharset: {len(chars)} 个字符")


def create_manual_traineddata(training_dir, traineddata_dir, lang, files):
    """手动创建 traineddata 文件（简化版）"""
    print("\n尝试手动创建 traineddata...")

    traineddata_file = traineddata_dir / f"{lang}.traineddata"

    # 创建一个简化的 traineddata（实际上是 zip 文件）
    with zipfile.ZipFile(traineddata_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in files:
            fpath = training_dir / fname
            if fpath.exists():
                zf.write(fpath, fname)
                print(f"  添加: {fname}")

    if traineddata_file.exists():
        print(f"  成功创建: {traineddata_file}")
        print("  注意: 这是简化版本，可能无法正常使用")
        return True
    return False


def create_config_files():
    """创建配置文件"""
    traineddata_dir = Path("assets") / "traineddata"
    traineddata_dir.mkdir(parents=True, exist_ok=True)

    # 创建 poker.config 文件
    # config_file = traineddata_dir / "poker.config"
    # with open(config_file, "w") as f:
    #     f.write("# Poker OCR Configuration\n")
    #     f.write("tessedit_char_whitelist AKQJT23456789SHCD\n")
    # print(f"创建配置文件: {config_file}")

    # # 创建用户词库
    # wordlist_file = traineddata_dir / "poker.wordlist"
    # with open(wordlist_file, "w") as f:
    #     for rank in "AKQJT23456789":
    #         f.write(f"{rank}\n")
    #     for suit in "SHCD":
    #         f.write(f"{suit}\n")
    #     for rank in "AKQJT23456789":
    #         for suit in "SHCD":
    #             f.write(f"{rank}{suit}\n")
    # print(f"创建词库: {wordlist_file}")


def main():
    """主函数"""
    print("=" * 60)
    print("Tesseract Poker OCR 训练工具")
    print("=" * 60)

    # 检查依赖
    try:
        from PIL import Image
    except ImportError:
        print("\n错误: 需要安装 Pillow!")
        print("运行: pip install Pillow")
        return

    # 检查 Tesseract
    try:
        result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True)
        print(f"\nTesseract 版本: {result.stdout.split()[1] if result.stdout else '未知'}")
    except FileNotFoundError:
        print("\n错误: 未找到 Tesseract!")
        print("请先安装 Tesseract OCR 并添加到 PATH")
        print("下载地址: https://github.com/tesseract-ocr/tesseract/releases")
        return

    # 创建配置文件
    print("\n" + "-" * 40)
    create_config_files()

    # 训练模型
    print("\n" + "-" * 40)
    success = train_tesseract_model()

    print("\n" + "=" * 60)
    if success:
        shutil.rmtree("assets/training", True)
        print("训练成功!")
        print(f"模型文件: assets/traineddata/poker.traineddata")
        print("\n使用方法:")
        print("  1. 将 poker.traineddata 复制到 Tesseract 的 tessdata 目录")
        print("  2. 或使用: pytesseract.image_to_string(img, lang='poker')")
    else:
        print("训练失败!")
        print("请检查错误信息并确保 Tesseract 训练工具已安装")
    print("=" * 60)


if __name__ == "__main__":
    main()
