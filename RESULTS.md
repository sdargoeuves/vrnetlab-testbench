
# TESTS Results

## Aruba OS-CX

pt: Passthrough (Transparent Management)
cfg: Config via binds

| image | pt | cfg | result |
| ----- | -- | --- | ------ |
| vrnetlab/aruba_arubaos-cx:10_16_1060 | no | no | PASS |
| vrnetlab/aruba_arubaos-cx:10_16_1060 | no | yes | PASS |
| vrnetlab/aruba_arubaos-cx:10_16_1060 | yes | no | PASS |
| vrnetlab/aruba_arubaos-cx:10_16_1060 | yes | yes | PASS |

## EXOS

pt: Passthrough (Transparent Management)
cfg: Config via binds

Tested on AMD CPU, passing `env.QEMU_CPU: "core2duo"`

| image | pt | cfg | result | comments |
| ----- | -- | --- | ------ | -------- |
| vrnetlab/extreme_exos:33.6.1.14 | no | no | PASS | |
| vrnetlab/extreme_exos:33.6.1.14 | no | yes | PASS | |
| vrnetlab/extreme_exos:33.6.1.14 | yes | no | PASS | |
| vrnetlab/extreme_exos:33.6.1.14 | yes | yes | PASS | |
| vrnetlab/extreme_exos:33.1.1.31 | no | no | FAIL | OK on Intel CPU |
| vrnetlab/extreme_exos:33.1.1.31 | no | yes | FAIL | OK on Intel CPU |
| vrnetlab/extreme_exos:33.1.1.31 | yes | no | FAIL | OK on Intel CPU |
| vrnetlab/extreme_exos:33.1.1.31 | yes | yes | FAIL | OK on Intel CPU |
| vrnetlab/extreme_exos:32.7.2.19 | no | no | PASS | |
| vrnetlab/extreme_exos:32.7.2.19 | no | yes | PASS | |
| vrnetlab/extreme_exos:32.7.2.19 | yes | no | PASS | |
| vrnetlab/extreme_exos:32.7.2.19 | yes | yes | PASS | |
| vrnetlab/extreme_exos:32.6.3.126 | no | no | PASS | |
| vrnetlab/extreme_exos:32.6.3.126 | no | yes | PASS | |
| vrnetlab/extreme_exos:32.6.3.126 | yes | no | PASS | |
| vrnetlab/extreme_exos:32.6.3.126 | yes | yes | PASS | |

## VOSS

pt: Passthrough (Transparent Management)
cfg: Config via binds

| image | pt | cfg | result |
| ----- | -- | --- | ------ |
| vrnetlab/extreme_voss:8.10.1.0 | no | no | PASS |
| vrnetlab/extreme_voss:8.10.1.0 | no | yes | PASS |
| vrnetlab/extreme_voss:8.10.1.0 | yes | no | PASS |
| vrnetlab/extreme_voss:8.10.1.0 | yes | yes | PASS |
| vrnetlab/extreme_voss:9.3.1.0 | no | no | PASS |
| vrnetlab/extreme_voss:9.3.1.0 | no | yes | PASS |
| vrnetlab/extreme_voss:9.3.1.0 | yes | no | PASS |
| vrnetlab/extreme_voss:9.3.1.0 | yes | yes | PASS |
| vrnetlab/extreme_voss:9.4.0.0 | no | no | PASS |
| vrnetlab/extreme_voss:9.4.0.0 | no | yes | PASS |
| vrnetlab/extreme_voss:9.4.0.0 | yes | no | PASS |
| vrnetlab/extreme_voss:9.4.0.0 | yes | yes | PASS |

## ASAv

| image | pt | cfg | result |
| ----- | -- | --- | ------ |
| vrnetlab/cisco_asav:9-18-1 | no | no | PASS |
| vrnetlab/cisco_asav:9-18-1 | no | yes | PASS |
| vrnetlab/cisco_asav:9-18-1 | yes | no | PASS |
| vrnetlab/cisco_asav:9-18-1 | yes | yes | PASS |
| vrnetlab/cisco_asav:9-24-1 | no | no | PASS |
| vrnetlab/cisco_asav:9-24-1 | no | yes | PASS |
| vrnetlab/cisco_asav:9-24-1 | yes | no | PASS |
| vrnetlab/cisco_asav:9-24-1 | yes | yes | PASS |

Also tested: Change of default credentials - PASS

## VSRX

| image | pt | cfg | result |
| ----- | -- | --- | ------ |
| vrnetlab/juniper_vsrx:22.3R1.11 | no | no | PASS |
| vrnetlab/juniper_vsrx:22.3R1.11 | no | yes | PASS |
| vrnetlab/juniper_vsrx:22.3R1.11 | yes | no | PASS |
| vrnetlab/juniper_vsrx:22.3R1.11 | yes | yes | PASS |

Also tested: Change of default credentials - PASS
