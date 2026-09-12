from dialogue_generation.cli import build_parser


def test_expected_commands_exist():
    parser = build_parser()
    for argv in [
        ["doctor"],
        ["ingest", "--cast-id", "E36B"],
        ["status", "--cast-id", "E36B"],
        ["generate", "--cast-id", "E36B"],
        ["review", "--cast-id", "E36B"],
        ["export", "--cast-id", "E36B"],
    ]:
        args = parser.parse_args(argv)
        assert callable(args.func)
