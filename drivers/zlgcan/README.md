# ZLG CANFD Driver

This project depends on the official driver for ZLG (Zhou Ligong) USB-CANFD devices. Place the driver files in this directory.

## Obtain the Driver Files

Download the driver/SDK for your CANFD device model from the [ZLG website](https://www.zlg.cn/). The required files can be found in the extracted package.

## Required Files

| File / Directory | Description |
|---|---|
| `zlgcan.dll` | Main driver DLL |
| `kerneldlls/` | Dependency DLL subdirectory, **must be copied together with `zlgcan.dll`** |

## Directory Layout

After placing the files, the directory structure should look like this:

```
drivers/zlgcan/
├── README.md
├── README.zh.md
├── zlgcan.dll
└── kerneldlls/
    ├── USBCANFD.dll
    ├── CANFDNET.dll
    └── ... (other dependency DLLs)
```

> Note: Missing `kerneldlls/` will cause `zlgcan.dll` to fail loading.
