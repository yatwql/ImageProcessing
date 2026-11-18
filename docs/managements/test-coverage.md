# 测试覆盖率与分组统计

> 版本：v0.1

本文件由 `tools/coverage_report.py --write` 生成，数据取自 `reports/coverage.xml` 与
`reports/junit.xml`（`tools/check_all.py` 全量模式产出）。改完用例或实现后重新生成即可，
不要手改数字。

> 生成时间：2026-11-18 14:24　|　命令：`.venv/bin/python tools/check_all.py`

## 1. 总览

| 指标 | 数值 | 门槛 | 结论 |
| --- | ---: | ---: | --- |
| 行覆盖率 | 85.7% | ≥ 75.0% | ✅ |
| 用例总数 | 446 | — | — |
| 通过 | 446 | = 总数 | ✅ |
| 跳过 | 0（0.0%） | ≤ 15.0% | ✅ |
| 用例总耗时 | 73.8s | — | — |

## 2. 模块覆盖率（高风险模块带门槛）

| 模块 | 覆盖率 | 覆盖行 / 总行 | 门槛 | 结论 |
| --- | ---: | ---: | ---: | --- |
| `cli/__main__.py` | 0.0% | 0 / 4 | — | — |
| `tui/__main__.py` | 0.0% | 0 / 4 | — | — |
| `bootstrap.py` | 57.8% | 59 / 102 | — | — |
| `tui/ui.py` | 60.5% | 72 / 119 | — | — |
| `launch.py` | 71.9% | 23 / 32 | — | — |
| `tui/ui_base.py` | 78.1% | 75 / 96 | — | — |
| `tui/ui_actions.py` | 80.0% | 180 / 225 | ≥ 80.0% | ✅ |
| `tui/ui_input.py` | 81.0% | 81 / 100 | — | — |
| `tui/app.py` | 85.4% | 403 / 472 | ≥ 80.0% | ✅ |
| `cli/main.py` | 85.8% | 188 / 219 | — | — |
| `core/audit.py` | 89.0% | 153 / 172 | ≥ 85.0% | ✅ |
| `core/render.py` | 89.5% | 85 / 95 | ≥ 85.0% | ✅ |
| `core/image.py` | 89.8% | 88 / 98 | ≥ 85.0% | ✅ |
| `core/style.py` | 90.0% | 153 / 170 | — | — |
| `core/fonts.py` | 90.1% | 136 / 151 | — | — |
| `cli/log_query.py` | 92.0% | 46 / 50 | — | — |
| `core/ocr.py` | 92.5% | 37 / 40 | — | — |
| `core/edit.py` | 93.4% | 114 / 122 | ≥ 85.0% | ✅ |
| `core/options.py` | 93.9% | 46 / 49 | ≥ 90.0% | ✅ |
| `tui/ui_draw.py` | 94.1% | 222 / 236 | ≥ 85.0% | ✅ |
| `config.py` | 95.1% | 77 / 81 | — | — |
| `core/match.py` | 95.2% | 60 / 63 | ≥ 90.0% | ✅ |
| `__init__.py` | 100.0% | 4 / 4 | — | — |
| `version.py` | 100.0% | 5 / 5 | — | — |
| `core/__init__.py` | 100.0% | 12 / 12 | — | — |
| `core/errors.py` | 100.0% | 2 / 2 | — | — |
| `core/jobs.py` | 100.0% | 47 / 47 | — | — |
| `tui/browse.py` | 100.0% | 33 / 33 | — | — |

## 3. 包级汇总

| 包 | 文件数 | 覆盖率 |
| --- | ---: | ---: |
| `.` | 5 | 75.0% |
| `cli` | 3 | 85.7% |
| `core` | 12 | 91.4% |
| `tui` | 8 | 83.0% |

## 4. 场景测试分组（293 例）

| 分组 | 用例数 | 通过 | 耗时 | 覆盖的点 |
| --- | ---: | ---: | ---: | --- |
| `cli.test_arguments.ArgumentGuards` | 5 | 5 | 0.0s | — |
| `cli.test_arguments.MappingLoading` | 5 | 5 | 0.0s | — |
| `cli.test_arguments.ParserDefaults` | 3 | 3 | 0.0s | — |
| `cli.test_arguments.VersionFlag` | 1 | 1 | 0.0s | — |
| `cli.test_batch_directory.BatchDirectoryRun` | 9 | 9 | 6.2s | — |
| `cli.test_demo_assets.DemoAssets` | 2 | 2 | 0.0s | — |
| `cli.test_demo_assets.DemoCliFlows` | 5 | 5 | 7.5s | — |
| `cli.test_entry_smoke.EntryPoints` | 8 | 8 | 0.8s | — |
| `cli.test_entry_smoke.ScriptLaunchers` | 2 | 2 | 0.2s | — |
| `cli.test_launch_env.AutoSetupSwitch` | 3 | 3 | 0.0s | — |
| `cli.test_launch_env.BootstrapEntry` | 2 | 2 | 0.0s | — |
| `cli.test_launch_env.LaunchChannels` | 4 | 4 | 0.0s | — |
| `cli.test_launch_env.MissingModules` | 3 | 3 | 0.2s | — |
| `cli.test_log_query_cli.LogQueryCli` | 8 | 8 | 0.0s | — |
| `cli.test_single_image.SingleImageOutputPixels` | 1 | 1 | 0.7s | — |
| `cli.test_single_image.SingleImageRun` | 13 | 13 | 8.4s | — |
| `cli.test_single_image.VersionBanner` | 1 | 1 | 2.8s | — |
| `core.test_cancel_pipeline.ReplacementCancel` | 4 | 4 | 0.4s | — |
| `core.test_log_query.LogQuery` | 9 | 9 | 0.0s | — |
| `core.test_mapping_rules.BlockOverrides` | 4 | 4 | 0.0s | — |
| `core.test_mapping_rules.MappingRules` | 8 | 8 | 0.0s | — |
| `core.test_version_display.CodeUpdatedDate` | 5 | 5 | 0.0s | — |
| `core.test_version_display.VersionInDocs` | 1 | 1 | 0.0s | — |
| `core.test_version_display.VersionIsLogged` | 1 | 1 | 0.0s | — |
| `core.test_version_display.VersionIsPrinted` | 4 | 4 | 2.6s | — |
| `core.test_version_display.VersionSource` | 2 | 2 | 0.0s | — |
| `core.test_write_audit_log.AuditEntryFields` | 7 | 7 | 0.0s | — |
| `core.test_write_audit_log.AuditLogFile` | 9 | 9 | 0.5s | — |
| `core.test_write_audit_log.CliWritesAuditLog` | 9 | 9 | 8.3s | — |
| `core.test_write_audit_log.TuiWritesAuditLog` | 7 | 7 | 5.2s | — |
| `tui.test_apply_and_batch.ApplyFlow` | 12 | 12 | 6.0s | — |
| `tui.test_directory_browsing.BrowseKeys` | 3 | 3 | 0.1s | — |
| `tui.test_directory_browsing.DefaultInput` | 2 | 2 | 0.0s | — |
| `tui.test_directory_browsing.DirectoryRows` | 7 | 7 | 0.0s | — |
| `tui.test_interaction_edges.BatchEdges` | 3 | 3 | 0.3s | — |
| `tui.test_interaction_edges.BrowsingEdges` | 4 | 4 | 0.0s | — |
| `tui.test_interaction_edges.KeyEdges` | 5 | 5 | 0.1s | — |
| `tui.test_interaction_edges.MappingEdits` | 4 | 4 | 0.0s | — |
| `tui.test_interaction_edges.SettingParsing` | 8 | 8 | 0.0s | — |
| `tui.test_key_dispatch.BackgroundLoading` | 2 | 2 | 0.1s | — |
| `tui.test_key_dispatch.BatchInterrupt` | 2 | 2 | 0.0s | — |
| `tui.test_key_dispatch.MainPanelKeys` | 17 | 17 | 0.3s | — |
| `tui.test_key_dispatch.MapPanelKeys` | 5 | 5 | 0.0s | — |
| `tui.test_key_dispatch.NonAsciiDigits` | 2 | 2 | 0.0s | — |
| `tui.test_key_dispatch.NonBlockingInput` | 4 | 4 | 0.0s | — |
| `tui.test_key_dispatch.RescanDirectory` | 3 | 3 | 0.0s | — |
| `tui.test_key_dispatch.SettingsPanelKeys` | 4 | 4 | 0.0s | — |
| `tui.test_keys_and_navigation.CliLikeArguments` | 2 | 2 | 0.0s | — |
| `tui.test_keys_and_navigation.KeySequenceDecoding` | 4 | 4 | 0.0s | — |
| `tui.test_keys_and_navigation.ListNavigation` | 11 | 11 | 0.1s | — |
| `tui.test_layout_rendering.BorderDrawing` | 3 | 3 | 0.0s | — |
| `tui.test_layout_rendering.LayoutRendering` | 6 | 6 | 0.0s | — |
| `tui.test_layout_rendering.RefreshFlush` | 3 | 3 | 0.0s | — |
| `tui.test_layout_rendering.ResponsiveLayout` | 8 | 8 | 0.0s | — |
| `tui.test_layout_rendering.WindowsStyleAcs` | 1 | 1 | 0.0s | — |
| `tui.test_mapping_panel.MappingPanel` | 5 | 5 | 0.1s | — |
| `tui.test_screen_snapshots.ScreenSnapshots` | 1 | 1 | 0.1s | — |
| `tui.test_screen_snapshots.SnapshotSanity` | 2 | 2 | 0.1s | — |
| `tui.test_session_state.TuiSessionState` | 4 | 4 | 0.0s | — |
| `tui.test_settings_panel.SettingsPanel` | 9 | 9 | 0.1s | — |
| `tui.test_tui_real_terminal.RealTerminalSmoke` | 2 | 2 | 10.1s | — |

## 5. 单元测试分组（132 例）

| 分组 | 用例数 | 通过 | 耗时 | 覆盖的点 |
| --- | ---: | ---: | ---: | --- |
| `core.background.test_background_types` | 7 | 7 | 0.1s | — |
| `core.color.test_alpha_channel` | 4 | 4 | 0.6s | — |
| `core.color.test_text_colors` | 2 | 2 | 2.0s | — |
| `core.font.test_font_pool` | 16 | 16 | 0.7s | — |
| `core.format.test_image_read_write` | 16 | 16 | 0.0s | — |
| `core.layout.test_text_layout` | 5 | 5 | 3.5s | — |
| `core.pipeline.test_replace_pipeline` | 3 | 3 | 2.4s | — |
| `core.primitives.test_erasing_and_drawing` | 12 | 12 | 0.1s | — |
| `core.primitives.test_inpaint_radius` | 6 | 6 | 0.0s | — |
| `core.primitives.test_rendering_primitives` | 4 | 4 | 0.0s | — |
| `core.primitives.test_style_analysis` | 3 | 3 | 1.5s | — |
| `core.test_feature_edges.AreaJobs` | 3 | 3 | 0.0s | — |
| `core.test_feature_edges.ColorParsing` | 2 | 2 | 0.0s | — |
| `core.test_feature_edges.ImageFormatTable` | 3 | 3 | 0.0s | — |
| `core.test_feature_edges.LogRotation` | 3 | 3 | 0.0s | — |
| `core.test_feature_edges.NormMap` | 3 | 3 | 0.0s | — |
| `core.test_feature_edges.OptionsSummary` | 3 | 3 | 0.0s | — |
| `core.test_feature_edges.PlanJobs` | 6 | 6 | 0.0s | — |
| `core.test_platform_stability.ConfigResolution` | 5 | 5 | 0.0s | — |
| `core.test_platform_stability.EnvOverrides` | 1 | 1 | 0.0s | — |
| `core.test_platform_stability.ErrorContract` | 2 | 2 | 0.0s | — |
| `core.test_platform_stability.PathHandling` | 5 | 5 | 0.0s | — |
| `core.test_platform_stability.PlatformDefaults` | 4 | 4 | 0.0s | — |
| `core.test_platform_stability.ScaleAndIdempotence` | 3 | 3 | 0.2s | — |
| `core.test_platform_stability.VersionMeta` | 2 | 2 | 0.0s | — |
| `core.test_properties.ColorProperties` | 2 | 2 | 0.1s | — |
| `core.test_properties.NormMapProperties` | 3 | 3 | 0.2s | — |
| `core.test_properties.PlanJobsProperties` | 1 | 1 | 0.1s | — |
| `core.test_properties.UniquePathProperties` | 1 | 1 | 0.1s | — |
| `core.test_properties.WidthProperties` | 2 | 2 | 0.1s | — |

## 6. 其他（未归类，需显式确认）

| 分组 | 用例数 | 通过 | 覆盖的点 |
| --- | ---: | ---: | --- |
| `core.test_config_file.ConfigFile` | 9 | 9 | 待归类 |
| `core.test_error_contract.CoreErrorContract` | 5 | 5 | 待归类 |
| `core.test_ocr_contract.OcrRegionCalls` | 4 | 4 | 待归类 |
| `core.test_ocr_contract.OcrResultParsing` | 3 | 3 | 待归类 |

## 7. 覆盖薄弱点（按覆盖率升序，前 10）

| 模块 | 覆盖率 | 未覆盖行 |
| --- | ---: | ---: |
| `cli/__main__.py` | 0.0% | 4 |
| `tui/__main__.py` | 0.0% | 4 |
| `bootstrap.py` | 57.8% | 43 |
| `tui/ui.py` | 60.5% | 47 |
| `launch.py` | 71.9% | 9 |
| `tui/ui_base.py` | 78.1% | 21 |
| `tui/ui_actions.py` | 80.0% | 45 |
| `tui/ui_input.py` | 81.0% | 19 |
| `tui/app.py` | 85.4% | 69 |
| `cli/main.py` | 85.8% | 31 |

## 8. 怎么更新

```bash
.venv/bin/python tools/check_all.py                 # 跑全量用例并生成 coverage.xml / junit.xml
.venv/bin/python tools/coverage_report.py --write    # 重新生成本文件
```

覆盖率门槛由 `tools/check_coverage.py` 把关（总量、9 个高风险模块、skip 比例），
所以本文件里的 ❌ 会同时让 `check_all` 变红。
