import ask_alie
from ask_alie.cli import COMMANDS, build_parser


def test_version() -> None:
    assert ask_alie.__version__


def test_help_lists_all_commands() -> None:
    help_text = build_parser().format_help()
    for name in COMMANDS:
        assert name in help_text


def test_all_commands_implemented() -> None:
    from ask_alie.cli import IMPLEMENTED, main

    assert set(COMMANDS) == set(IMPLEMENTED)
    assert main([]) == 0  # bare invocation prints help
