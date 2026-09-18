from pa_agent.config.model_providers import guess_provider


def test_custom_base_url_wins_over_model_keyword() -> None:
    """A relay URL must remain custom even when its model name says deepseek."""
    assert (
        guess_provider(
            "https://cli.999554.xyz/v1",
            "DeepSeek-V4-Flash[free]",
        )
        is None
    )
