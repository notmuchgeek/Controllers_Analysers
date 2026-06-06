# 妯″潡鍦板浘

鐗堟湰锛歚v16.2.260606.2137`

## 鏍圭洰褰?
- `run_ca_app.py`锛氫粠婧愮爜鍚姩绋嬪簭銆?- `pyproject.toml`锛氬寘鍏冩暟鎹拰渚濊禆銆?- `README.md`銆乣README.zh-CN.md`銆乣AGENTS.md`锛氫汉绫诲拰 coding agent 鍏ュ彛銆?
## 搴旂敤灞?
- `src/ca_app/app.py`锛氬垱寤?wx app銆?- `src/ca_app/constants.py`锛氬叡浜粯璁ゅ€笺€?- `src/ca_app/__init__.py`锛氱増鏈厓鏁版嵁銆?
## 涓荤獥鍙?
- `src/ca_app/gui/main_frame.py`锛氫富 frame銆佽彍鍗曘€亀orkspace銆乺estore銆乤bout銆佺獥鍙ｆ爣棰樸€?
## Panels

- `afm_kpfm_panel.py`锛欰FM/KPFM notebook銆?- `afm_controller_panel.py`锛欿eithley 鎺у埗鍣ㄣ€?- `afm_analysis_panel.py`锛欳PD 鍥惧儚鍒嗘瀽銆?- `aps_panel.py`锛欰PS/DWF/DOS/SPV銆?- `raman_panel.py`锛歊aman 鍥涗釜瀛愬伐浣滃尯銆?- `tpc_panel.py`锛歍PC 鎺у埗銆?
## Core

- `intensity_profile_tools.py`锛氭牎鍑嗐€佸嚱鏁拌〃杈惧紡鍜?profile銆?- `calibration_models.py`锛氭牎鍑嗘ā鍨嬪鍏ラ潰銆?- `function_profiles.py`锛氬嚱鏁版洸绾垮鍏ラ潰銆?- `raman_baseline.py`锛歊aman baseline銆?- `raman_mapping.py`锛歊aman mapping銆?- `raman_insitu_echem.py`锛歊aman sequence 鍒嗘瀽銆?
## Hardware / Runtime / IO

- `hardware/keithley_serial.py`锛欿eithley 涓插彛鍜?SCPI 鍘熻銆?- `runtime/`锛氭湭鏉?worker/service 鎶藉彇鍖哄煙銆?- `io/`锛氭湭鏉ュ鍏?瀵煎嚭杈圭晫銆?
## Tests

- `tests/`锛氶潪纭欢鑷姩娴嬭瘯銆?
