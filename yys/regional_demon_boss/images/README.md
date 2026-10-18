# 地域鬼王识别模板

模板均来自录制 `regional_demon_boss/20260907T130329Z-9e74a0d8` 的 1136×640 客户区帧；测试使用 `tests/fixtures/regional_demon_boss/` 中对应的脱敏帧。

| 模板 | 来源帧 | 裁剪区域 `(x0,y0,x1,y1)` | 生产搜索区域 |
| --- | --- | --- | --- |
| `home_marker.bmp` | `frames/000007-before.png` | `(395,65,495,195)` | `(0,0,1136,640)` |
| `home_marker_night.bmp` | `diagnostics/2026-09-12-2225/current_home.png` | `(507,94,607,197)` | `(0,0,1136,640)` |
| `exploration_marker.bmp` | `frames/000008-before.png` | `(530,525,640,640)` | `(480,480,700,640)` |
| `map_initial.bmp` | `timeline-014.png` | `(440,0,720,58)` | `(400,0,750,80)` |
| `map_target.bmp` | `timeline-018.png` | `(650,90,850,340)` | `(600,60,900,380)`；匹配中心加 `(11,41)` 后点击录制头像 `(761,256)` |
| `detail_title.bmp` | `frames/000012-before.png` | `(75,35,275,90)` | `(50,20,320,110)` |
| `detail_boss.bmp` | `frames/000012-before.png` | `(550,60,630,175)` | `(520,40,660,200)` |
| `challenge.bmp` | `frames/000012-before.png` | `(960,430,1136,575)` | `(900,380,1136,620)`；匹配中心加 `(-21,5)` 后点击 `(1027,507)` |
| `preparation.bmp` | `timeline-025.png` | `(970,430,1136,640)` | `(900,380,1136,640)` |
| `battling_early.bmp` | `timeline-035.png` | `(0,0,190,80)` | `(0,0,250,120)`；同一张生产模板已验证覆盖 `timeline-060/095.png` 的中、后段战斗画面 |
| `result_success.bmp` | `timeline-101.png` | `(420,495,930,640)` | `(350,430,1000,640)` |
| `reward.bmp` | `frames/000014-after.png` | `(190,115,750,570)` | `(150,80,800,600)` |
| `settlement_continue.bmp` | `timeline-101.png` | `(430,590,710,640)` | `(350,540,800,640)` |

本次录制没有失败结算，生产脚本不启用失败模板。未知结算会安全失败，不推断为胜利。
