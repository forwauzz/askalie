import ask_alie
from ask_alie.cli import COMMANDS, build_parser


def test_version() -> None:
    assert ask_alie.__version__


def test_help_lists_all_commands() -> None:
    help_text = build_parser().format_help()
    for name in COMMANDS:
        assert name in help_text


def test_stub_commands_exit_nonzero() -> None:
    from ask_alie.cli import IMPLEMENTED, main

    stub_commands = set(COMMANDS) - set(IMPLEMENTED)
    assert stub_commands, "all commands implemented: retire this test"
    assert main([next(iter(sorted(stub_commands)))]) == 1
    assert main([]) == 0
