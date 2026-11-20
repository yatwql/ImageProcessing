# 测试覆盖率与分组统计

> 版本：v0.5-dev

本文件由 `python -m src.python.tools.test_coverage_report --write` 生成，数据取自 `reports/coverage.xml` 与
`reports/junit.xml`（`python -m src.python.tools.check_all` 全量模式产出）。改完用例或实现后重新生成即可，
不要手改数字。

> 生成时间：2026-11-20 08:21　|　命令：`.venv/bin/python -m src.python.tools.check_all`

## 1. 总览

| 指标 | 数值 | 门槛 | 结论 |
| --- | ---: | ---: | --- |
| 行覆盖率 | 95.3% | ≥ 93.0% | ✅ |
| 用例总数 | 755 | — | — |
| 通过 | 755 | = 总数 | ✅ |
| 跳过 | 0（0.0%） | ≤ 15.0% | ✅ |
| 用例总耗时 | 183.8s | — | — |

## 2. 模块覆盖率（高风险模块带门槛）

| 模块 | 覆盖率 | 覆盖行 / 总行 | 门槛 | 结论 |
| --- | ---: | ---: | ---: | --- |
| `tui/ui_actions.py` | 86.3% | 196 / 227 | ≥ 80.0% | ✅ |
| `tui/app.py` | 87.6% | 454 / 518 | ≥ 80.0% | ✅ |
| `core/match.py` | 91.4% | 96 / 105 | ≥ 90.0% | ✅ |
| `cli/main.py` | 91.9% | 182 / 198 | ≥ 85.0% | ✅ |
| `core/style.py` | 93.7% | 179 / 191 | — | — |
| `core/edit.py` | 96.9% | 154 / 159 | ≥ 85.0% | ✅ |
| `cli/batch.py` | 97.6% | 122 / 125 | — | — |
| `core/render.py` | 97.9% | 93 / 95 | ≥ 85.0% | ✅ |
| `bootstrap.py` | 98.2% | 112 / 114 | ≥ 90.0% | ✅ |
| `tui/ui_input.py` | 99.1% | 106 / 107 | ≥ 80.0% | ✅ |
| `tui/ui.py` | 99.2% | 122 / 123 | ≥ 90.0% | ✅ |
| `__init__.py` | 100.0% | 4 / 4 | — | — |
| `config.py` | 100.0% | 81 / 81 | — | — |
| `launch.py` | 100.0% | 30 / 30 | ≥ 90.0% | ✅ |
| `stdio.py` | 100.0% | 15 / 15 | — | — |
| `version.py` | 100.0% | 5 / 5 | — | — |
| `cli/__main__.py` | 100.0% | 2 / 2 | — | — |
| `cli/log_query.py` | 100.0% | 48 / 48 | ≥ 90.0% | ✅ |
| `core/__init__.py` | 100.0% | 12 / 12 | — | — |
| `core/audit.py` | 100.0% | 183 / 183 | ≥ 85.0% | ✅ |
| `core/errors.py` | 100.0% | 2 / 2 | — | — |
| `core/fonts.py` | 100.0% | 151 / 151 | — | — |
| `core/image.py` | 100.0% | 105 / 105 | ≥ 85.0% | ✅ |
| `core/jobs.py` | 100.0% | 48 / 48 | — | — |
| `core/ocr.py` | 100.0% | 40 / 40 | — | — |
| `core/options.py` | 100.0% | 54 / 54 | ≥ 90.0% | ✅ |
| `tui/__main__.py` | 100.0% | 2 / 2 | — | — |
| `tui/browse.py` | 100.0% | 33 / 33 | — | — |
| `tui/ui_base.py` | 100.0% | 96 / 96 | ≥ 80.0% | ✅ |
| `tui/ui_draw.py` | 100.0% | 236 / 236 | ≥ 85.0% | ✅ |

## 3. 包级汇总

| 包 | 文件数 | 覆盖率 |
| --- | ---: | ---: |
| `.` | 6 | 99.2% |
| `cli` | 4 | 94.9% |
| `core` | 12 | 97.6% |
| `tui` | 8 | 92.8% |

## 4. 场景测试分组（426 例）

| 分组 | 用例数 | 通过 | 耗时 | 覆盖的点 |
| --- | ---: | ---: | ---: | --- |
| `cli.test_arguments.ArgumentGuards` | 5 | 5 | 0.0s | — |
| `cli.test_arguments.MappingLoading` | 5 | 5 | 0.0s | — |
| `cli.test_arguments.ParserDefaults` | 3 | 3 | 0.0s | — |
| `cli.test_arguments.VersionFlag` | 1 | 1 | 0.0s | — |
| `cli.test_arguments.WorkerLevels` | 6 | 6 | 0.0s | — |
| `cli.test_batch_directory.BatchDirectoryRun` | 9 | 9 | 20.0s | — |
| `cli.test_bootstrap_launch.BootstrapMain` | 4 | 4 | 0.0s | — |
| `cli.test_bootstrap_launch.ConfDirResolution` | 3 | 3 | 0.0s | — |
| `cli.test_bootstrap_launch.EnsureDependencies` | 4 | 4 | 0.0s | — |
| `cli.test_bootstrap_launch.EnsureVenv` | 2 | 2 | 0.0s | — |
| `cli.test_bootstrap_launch.LaunchDispatch` | 4 | 4 | 0.0s | — |
| `cli.test_bootstrap_launch.MissingModules` | 3 | 3 | 0.6s | — |
| `cli.test_bootstrap_launch.PlatformPaths` | 2 | 2 | 0.0s | — |
| `cli.test_bootstrap_launch.WriteConfig` | 3 | 3 | 0.0s | — |
| `cli.test_bootstrap_probe_paths.BootstrapGaps` | 1 | 1 | 0.0s | — |
| `cli.test_bootstrap_probe_paths.BootstrapProbe` | 1 | 1 | 0.0s | — |
| `cli.test_bootstrap_probe_paths.EntryShimGaps` | 2 | 2 | 0.0s | — |
| `cli.test_bootstrap_probe_paths.FinalGaps` | 1 | 1 | 0.0s | — |
| `cli.test_bootstrap_probe_paths.FinalGaps6` | 1 | 1 | 0.0s | — |
| `cli.test_bootstrap_probe_paths.LaunchGaps` | 1 | 1 | 0.0s | — |
| `cli.test_bootstrap_probe_paths.ProbeOserror` | 1 | 1 | 0.0s | — |
| `cli.test_bootstrap_probe_paths.VenvHint` | 3 | 3 | 0.0s | — |
| `cli.test_cli_failure_paths.AllImagesUnreadable` | 1 | 1 | 0.0s | — |
| `cli.test_cli_failure_paths.CliReportGaps` | 1 | 1 | 0.0s | — |
| `cli.test_cli_failure_paths.CliSaveFailureCleanup` | 1 | 1 | 0.0s | — |
| `cli.test_cli_failure_paths.FinalGaps` | 2 | 2 | 0.0s | — |
| `cli.test_cli_failure_paths.FinalGaps2` | 1 | 1 | 0.0s | — |
| `cli.test_cli_failure_paths.FinalGaps3` | 1 | 1 | 0.0s | — |
| `cli.test_cli_failure_paths.FinalGaps4` | 1 | 1 | 0.0s | — |
| `cli.test_cli_failure_paths.FinalGaps5` | 1 | 1 | 0.0s | — |
| `cli.test_cli_failure_paths.FinalGaps6` | 1 | 1 | 0.0s | — |
| `cli.test_cli_failure_paths.FinalGaps7` | 1 | 1 | 0.1s | — |
| `cli.test_cli_failure_paths.FinalGaps8` | 1 | 1 | 0.0s | — |
| `cli.test_cli_failure_paths.ReserveFailure` | 1 | 1 | 0.0s | — |
| `cli.test_cli_failure_paths.SameFileRefusal` | 1 | 1 | 0.1s | — |
| `cli.test_demo_assets.DemoAssets` | 2 | 2 | 0.1s | — |
| `cli.test_demo_assets.DemoCliFlows` | 5 | 5 | 23.6s | — |
| `cli.test_entry_smoke.EntryPoints` | 8 | 8 | 0.2s | — |
| `cli.test_entry_smoke.ScriptLaunchers` | 2 | 2 | 0.5s | — |
| `cli.test_entry_smoke.ShellScriptsAreLf` | 1 | 1 | 0.0s | — |
| `cli.test_launch_env.AutoSetupSwitch` | 3 | 3 | 0.0s | — |
| `cli.test_launch_env.BootstrapEntry` | 2 | 2 | 0.0s | — |
| `cli.test_launch_env.LaunchChannels` | 4 | 4 | 0.0s | — |
| `cli.test_launch_env.MissingModules` | 3 | 3 | 0.7s | — |
| `cli.test_log_query_cli.LogQueryCli` | 8 | 8 | 0.1s | — |
| `cli.test_single_image.SingleImageOutputPixels` | 1 | 1 | 1.0s | — |
| `cli.test_single_image.SingleImageRun` | 13 | 13 | 23.9s | — |
| `cli.test_single_image.VersionBanner` | 1 | 1 | 4.4s | — |
| `core.test_cancel_pipeline.ReplacementCancel` | 4 | 4 | 0.7s | — |
| `core.test_log_query.LogQuery` | 9 | 9 | 0.1s | — |
| `core.test_mapping_rules.BlockOverrides` | 4 | 4 | 0.0s | — |
| `core.test_mapping_rules.MappingRules` | 8 | 8 | 0.0s | — |
| `core.test_version_display.CodeUpdatedDate` | 5 | 5 | 0.0s | — |
| `core.test_version_display.VersionInDocs` | 1 | 1 | 0.0s | — |
| `core.test_version_display.VersionIsLogged` | 1 | 1 | 0.0s | — |
| `core.test_version_display.VersionIsPrinted` | 4 | 4 | 6.2s | — |
| `core.test_version_display.VersionSource` | 2 | 2 | 0.0s | — |
| `core.test_write_audit_log.AuditEntryFields` | 7 | 7 | 0.0s | — |
| `core.test_write_audit_log.AuditLogFile` | 9 | 9 | 0.5s | — |
| `core.test_write_audit_log.CliWritesAuditLog` | 9 | 9 | 18.2s | — |
| `core.test_write_audit_log.TuiWritesAuditLog` | 7 | 7 | 9.8s | — |
| `tui.test_apply_and_batch.ApplyFlow` | 12 | 12 | 14.3s | — |
| `tui.test_directory_browsing.BrowseKeys` | 3 | 3 | 0.1s | — |
| `tui.test_directory_browsing.DefaultInput` | 2 | 2 | 0.0s | — |
| `tui.test_directory_browsing.DirectoryRows` | 7 | 7 | 0.1s | — |
| `tui.test_interaction_edges.BatchEdges` | 3 | 3 | 0.7s | — |
| `tui.test_interaction_edges.BrowsingEdges` | 4 | 4 | 0.0s | — |
| `tui.test_interaction_edges.KeyEdges` | 5 | 5 | 0.3s | — |
| `tui.test_interaction_edges.MappingEdits` | 4 | 4 | 0.0s | — |
| `tui.test_interaction_edges.SettingParsing` | 8 | 8 | 0.1s | — |
| `tui.test_key_dispatch.BackgroundLoading` | 2 | 2 | 0.1s | — |
| `tui.test_key_dispatch.BatchInterrupt` | 2 | 2 | 0.1s | — |
| `tui.test_key_dispatch.MainPanelKeys` | 17 | 17 | 2.1s | — |
| `tui.test_key_dispatch.MapPanelKeys` | 5 | 5 | 0.0s | — |
| `tui.test_key_dispatch.NonAsciiDigits` | 2 | 2 | 0.0s | — |
| `tui.test_key_dispatch.NonBlockingInput` | 4 | 4 | 0.0s | — |
| `tui.test_key_dispatch.RescanDirectory` | 3 | 3 | 0.0s | — |
| `tui.test_key_dispatch.SettingsPanelKeys` | 4 | 4 | 0.0s | — |
| `tui.test_keys_and_navigation.CliLikeArguments` | 2 | 2 | 0.0s | — |
| `tui.test_keys_and_navigation.KeySequenceDecoding` | 4 | 4 | 0.0s | — |
| `tui.test_keys_and_navigation.ListNavigation` | 11 | 11 | 0.4s | — |
| `tui.test_layout_rendering.BorderDrawing` | 3 | 3 | 0.0s | — |
| `tui.test_layout_rendering.LayoutRendering` | 6 | 6 | 0.1s | — |
| `tui.test_layout_rendering.RefreshFlush` | 3 | 3 | 0.1s | — |
| `tui.test_layout_rendering.ResponsiveLayout` | 8 | 8 | 0.1s | — |
| `tui.test_layout_rendering.WindowsStyleAcs` | 1 | 1 | 0.0s | — |
| `tui.test_mapping_panel.MappingPanel` | 5 | 5 | 0.3s | — |
| `tui.test_screen_snapshots.ScreenSnapshots` | 1 | 1 | 0.5s | — |
| `tui.test_screen_snapshots.SnapshotSanity` | 2 | 2 | 0.2s | — |
| `tui.test_session_state.TuiSessionState` | 4 | 4 | 0.1s | — |
| `tui.test_settings_panel.SettingsPanel` | 9 | 9 | 0.4s | — |
| `tui.test_tui_real_terminal.RealTerminalSmoke` | 2 | 2 | 10.0s | — |
| `tui.test_tui_state_edges.EnterOnBlocksPanel` | 1 | 1 | 0.0s | — |
| `tui.test_tui_state_edges.FinalGaps` | 5 | 5 | 0.0s | — |
| `tui.test_tui_state_edges.FinalGaps2` | 6 | 6 | 0.0s | — |
| `tui.test_tui_state_edges.FinalGaps3` | 5 | 5 | 0.0s | — |
| `tui.test_tui_state_edges.FinalGaps4` | 7 | 7 | 0.0s | — |
| `tui.test_tui_state_edges.FinalGaps5` | 3 | 3 | 0.1s | — |
| `tui.test_tui_state_edges.FinalGaps6` | 3 | 3 | 0.1s | — |
| `tui.test_tui_state_edges.FinalGaps7` | 3 | 3 | 0.0s | — |
| `tui.test_tui_state_edges.FinalGaps8` | 1 | 1 | 0.0s | — |
| `tui.test_tui_state_edges.SettingsJump` | 5 | 5 | 0.0s | — |
| `tui.test_tui_state_edges.TuiGaps` | 7 | 7 | 0.1s | — |
| `tui.test_ui_shell.BaseWidgets` | 5 | 5 | 0.0s | — |
| `tui.test_ui_shell.DrawEntry` | 1 | 1 | 0.0s | — |
| `tui.test_ui_shell.LoopBehaviour` | 5 | 5 | 0.6s | — |
| `tui.test_ui_shell.MainEntry` | 5 | 5 | 0.0s | — |
| `tui.test_ui_shell.ParseArgs` | 6 | 6 | 0.0s | — |
| `tui.test_ui_shell.ReadKey` | 8 | 8 | 0.0s | — |

## 5. 单元测试分组（147 例）

| 分组 | 用例数 | 通过 | 耗时 | 覆盖的点 |
| --- | ---: | ---: | ---: | --- |
| `core.background.test_background_types` | 7 | 7 | 0.3s | — |
| `core.color.test_alpha_channel` | 4 | 4 | 1.1s | — |
| `core.color.test_text_colors` | 2 | 2 | 8.5s | — |
| `core.font.test_font_matching_edges` | 13 | 13 | 0.3s | — |
| `core.font.test_font_pool` | 16 | 16 | 1.2s | — |
| `core.format.test_image_io_edges` | 5 | 5 | 0.0s | — |
| `core.format.test_image_read_write` | 16 | 16 | 0.1s | — |
| `core.layout.test_text_layout` | 5 | 5 | 11.9s | — |
| `core.pipeline.test_edit_pipeline_edges` | 17 | 17 | 0.3s | — |
| `core.pipeline.test_replace_pipeline` | 3 | 3 | 7.7s | — |
| `core.primitives.test_erasing_and_drawing` | 12 | 12 | 0.1s | — |
| `core.primitives.test_inpaint_radius` | 6 | 6 | 0.1s | — |
| `core.primitives.test_rendering_edges` | 3 | 3 | 0.0s | — |
| `core.primitives.test_rendering_primitives` | 4 | 4 | 0.0s | — |
| `core.primitives.test_style_analysis` | 3 | 3 | 4.2s | — |
| `core.test_platform_stability.ConfigResolution` | 5 | 5 | 0.0s | — |
| `core.test_platform_stability.EnvOverrides` | 1 | 1 | 0.0s | — |
| `core.test_platform_stability.ErrorContract` | 2 | 2 | 0.0s | — |
| `core.test_platform_stability.PathHandling` | 5 | 5 | 0.0s | — |
| `core.test_platform_stability.PlatformDefaults` | 4 | 4 | 0.0s | — |
| `core.test_platform_stability.ScaleAndIdempotence` | 3 | 3 | 0.3s | — |
| `core.test_platform_stability.VersionMeta` | 2 | 2 | 0.0s | — |
| `core.test_properties.ColorProperties` | 2 | 2 | 0.3s | — |
| `core.test_properties.NormMapProperties` | 3 | 3 | 0.6s | — |
| `core.test_properties.PlanJobsProperties` | 1 | 1 | 0.4s | — |
| `core.test_properties.UniquePathProperties` | 1 | 1 | 0.5s | — |
| `core.test_properties.WidthProperties` | 2 | 2 | 0.4s | — |

## 6. 其他（未归类，需显式确认）

| 分组 | 用例数 | 通过 | 覆盖的点 |
| --- | ---: | ---: | --- |
| `core.mapping.test_matching_edge_cases` | 12 | 12 | 待归类 |
| `core.test_audit_log_edges.AuditBadLine` | 1 | 1 | 待归类 |
| `core.test_audit_log_edges.AuditGaps` | 1 | 1 | 待归类 |
| `core.test_audit_log_edges.AuditJsonError` | 1 | 1 | 待归类 |
| `core.test_audit_log_edges.AuditWriteFailure` | 1 | 1 | 待归类 |
| `core.test_audit_log_edges.FinalGaps2` | 1 | 1 | 待归类 |
| `core.test_audit_log_edges.FinalGaps3` | 2 | 2 | 待归类 |
| `core.test_audit_log_edges.FinalGaps4` | 1 | 1 | 待归类 |
| `core.test_audit_log_edges.FinalGaps5` | 1 | 1 | 待归类 |
| `core.test_audit_log_edges.FinalGaps6` | 1 | 1 | 待归类 |
| `core.test_audit_log_edges.FinalGaps7` | 1 | 1 | 待归类 |
| `core.test_audit_log_edges.FinalGaps8` | 1 | 1 | 待归类 |
| `core.test_audit_log_edges.LockWithoutAnyBackend` | 1 | 1 | 待归类 |
| `core.test_audit_log_edges.LogRotation` | 3 | 3 | 待归类 |
| `core.test_audit_log_edges.OptionsSummary` | 3 | 3 | 待归类 |
| `core.test_audit_log_edges.WinLockImportFailure` | 1 | 1 | 待归类 |
| `core.test_config_and_ocr_edges.ConfigAlign` | 1 | 1 | 待归类 |
| `core.test_config_and_ocr_edges.ConfigFitWidth` | 1 | 1 | 待归类 |
| `core.test_config_and_ocr_edges.ConfigGaps` | 1 | 1 | 待归类 |
| `core.test_config_and_ocr_edges.OcrEmptyResult` | 1 | 1 | 待归类 |
| `core.test_config_and_ocr_edges.OcrGaps` | 1 | 1 | 待归类 |
| `core.test_config_and_ocr_edges.OcrImportFailure` | 1 | 1 | 待归类 |
| `core.test_config_and_ocr_edges.OptionGaps` | 1 | 1 | 待归类 |
| `core.test_config_and_ocr_edges.VerboseLog` | 1 | 1 | 待归类 |
| `core.test_config_and_ocr_edges.WarnOutput` | 1 | 1 | 待归类 |
| `core.test_config_file.ConfigFile` | 9 | 9 | 待归类 |
| `core.test_error_contract.CoreErrorContract` | 5 | 5 | 待归类 |
| `core.test_ocr_contract.OcrRegionCalls` | 4 | 4 | 待归类 |
| `core.test_ocr_contract.OcrResultParsing` | 3 | 3 | 待归类 |
| `core.test_report_inline_fragment.FragmentInWriteLog` | 2 | 2 | 待归类 |
| `core.test_report_inline_fragment.InlineFragmentInReport` | 3 | 3 | 待归类 |
| `core.test_stdio.Utf8Stdio` | 5 | 5 | 待归类 |
| `tools.test_gate_pipeline.BatchExecution` | 5 | 5 | 待归类 |
| `tools.test_gate_pipeline.GateArgs` | 4 | 4 | 待归类 |
| `tools.test_gate_pipeline.ReleaseFailFast` | 3 | 3 | 待归类 |
| `tools.test_gate_pipeline.VariantPlan` | 8 | 8 | 待归类 |
| `tools.test_gate_pipeline.WorkerPlan` | 6 | 6 | 待归类 |
| `tools.test_gate_stamp.CommandLine` | 2 | 2 | 待归类 |
| `tools.test_gate_stamp.Fingerprint` | 2 | 2 | 待归类 |
| `tools.test_gate_stamp.StampFile` | 4 | 4 | 待归类 |
| `tools.test_gen_folders_stats.RefreshStats` | 2 | 2 | 待归类 |
| `tools.test_gen_folders_stats.StatsCells` | 2 | 2 | 待归类 |
| `tools.test_junit_summary.CommandLine` | 3 | 3 | 待归类 |
| `tools.test_junit_summary.FailingCases` | 2 | 2 | 待归类 |
| `tools.test_perf_limits.PerfLimits` | 3 | 3 | 待归类 |
| `tools.test_platform_safety_rules.AbsoluteThresholdRule` | 2 | 2 | 待归类 |
| `tools.test_platform_safety_rules.BareShellRule` | 2 | 2 | 待归类 |
| `tools.test_platform_safety_rules.BashProbe` | 3 | 3 | 待归类 |
| `tools.test_platform_safety_rules.FcntlRule` | 2 | 2 | 待归类 |
| `tools.test_platform_safety_rules.FontFamilyRule` | 3 | 3 | 待归类 |
| `tools.test_platform_safety_rules.FontModeSelections` | 4 | 4 | 待归类 |
| `tools.test_platform_safety_rules.LineEndingRule` | 1 | 1 | 待归类 |
| `tools.test_platform_safety_rules.RawRuntimeRule` | 2 | 2 | 待归类 |
| `tools.test_platform_safety_rules.ToolStdioRule` | 3 | 3 | 待归类 |
| `tools.test_release_archive.ArchiveCommand` | 4 | 4 | 待归类 |
| `tools.test_release_archive.IndexBlock` | 1 | 1 | 待归类 |
| `tools.test_release_archive.SeriesName` | 1 | 1 | 待归类 |
| `tools.test_release_archive.SplitDoc` | 3 | 3 | 待归类 |
| `tools.test_release_versions.DevBump` | 2 | 2 | 待归类 |
| `tools.test_release_versions.Prepare` | 3 | 3 | 待归类 |
| `tools.test_release_versions.Tag` | 3 | 3 | 待归类 |
| `tools.test_release_versions.VersionForm` | 2 | 2 | 待归类 |
| `tools.test_test_failure_tooling.Locate` | 2 | 2 | 待归类 |
| `tools.test_test_failure_tooling.MinimizePrefix` | 2 | 2 | 待归类 |
| `tools.test_test_failure_tooling.NodeId` | 2 | 2 | 待归类 |
| `tools.test_test_failure_tooling.ParseCollectOrder` | 2 | 2 | 待归类 |
| `tools.test_test_failure_tooling.TestFailuresCLI` | 5 | 5 | 待归类 |
| `tools.test_tool_entry_contracts.CIMode` | 3 | 3 | 待归类 |
| `tools.test_tool_entry_contracts.HelpExit` | 1 | 1 | 待归类 |
| `tools.test_tool_entry_contracts.HelpHasNoSideEffects` | 1 | 1 | 待归类 |
| `tools.test_workflow_checks.InlinePythonBan` | 2 | 2 | 待归类 |
| `tools.test_workflow_checks.ShellSyntax` | 3 | 3 | 待归类 |

## 7. 覆盖薄弱点（按覆盖率升序，前 10）

| 模块 | 覆盖率 | 未覆盖行 |
| --- | ---: | ---: |
| `tui/ui_actions.py` | 86.3% | 31 |
| `tui/app.py` | 87.6% | 64 |
| `core/match.py` | 91.4% | 9 |
| `cli/main.py` | 91.9% | 16 |
| `core/style.py` | 93.7% | 12 |
| `core/edit.py` | 96.9% | 5 |
| `cli/batch.py` | 97.6% | 3 |
| `core/render.py` | 97.9% | 2 |
| `bootstrap.py` | 98.2% | 2 |
| `tui/ui_input.py` | 99.1% | 1 |

## 8. 怎么更新

```bash
.venv/bin/python -m src.python.tools.check_all                # 跑全量用例并生成 coverage.xml / junit.xml
.venv/bin/python -m src.python.tools.test_coverage_report --write  # 重新生成本文件
```

覆盖率门槛由 `src/python/tools/check_coverage.py` 把关（行 + 分支总量 93%、16 个高风险模块、skip ≤15%），
所以本文件里的 ❌ 会同时让 `check_all` 变红。
