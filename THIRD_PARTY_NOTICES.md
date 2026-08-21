# Third-Party Notices

GHand Python SDK is distributed under the Apache License 2.0.

This SDK depends on third-party open-source software. Each third-party component
remains subject to its own license terms. Local copies of the referenced license
texts are provided in the `LICENSES/` directory for packaging and audit use.

## Core Runtime Dependencies

| Component | Version range | License | Purpose | License text |
| --- | --- | --- | --- | --- |
| pysoem | `>=1.0.2,<2.0.0` | MIT | EtherCAT communication | `LICENSES/pysoem-MIT.txt` |
| pymodbus | `>=3.0.0` | BSD-3-Clause | Modbus/RS-485 protocol support | `LICENSES/pymodbus-BSD-3-Clause.txt` |
| pyserial | `>=3.5` | BSD-3-Clause | Serial transport support | `LICENSES/pyserial-BSD-3-Clause.txt` |
| netifaces | `>=0.11.0` | MIT-style | Network interface discovery | `LICENSES/netifaces-LICENSE.txt` |
| numpy | `>=1.24.0` | BSD-3-Clause | Numeric data handling | `LICENSES/numpy-BSD-3-Clause.txt` |
| numpy-stl | `>=3.1.0` | BSD-3-Clause | STL mesh loading | `LICENSES/numpy-stl-BSD-3-Clause.txt` |
| pandas | `>=2.0.0` | BSD-3-Clause | Collision data table handling | `LICENSES/pandas-BSD-3-Clause.txt` |

## Notes

- The Python SDK does not bundle SOEM source code directly. EtherCAT access is
  provided through the PySOEM Python package.
- PySOEM is constrained to `>=1.0.2,<2.0.0` so the SDK uses the MIT-licensed
  PySOEM release line.
- Collision detection dependencies are part of the core install.
