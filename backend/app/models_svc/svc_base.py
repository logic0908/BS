class VoiceConversionEngine:
    def convert(
        self,
        input_vocals_path: str,
        prompt_text: str,
        style_strength: float,
        output_path: str,
        **kwargs,
    ) -> str:
        raise NotImplementedError
