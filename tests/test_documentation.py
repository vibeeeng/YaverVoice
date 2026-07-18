from __future__ import annotations

import unittest

from src.core.documentation import DocumentationError, GroqDocumentationGenerator


FAKE_GROQ_KEY = "gsk" + "_test"


class FakeMessage:
    def __init__(self, content: str):
        self.content = content


class FakeChoice:
    def __init__(self, content: str):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content: str):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse("# Test Doc\n\n## Kisa Ozet\n- Done")


class FakeChat:
    def __init__(self):
        self.completions = FakeCompletions()


class FakeClient:
    def __init__(self):
        self.chat = FakeChat()


class DocumentationTests(unittest.TestCase):
    def test_generate_markdown_uses_chat_completion(self):
        client = FakeClient()
        generator = GroqDocumentationGenerator(FAKE_GROQ_KEY, client=client)

        result = generator.generate("Bu bir toplanti transkriptidir.", source_name="meeting.wav", language="tr")

        self.assertTrue(result.markdown.startswith("# Test Doc"))
        self.assertEqual(result.model, "openai/gpt-oss-120b")
        self.assertEqual(result.calls, 1)
        self.assertEqual(client.chat.completions.calls[0]["model"], "openai/gpt-oss-120b")
        self.assertEqual(client.chat.completions.calls[0]["temperature"], 0.2)
        self.assertEqual(client.chat.completions.calls[0]["reasoning_effort"], "low")
        self.assertEqual(client.chat.completions.calls[0]["reasoning_format"], "hidden")

    def test_long_transcript_is_reduced_before_final_markdown(self):
        client = FakeClient()
        generator = GroqDocumentationGenerator(FAKE_GROQ_KEY, client=client)

        result = generator.generate("line\n" * 25000, source_name="long.wav", language="tr")

        self.assertIn("## Kisa Ozet", result.markdown)
        self.assertGreater(len(client.chat.completions.calls), 1)

    def test_can_select_qwen_model_profile(self):
        client = FakeClient()
        generator = GroqDocumentationGenerator(FAKE_GROQ_KEY, model="qwen/qwen3.6-27b", client=client)

        result = generator.generate("hello", source_name="short.wav", language="en")

        self.assertEqual(result.model, "qwen/qwen3.6-27b")
        self.assertEqual(client.chat.completions.calls[0]["model"], "qwen/qwen3.6-27b")
        self.assertEqual(client.chat.completions.calls[0]["reasoning_effort"], "none")
        self.assertEqual(client.chat.completions.calls[0]["reasoning_format"], "hidden")

    def test_detail_profile_changes_max_tokens_and_prompt(self):
        client = FakeClient()
        generator = GroqDocumentationGenerator(FAKE_GROQ_KEY, detail="detailed", client=client)

        result = generator.generate("hello", source_name="short.wav", language="en")

        self.assertEqual(result.detail, "detailed")
        self.assertEqual(client.chat.completions.calls[0]["max_tokens"], 6120)
        messages = client.chat.completions.calls[0]["messages"]
        self.assertIn("Create a detailed document", messages[1]["content"])

    def test_turkish_output_language_prompt_uses_turkish_instructions(self):
        client = FakeClient()
        generator = GroqDocumentationGenerator(FAKE_GROQ_KEY, client=client)

        generator.generate("This is an English transcript.", source_name="short.wav", language="tr")

        messages = client.chat.completions.calls[0]["messages"]
        self.assertIn("Write the output in this language: Turkish.", messages[1]["content"])
        self.assertIn("Use Markdown section headings in that output language.", messages[1]["content"])
        self.assertIn("## Kisa Ozet", messages[1]["content"])

    def test_same_language_uses_transcript_language_instruction(self):
        client = FakeClient()
        generator = GroqDocumentationGenerator(FAKE_GROQ_KEY, client=client)

        generator.generate("hello", source_name="short.wav", language="same")

        messages = client.chat.completions.calls[0]["messages"]
        self.assertIn("same language as the transcript", messages[1]["content"])

    def test_english_output_language_prompt_uses_english_headings(self):
        client = FakeClient()
        generator = GroqDocumentationGenerator(FAKE_GROQ_KEY, client=client)

        generator.generate("Merhaba", source_name="short.wav", language="en")

        messages = client.chat.completions.calls[0]["messages"]
        self.assertIn("Write the output in this language: English.", messages[1]["content"])
        self.assertIn("## Brief Summary", messages[1]["content"])
        self.assertIn("## Action Items", messages[1]["content"])

    def test_invalid_output_language_is_rejected(self):
        client = FakeClient()
        generator = GroqDocumentationGenerator(FAKE_GROQ_KEY, client=client)

        with self.assertRaisesRegex(DocumentationError, "Unsupported Docs output language"):
            generator.generate("hello", source_name="short.wav", language="jp")

        with self.assertRaisesRegex(DocumentationError, "Unsupported Docs output language"):
            generator.generate("hello", source_name="short.wav", language="auto")

    def test_progress_callback_reports_model_calls(self):
        client = FakeClient()
        progress = []
        generator = GroqDocumentationGenerator(FAKE_GROQ_KEY, client=client, on_progress=progress.append)

        generator.generate("line\n" * 25000, source_name="long.wav", language="tr")

        self.assertGreater(len(progress), 1)
        self.assertEqual(progress[-1]["phase"], "final")
        self.assertEqual(progress[-1]["current"], progress[-1]["total"])

    def test_long_paragraph_split_prefers_sentence_boundaries(self):
        text = ("First sentence. Second sentence. Third sentence. " * 40).strip()

        chunks = GroqDocumentationGenerator._split_text(text, 120)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 120 for chunk in chunks))
        self.assertTrue(any(chunk.endswith(".") for chunk in chunks[:-1]))


if __name__ == "__main__":
    unittest.main()
