# 第三方组件声明（THIRD PARTY NOTICES）

本仓库按原样再分发下列第三方组件，未做任何修改。

## Equalizer APO 1.4.2

- 文件：`assets/EqualizerAPO-x64-1.4.2.exe`（构建时会随程序一起打包）
- 来源：https://sourceforge.net/projects/equalizerapo/files/1.4.2/
- 大小：11,980,366 字节
- SHA-256：`7403be7427bbe1936a40dded082829b6e217fc4f5990fee5cba501f0ae055afa`
  （与 SourceForge 发布页公布的校验值一致，证明为官方未修改安装包）
- 许可证：GPL-2.0（Copyright (C) 2025 Peter Verbeek / Team Equalizer APO）

本程序只调用该安装包的静默安装（NSIS `/S`）能力，并以只读方式访问其
`config\config.txt` 与注册表项 `HKLM\SOFTWARE\EqualizerAPO\Child APOs`，
不包含、不修改其任何源码或二进制。

按 GPL-2.0 的要求，Equalizer APO 的源代码可在其官方项目主页获取：
https://sourceforge.net/projects/equalizerapo/
（GPL-2.0 第 3 条的“源码随二进制分发或提供书面获取承诺”，此处以上游公开
源码链接满足；如链接失效，可向本项目作者索取副本。）

## ffmpeg

- 来源：`imageio-ffmpeg` 随包附带的 Windows 构建（构建时复制到 `assets/ffmpeg.exe`）
- 许可证：LGPL-2.1（若采用 GPL 构建则为 GPL）；源码见 https://ffmpeg.org/download.html
- 本程序仅以独立子进程方式调用其命令行，未链接其库代码。
