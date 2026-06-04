# ZLG CANFD 驱动

本项目依赖 ZLG（周立功）USB-CANFD 设备的官方驱动，请将驱动文件放置于此目录下。

## 获取驱动文件

从 [ZLG 官网](https://www.zlg.cn/) 下载对应型号的 CANFD 设备驱动/SDK，解压后即可找到以下文件。

## 所需文件

| 文件/目录 | 说明 |
|---|---|
| `zlgcan.dll` | 主驱动 DLL |
| `kerneldlls/` | 依赖 DLL 子目录，**必须与 `zlgcan.dll` 一并复制** |

## 目录结构

放置完成后，本目录结构应如下所示：

```
drivers/zlgcan/
├── README.md
├── README.zh.md
├── zlgcan.dll
└── kerneldlls/
    ├── USBCANFD.dll
    ├── CANFDNET.dll
    └── ...（其他依赖 DLL）
```

> 注意：缺少 `kerneldlls/` 会导致 `zlgcan.dll` 加载失败。
