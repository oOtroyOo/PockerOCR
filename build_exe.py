"""
打包 PokerOCR 为可执行文件
"""

import os
import sys
import shutil
import subprocess


def clean_build():
    """清理构建目录"""
    dirs_to_remove = ["build", "dist", "__pycache__"]
    for d in dirs_to_remove:
        if os.path.exists(d):
            print(f"清理 {d}...")
            shutil.rmtree(d)

    # 清理 .pyc 文件
    for root, dirs, files in os.walk("."):
        for f in files:
            if f.endswith(".pyc"):
                os.remove(os.path.join(root, f))
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d))


def build_exe():
    """使用 PyInstaller 打包"""
    print("开始打包...")

    # 确保资源目录存在
    os.makedirs("dist/PokerOCR/assets", exist_ok=True)

    # 运行 PyInstaller
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "poker_ocr.spec"]

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        print("打包失败!")
        return False

    print("打包完成!")
    return True


def copy_additional_files():
    """复制额外文件到输出目录"""
    dest = "dist/PokerOCR"

    # 复制配置文件
    if os.path.exists("config.yaml"):
        shutil.copy("config.yaml", dest)
        print("复制 config.yaml")

    # 复制样式文件
    if os.path.exists("styles/style.qss"):
        os.makedirs(f"{dest}/styles", exist_ok=True)
        shutil.copy("styles/style.qss", f"{dest}/styles/")
        print("复制 style.qss")

    # 复制资源文件
    if os.path.exists("assets"):
        if os.path.exists(f"{dest}/assets"):
            shutil.rmtree(f"{dest}/assets")
        shutil.copytree("assets", f"{dest}/assets")
        print("复制 assets 目录")

    # 创建截图目录
    os.makedirs(f"{dest}/screenshot", exist_ok=True)
    print("创建 screenshot 目录")


def main():
    """主函数"""
    print("=" * 50)
    print("PokerOCR 打包工具")
    print("=" * 50)
    # 清理
    clean_build()

    # 打包
    if build_exe():
        copy_additional_files()
        dirs_to_remove = ["build", "__pycache__"]
        for d in dirs_to_remove:
            if os.path.exists(d):
                print(f"清理 {d}...")
                shutil.rmtree(d)
        print("\n" + "=" * 50)
        print("打包成功!")
        print(f"输出目录: {os.path.abspath('dist/PokerOCR')}")
        print("=" * 50)
    else:
        print("\n打包失败!")
        sys.exit(1)


if __name__ == "__main__":
    main()
