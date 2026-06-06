# Controllers & Analysers

[English](README.md) | **绠€浣撲腑鏂?*

鐗堟湰锛歚v16.2.260606.2137`

Controllers & Analysers 鏄竴涓?wxPython 妗岄潰绉戠爺杞欢锛岀敤浜庡疄楠屾帶鍒跺拰绉戝鏁版嵁鍒嗘瀽銆傚畠鍖呭惈 AFM/KPFM Keithley 鎺у埗銆丆PD 鍥惧儚鍒嗘瀽銆丄PS/DWF/SPV 鍒嗘瀽銆乀PC 婵€鍏変簩鏋佺鎺у埗銆丷aman 鍩虹嚎鏍℃銆丷aman Mapping銆丷aman Insitu EChem 搴忓垪鍒嗘瀽锛屼互鍙?Raman Electrical 鐢靛 CSV 棰勮銆?
## 鏂囨。

璇︾粏鏂囨。鎸夎瑷€鍜岃鑰呮媶鍒嗭細

- [涓枃鏂囨。绱㈠紩](docs/zh-CN/index.md)
- [English documentation index](docs/en/index.md)
- [Coding-agent instructions](AGENTS.md)

寤鸿鍏堣锛?
- [椤圭洰姒傝](docs/zh-CN/project-overview.md)
- [鏋舵瀯璇存槑](docs/zh-CN/architecture.md)
- [宸ヤ綔鍖烘寚鍗梋(docs/zh-CN/workspace-guide.md)
- [寮€鍙戣€呮寚鍗梋(docs/zh-CN/developer-guide.md)
- [娴嬭瘯璇存槑](docs/zh-CN/testing.md)
- [鐗堟湰瑙勫垯](docs/zh-CN/versioning.md)

## 涓昏宸ヤ綔鍖?
| 宸ヤ綔鍖?| 涓昏鍔熻兘 |
| --- | --- |
| AFM/KPFM Controller | Keithley 鐢垫祦婧愭帶鍒躲€佺數娴?鍏夊己妯″紡銆丵uick Test銆丷ecurrent/Step 鏃跺簭銆佸嚱鏁版洸绾裤€佹牎鍑嗐€佸疄鏃剁數鍘嬨€乻ource CSV 鍜?Keithley CSV |
| AFM/KPFM Analysis | CPD 鍥惧儚銆丆PD/energy銆丠OPG 鎷熷悎銆佸厜鐓у尯鍩熴€乵ask銆佺洿鏂瑰浘銆乺ow/time profiles |
| APS/DWF/SPV | APS銆丏WF銆亀orkfunction銆丏OS銆丼PV 鍒嗘瀽鍜屽鍑?|
| TPC Control | 绾?缁挎縺鍏変簩鏋佺鐢垫祦鎺у埗 |
| Raman Baseline | TXT 璇诲彇銆乣asPLS`銆乣drPLS`銆乣Polynomial/backcor`銆佹牎姝ｈ氨瀵煎嚭 |
| Raman Mapping | WDF/TXT mapping 璇诲彇銆佸钩鍧?褰掍竴鍖栥€乺aw/location/selected 棰勮銆侀€変腑璋卞鍑哄拰浼犻€?|
| Raman Insitu EChem | 搴忓垪/WDF 璇诲彇銆佸嘲绐楀彛銆佸嘲浣嶃€佸嘲寮恒€佸綊涓€鍖栨瘮鍊笺€丳NG/CSV 瀵煎嚭 |
| Raman Electrical | 鐢靛 CSV 璇诲彇銆佸洓閫氶亾 raw preview銆乂_Gate/V_Drain 鍙岃酱棰勮銆乸ulse summary 琛?|

## 瀹夎

宸茬煡鍙敤鐜锛?
- Windows
- Python 3.13.x
- wxPython 4.2.x
- pyserial 3.5
- numpy
- matplotlib
- scipy
- Pillow
- `.wdf` Raman 鏂囦欢闇€瑕?`renishawWiRE`

鍦ㄩ」鐩牴鐩綍杩愯锛?
```cmd
pip install -e .
```

## 杩愯

```cmd
python run_ca_app.py
```

绐楀彛鏍囬搴旀樉绀猴細

```text
Controller & Analysers v16.2.260606.2137
```

## 娴嬭瘯

```cmd
python -m compileall src tests
python -m unittest discover -s tests
```

榛樿娴嬭瘯涓嶈繛鎺ョ‖浠躲€備换浣曠湡瀹?Keithley 鎴栨縺鍏変簩鏋佺娴嬭瘯閮藉繀椤诲厛鐢辩敤鎴锋槑纭‘璁ゅ畨鍏ㄧ數娴佸拰 compliance 璁剧疆銆?
## 鐗堟湰瑙勫垯

v16 绯诲垪浣跨敤锛?
```text
v<major>.<minor>.<YYMMDD>.<HHMM>
```

`v16.2.260606.2137` 涓紝`v16` 鏄ぇ鐗堟湰锛宍2` 鏄?v16 鍐呭皬鐗堟湰锛宍260606` 鏄棩鏈燂紝`2137` 鏄?coding agent 淇敼椤圭洰鐨?24 灏忔椂鏃堕棿銆傝瑙?[鐗堟湰瑙勫垯](docs/zh-CN/versioning.md)銆?

