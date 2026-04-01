from __future__ import annotations

from rhc.cli import CUSTOMIZE_TARGETS_ORDER, _normalize_customize_targets, build_parser


def test_normalize_customize_targets_defaults_to_all() -> None:
    assert _normalize_customize_targets(None) == CUSTOMIZE_TARGETS_ORDER


def test_normalize_customize_targets_accepts_aliases() -> None:
    assert _normalize_customize_targets(["apk", "rotate"]) == ["apks", "auto-rotate"]


def test_normalize_customize_targets_all_overrides_specific() -> None:
    assert _normalize_customize_targets(["apks", "all"]) == CUSTOMIZE_TARGETS_ORDER


def test_build_parser_accepts_global_output_flags() -> None:
    parser = build_parser()

    args = parser.parse_args(["--output", "json", "--log-file", "tmp/log.jsonl", "hello"])

    assert args.output == "json"
    assert args.log_file == "tmp/log.jsonl"
    assert args.command == "hello"


def test_build_parser_collects_multiple_customize_targets() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "customize-device",
            "--target",
            "format-sd",
            "--target",
            "apks",
            "--cleanup-rpc",
        ]
    )

    assert args.command == "customize-device"
    assert args.target == ["format-sd", "apks"]
    assert args.cleanup_rpc is True


def test_normalize_customize_targets_includes_obtainium_alias() -> None:
    assert _normalize_customize_targets(["obtainium"]) == ["obtainium-import"]
