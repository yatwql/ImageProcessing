# 测试覆盖率与分组统计

> 版本：v0.4-dev

本文件由 `python -m src.python.tools.coverage_report --write` 生成，数据取自 `reports/coverage.xml` 与
`reports/junit.xml`（`python -m src.python.tools.check_all` 全量模式产出）。改完用例或实现后重新生成即可，
不要手改数字。

> 生成时间：2026-11-19 00:21　|　命令：`.venv/bin/python -m src.python.tools.check_all`

## 1. 总览

| 指标 | 数值 | 门槛 | 结论 |
| --- | ---: | ---: | --- |
| 行覆盖率 | 96.7% | ≥ 96.0% | ✅ |
| 用例总数 | 729 | — | — |
| 通过 | 729 | = 总数 | ✅ |
| 跳过 | 0（0.0%） | ≤ 15.0% | ✅ |
| 用例总耗时 | 148.2s | — | — |

## 2. 模块覆盖率（高风险模块带门槛）

| 模块 | 覆盖率 | 覆盖行 / 总行 | 门槛 | 结论 |
| --- | ---: | ---: | ---: | --- |
| `tui/ui_actions.py` | 85.8% | 193 / 225 | ≥ 80.0% | ✅ |
| `tui/app.py` | 91.9% | 434 / 472 | ≥ 80.0% | ✅ |
| `core/style.py` | 94.7% | 161 / 170 | — | — |
| `cli/main.py` | 95.8% | 206 / 215 | ≥ 85.0% | ✅ |
| `core/render.py` | 97.9% | 93 / 95 | ≥ 85.0% | ✅ |
| `tui/ui_base.py` | 99.0% | 95 / 96 | ≥ 80.0% | ✅ |
| `tui/ui_input.py` | 99.0% | 99 / 100 | ≥ 80.0% | ✅ |
| `core/edit.py` | 99.2% | 123 / 124 | ≥ 85.0% | ✅ |
| `__init__.py` | 100.0% | 4 / 4 | — | — |
| `bootstrap.py` | 100.0% | 100 / 100 | ≥ 90.0% | ✅ |
| `config.py` | 100.0% | 81 / 81 | — | — |
| `launch.py` | 100.0% | 30 / 30 | ≥ 90.0% | ✅ |
| `stdio.py` | 100.0% | 15 / 15 | — | — |
| `version.py` | 100.0% | 5 / 5 | — | — |
| `cli/__main__.py` | 100.0% | 2 / 2 | — | — |
| `cli/log_query.py` | 100.0% | 48 / 48 | ≥ 90.0% | ✅ |
| `core/__init__.py` | 100.0% | 12 / 12 | — | — |
| `core/audit.py` | 100.0% | 182 / 182 | ≥ 85.0% | ✅ |
| `core/errors.py` | 100.0% | 2 / 2 | — | — |
| `core/fonts.py` | 100.0% | 151 / 151 | — | — |
| `core/image.py` | 100.0% | 98 / 98 | ≥ 85.0% | ✅ |
| `core/jobs.py` | 100.0% | 47 / 47 | — | — |
| `core/match.py` | 100.0% | 63 / 63 | ≥ 90.0% | ✅ |
| `core/ocr.py` | 100.0% | 40 / 40 | — | — |
| `core/options.py` | 100.0% | 49 / 49 | ≥ 90.0% | ✅ |
| `tui/__main__.py` | 100.0% | 2 / 2 | — | — |
| `tui/browse.py` | 100.0% | 33 / 33 | — | — |
| `tui/ui.py` | 100.0% | 119 / 119 | ≥ 90.0% | ✅ |
| `tui/ui_draw.py` | 100.0% | 236 / 236 | ≥ 85.0% | ✅ |

## 3. 包级汇总

| 包 | 文件数 | 覆盖率 |
| --- | ---: | ---: |
| `.` | 6 | 100.0% |
| `cli` | 3 | 96.6% |
| `core` | 12 | 98.8% |
| `tui` | 8 | 94.4% |

## 4. 场景测试分组（351 例）

| 分组 | 用例数 | 通过 | 耗时 | 覆盖的点 |
| --- | ---: | ---: | ---: | --- |
| `cli.test_arguments.ArgumentGuards` | 5 | 5 | 0.0s | — |
| `cli.test_arguments.MappingLoading` | 5 | 5 | 0.0s | — |
| `cli.test_arguments.ParserDefaults` | 3 | 3 | 0.0s | — |
| `cli.test_arguments.VersionFlag` | 1 | 1 | 0.0s | — |
| `cli.test_batch_directory.BatchDirectoryRun` | 9 | 9 | 15.4s | — |
| `cli.test_bootstrap_launch.BootstrapMain` | 4 | 4 | 0.0s | — |
| `cli.test_bootstrap_launch.ConfDirResolution` | 3 | 3 | 0.0s | — |
| `cli.test_bootstrap_launch.EnsureDependencies` | 4 | 4 | 0.0s | — |
| `cli.test_bootstrap_launch.EnsureVenv` | 2 | 2 | 0.0s | — |
| `cli.test_bootstrap_launch.LaunchDispatch` | 6 | 6 | 0.0s | — |
| `cli.test_bootstrap_launch.MissingModules` | 3 | 3 | 0.4s | — |
| `cli.test_bootstrap_launch.PlatformPaths` | 2 | 2 | 0.0s | — |
| `cli.test_bootstrap_launch.WriteConfig` | 3 | 3 | 0.1s | — |
| `cli.test_demo_assets.DemoAssets` | 2 | 2 | 0.1s | — |
| `cli.test_demo_assets.DemoCliFlows` | 5 | 5 | 18.6s | — |
| `cli.test_entry_smoke.EntryPoints` | 8 | 8 | 0.3s | — |
| `cli.test_entry_smoke.ScriptLaunchers` | 2 | 2 | 0.4s | — |
| `cli.test_entry_smoke.ShellScriptsAreLf` | 1 | 1 | 0.0s | — |
| `cli.test_launch_env.AutoSetupSwitch` | 3 | 3 | 0.0s | — |
| `cli.test_launch_env.BootstrapEntry` | 2 | 2 | 0.0s | — |
| `cli.test_launch_env.LaunchChannels` | 4 | 4 | 0.0s | — |
| `cli.test_launch_env.MissingModules` | 3 | 3 | 0.4s | — |
| `cli.test_log_query_cli.LogQueryCli` | 8 | 8 | 0.0s | — |
| `cli.test_single_image.SingleImageOutputPixels` | 1 | 1 | 0.9s | — |
| `cli.test_single_image.SingleImageRun` | 13 | 13 | 17.7s | — |
| `cli.test_single_image.VersionBanner` | 1 | 1 | 3.5s | — |
| `core.test_cancel_pipeline.ReplacementCancel` | 4 | 4 | 0.5s | — |
| `core.test_log_query.LogQuery` | 9 | 9 | 0.1s | — |
| `core.test_mapping_rules.BlockOverrides` | 4 | 4 | 0.0s | — |
| `core.test_mapping_rules.MappingRules` | 8 | 8 | 0.0s | — |
| `core.test_version_display.CodeUpdatedDate` | 5 | 5 | 0.0s | — |
| `core.test_version_display.VersionInDocs` | 1 | 1 | 0.0s | — |
| `core.test_version_display.VersionIsLogged` | 1 | 1 | 0.0s | — |
| `core.test_version_display.VersionIsPrinted` | 4 | 4 | 4.9s | — |
| `core.test_version_display.VersionSource` | 2 | 2 | 0.0s | — |
| `core.test_write_audit_log.AuditEntryFields` | 7 | 7 | 0.1s | — |
| `core.test_write_audit_log.AuditLogFile` | 9 | 9 | 0.6s | — |
| `core.test_write_audit_log.CliWritesAuditLog` | 9 | 9 | 17.6s | — |
| `core.test_write_audit_log.TuiWritesAuditLog` | 7 | 7 | 7.9s | — |
| `tui.test_apply_and_batch.ApplyFlow` | 12 | 12 | 13.0s | — |
| `tui.test_directory_browsing.BrowseKeys` | 3 | 3 | 0.1s | — |
| `tui.test_directory_browsing.DefaultInput` | 2 | 2 | 0.0s | — |
| `tui.test_directory_browsing.DirectoryRows` | 7 | 7 | 0.0s | — |
| `tui.test_interaction_edges.BatchEdges` | 3 | 3 | 0.2s | — |
| `tui.test_interaction_edges.BrowsingEdges` | 4 | 4 | 0.0s | — |
| `tui.test_interaction_edges.KeyEdges` | 5 | 5 | 0.2s | — |
| `tui.test_interaction_edges.MappingEdits` | 4 | 4 | 0.1s | — |
| `tui.test_interaction_edges.SettingParsing` | 8 | 8 | 0.1s | — |
| `tui.test_key_dispatch.BackgroundLoading` | 2 | 2 | 0.1s | — |
| `tui.test_key_dispatch.BatchInterrupt` | 2 | 2 | 0.0s | — |
| `tui.test_key_dispatch.MainPanelKeys` | 17 | 17 | 0.5s | — |
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
| `tui.test_layout_rendering.ResponsiveLayout` | 8 | 8 | 0.1s | — |
| `tui.test_layout_rendering.WindowsStyleAcs` | 1 | 1 | 0.0s | — |
| `tui.test_mapping_panel.MappingPanel` | 5 | 5 | 0.1s | — |
| `tui.test_screen_snapshots.ScreenSnapshots` | 1 | 1 | 0.1s | — |
| `tui.test_screen_snapshots.SnapshotSanity` | 2 | 2 | 0.1s | — |
| `tui.test_session_state.TuiSessionState` | 4 | 4 | 0.0s | — |
| `tui.test_settings_panel.SettingsPanel` | 9 | 9 | 0.1s | — |
| `tui.test_tui_real_terminal.RealTerminalSmoke` | 2 | 2 | 10.1s | — |
| `tui.test_ui_shell.BaseWidgets` | 5 | 5 | 0.0s | — |
| `tui.test_ui_shell.DrawEntry` | 1 | 1 | 0.0s | — |
| `tui.test_ui_shell.LoopBehaviour` | 5 | 5 | 0.2s | — |
| `tui.test_ui_shell.MainEntry` | 5 | 5 | 0.0s | — |
| `tui.test_ui_shell.ParseArgs` | 6 | 6 | 0.0s | — |
| `tui.test_ui_shell.ReadKey` | 8 | 8 | 0.0s | — |

## 5. 单元测试分组（132 例）

| 分组 | 用例数 | 通过 | 耗时 | 覆盖的点 |
| --- | ---: | ---: | ---: | --- |
| `core.background.test_background_types` | 7 | 7 | 0.2s | — |
| `core.color.test_alpha_channel` | 4 | 4 | 0.9s | — |
| `core.color.test_text_colors` | 2 | 2 | 5.1s | — |
| `core.font.test_font_pool` | 16 | 16 | 1.8s | — |
| `core.format.test_image_read_write` | 16 | 16 | 0.1s | — |
| `core.layout.test_text_layout` | 5 | 5 | 10.4s | — |
| `core.pipeline.test_replace_pipeline` | 3 | 3 | 6.9s | — |
| `core.primitives.test_erasing_and_drawing` | 12 | 12 | 0.2s | — |
| `core.primitives.test_inpaint_radius` | 6 | 6 | 0.1s | — |
| `core.primitives.test_rendering_primitives` | 4 | 4 | 0.0s | — |
| `core.primitives.test_style_analysis` | 3 | 3 | 3.1s | — |
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
| `core.test_platform_stability.ScaleAndIdempotence` | 3 | 3 | 0.3s | — |
| `core.test_platform_stability.VersionMeta` | 2 | 2 | 0.0s | — |
| `core.test_properties.ColorProperties` | 2 | 2 | 0.2s | — |
| `core.test_properties.NormMapProperties` | 3 | 3 | 0.4s | — |
| `core.test_properties.PlanJobsProperties` | 1 | 1 | 0.1s | — |
| `core.test_properties.UniquePathProperties` | 1 | 1 | 0.2s | — |
| `core.test_properties.WidthProperties` | 2 | 2 | 0.2s | — |

## 6. 其他（未归类，需显式确认）

| 分组 | 用例数 | 通过 | 覆盖的点 |
| --- | ---: | ---: | --- |
| `core.test_config_file.ConfigFile` | 9 | 9 | 待归类 |
| `core.test_coverage_100.AllImagesUnreadable` | 1 | 1 | 待归类 |
| `core.test_coverage_100.EnterOnBlocksPanel` | 1 | 1 | 待归类 |
| `core.test_coverage_100.StyleInkSizeFailure` | 1 | 1 | 待归类 |
| `core.test_coverage_100.WinLockImportFailure` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.AuditGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.BootstrapGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.CliReportGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.ConfigGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.EditGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.EntryShimGaps` | 2 | 2 | 待归类 |
| `core.test_coverage_gaps.FontGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.ImageGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.LaunchGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.LogQueryGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.MatchGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.OcrGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.OptionGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.RenderGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.StyleGaps` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps.TuiGaps` | 7 | 7 | 待归类 |
| `core.test_coverage_gaps2.AuditBadLine` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps2.AuditJsonError` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps2.BootstrapProbe` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps2.CliSaveFailureCleanup` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps2.ConfigFitWidth` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps2.DebugMaskWriteFailure` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps2.FontRowParsing` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps2.MatchFuzzyPrint` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps2.MetaFailure` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps2.OcrEmptyResult` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps2.RenderEmptyLine` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps2.StyleRenderFailure` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps2.WarnOutput` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps3.AuditWriteFailure` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps3.BlankOnlyText` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps3.ConfigAlign` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps3.DebugDirFailure` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps3.EmptyMappingKey` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps3.FinalGaps` | 10 | 10 | 待归类 |
| `core.test_coverage_gaps3.FinalGaps2` | 10 | 10 | 待归类 |
| `core.test_coverage_gaps3.FinalGaps3` | 12 | 12 | 待归类 |
| `core.test_coverage_gaps3.FontCacheFailure` | 2 | 2 | 待归类 |
| `core.test_coverage_gaps3.LockWithoutAnyBackend` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps3.OcrImportFailure` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps3.ProbeOserror` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps3.RefineRenderFailure` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps3.ReserveFailure` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps3.SameFileRefusal` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps3.SettingsJump` | 5 | 5 | 待归类 |
| `core.test_coverage_gaps3.VerboseLog` | 1 | 1 | 待归类 |
| `core.test_coverage_gaps4.FinalGaps4` | 11 | 11 | 待归类 |
| `core.test_coverage_gaps4.FinalGaps5` | 6 | 6 | 待归类 |
| `core.test_coverage_gaps4.FinalGaps6` | 7 | 7 | 待归类 |
| `core.test_coverage_gaps4.FinalGaps7` | 5 | 5 | 待归类 |
| `core.test_coverage_gaps4.FinalGaps8` | 4 | 4 | 待归类 |
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
| `tools.test_release_versions.Tag` | 2 | 2 | 待归类 |
| `tools.test_release_versions.VersionForm` | 2 | 2 | 待归类 |
| `tools.test_workflow_checks.InlinePythonBan` | 2 | 2 | 待归类 |
| `tools.test_workflow_checks.ShellSyntax` | 3 | 3 | 待归类 |

## 7. 覆盖薄弱点（按覆盖率升序，前 10）

| 模块 | 覆盖率 | 未覆盖行 |
| --- | ---: | ---: |
| `tui/ui_actions.py` | 85.8% | 32 |
| `tui/app.py` | 91.9% | 38 |
| `core/style.py` | 94.7% | 9 |
| `cli/main.py` | 95.8% | 9 |
| `core/render.py` | 97.9% | 2 |
| `tui/ui_base.py` | 99.0% | 1 |
| `tui/ui_input.py` | 99.0% | 1 |
| `core/edit.py` | 99.2% | 1 |
| `__init__.py` | 100.0% | 0 |
| `bootstrap.py` | 100.0% | 0 |

## 8. 怎么更新

```bash
.venv/bin/python -m src.python.tools.check_all                # 跑全量用例并生成 coverage.xml / junit.xml
.venv/bin/python -m src.python.tools.coverage_report --write  # 重新生成本文件
```

覆盖率门槛由 `src/python/tools/check_coverage.py` 把关（总量 96%、16 个高风险模块、skip ≤15%），
所以本文件里的 ❌ 会同时让 `check_all` 变红。
