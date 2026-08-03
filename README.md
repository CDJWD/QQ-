# QQ 群相册下载桌面应用

把 QQ 群相册批量下载封装成桌面程序：内置浏览器登录、勾选相册、ZIP / 原图保存，并支持断点续传。

## 环境要求

- Windows 10/11
- Python 3.10+
- 能访问 `h5.qzone.qq.com`

## 安装

在项目根目录（`群相册下载`）执行：

```bash
pip install -r requirements-app.txt
```

## 运行

```bash
python main.py
```

或：

```bash
python -m app.main
```

## 使用步骤

1. 输入 QQ 群号，点击「打开相册并登录」
2. 在内置浏览器中登录有该群权限的 QQ 账号
3. 状态显示「已登录，可以开始处理」后，点击「开始处理」
4. 勾选要下载的相册，选择保存目录与方式：
   - **ZIP**：按相册打包；超过约 500 张会自动分卷到 `{相册名}_parts/`
   - **照片**：每个相册一个文件夹，保存图片/视频原链
5. 开始下载。可暂停 / 停止；进度写入  
   `{保存目录}/.qq_album_task/{群号}/state.json`  
   下次用相同目录继续即可跳过已完成项

## 打包（可选）

```bash
pip install pyinstaller
pyinstaller -F -w -n QQ群相册下载 ^
  --collect-all PySide6 ^
  --hidden-import PySide6.QtWebEngineWidgets ^
  app/main.py
```

生成的可执行文件在 `dist/`。首次打包体积较大（含 Chromium）。

## 说明

- 登录态保存在内置 Chromium 配置中，关闭应用后通常仍可保持一段时间。
- 超大视频相册分卷 ZIP 体积可能很大，请预留磁盘空间。
- 本工具仅供已授权成员备份自己群相册使用。
