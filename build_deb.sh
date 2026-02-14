#!/bin/bash

# --- 配置信息 ---
APP_NAME="cabin-stopwatch"
VERSION="1.5.1"
MAINTAINER="xiandeshen@foxmail.com"
PYTHON_SCRIPT="main.py"  # 请确保你的代码文件名叫 main.py

# --- 1. 创建清理旧目录 ---
echo "正在准备构建目录..."
BUILD_DIR="deb_build_tmp"
rm -rf $BUILD_DIR
mkdir -p $BUILD_DIR/DEBIAN
mkdir -p $BUILD_DIR/usr/bin
mkdir -p $BUILD_DIR/usr/share/applications

# --- 2. 复制并处理 Python 脚本 ---
echo "正在处理脚本..."
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "错误: 找不到 $PYTHON_SCRIPT 文件！"
    exit 1
fi

cp "$PYTHON_SCRIPT" $BUILD_DIR/usr/bin/$APP_NAME
chmod +x $BUILD_DIR/usr/bin/$APP_NAME

# --- 3. 生成 DEBIAN/control 文件 ---
echo "正在生成 control 文件..."
cat <<EOF > $BUILD_DIR/DEBIAN/control
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-gi, python3-psutil, gir1.2-appindicator3-0.1
Maintainer: $MAINTAINER
Description: 舱端专用秒表，支持 VokoScreen 录制检测。
EOF

# --- 4. 生成桌面快捷方式 ---
echo "正在生成桌面快捷方式..."
cat <<EOF > $BUILD_DIR/usr/share/applications/$APP_NAME.desktop
[Desktop Entry]
Name=舱端专用秒表
Comment=Stopwatch for Cabin with VokoScreen Detection
Exec=/usr/bin/$APP_NAME
Icon=cabin_stopwatch_samsung_clock
Type=Application
Categories=Utility;
Terminal=false
EOF

# --- 5. 设置权限并打包 ---
echo "正在构建 .deb 包..."
chmod -R 755 $BUILD_DIR
dpkg-deb --build $BUILD_DIR "${APP_NAME}_${VERSION}_all.deb"

# --- 6. 清理 ---
rm -rf $BUILD_DIR
echo "--------------------------------------"
echo "打包完成！文件名为: ${APP_NAME}_${VERSION}_all.deb"
echo "你可以使用以下命令安装:"
echo "sudo apt install ./${APP_NAME}_${VERSION}_all.deb"
