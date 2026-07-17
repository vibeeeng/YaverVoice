"""
Markdown documentation generation for transcript text.

The module is intentionally independent from audio transcription so the Docs
workflow can later be moved behind a separate UI or app shell.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable

from groq import Groq


DEFAULT_DOCS_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
DEFAULT_DOCS_DETAIL = "standard"
DEFAULT_DOCS_OUTPUT_LANGUAGE = "same"

DOCS_OUTPUT_LANGUAGES: dict[str, dict[str, Any]] = {
    "same": {
        "id": "same",
        "label": "Same as transcript",
        "instruction": "the same language as the transcript",
        "empty": "the local-language equivalent of '- None'",
        "sections": [
            "# <descriptive title in the transcript language>",
            "## <summary heading in the transcript language>",
            "## <main topics heading in the transcript language>",
            "## <detailed notes heading in the transcript language>",
            "## <decisions and outcomes heading in the transcript language>",
            "## <action items heading in the transcript language>",
            "## <open questions heading in the transcript language>",
            "## <source heading in the transcript language>",
        ],
    },
    "tr": {
        "id": "tr",
        "label": "Turkish",
        "instruction": "Turkish",
        "empty": "- Yok",
        "sections": [
            "# <Turkce aciklayici baslik>",
            "## Kisa Ozet",
            "## Ana Konular",
            "## Detayli Notlar",
            "## Kararlar ve Sonuclar",
            "## Aksiyon Maddeleri",
            "## Acik Sorular",
            "## Kaynak",
        ],
    },
    "en": {
        "id": "en",
        "label": "English",
        "instruction": "English",
        "empty": "- None",
        "sections": [
            "# <descriptive title>",
            "## Brief Summary",
            "## Main Topics",
            "## Detailed Notes",
            "## Decisions and Outcomes",
            "## Action Items",
            "## Open Questions",
            "## Source",
        ],
    },
    "de": {
        "id": "de",
        "label": "German",
        "instruction": "German",
        "empty": "- Keine",
        "sections": [
            "# <beschreibender Titel>",
            "## Kurze Zusammenfassung",
            "## Hauptthemen",
            "## Detaillierte Notizen",
            "## Entscheidungen und Ergebnisse",
            "## Aktionspunkte",
            "## Offene Fragen",
            "## Quelle",
        ],
    },
    "fr": {
        "id": "fr",
        "label": "French",
        "instruction": "French",
        "empty": "- Aucun",
        "sections": [
            "# <titre descriptif>",
            "## Bref resume",
            "## Sujets principaux",
            "## Notes detaillees",
            "## Decisions et resultats",
            "## Actions a mener",
            "## Questions ouvertes",
            "## Source",
        ],
    },
    "es": {
        "id": "es",
        "label": "Spanish",
        "instruction": "Spanish",
        "empty": "- Ninguno",
        "sections": [
            "# <titulo descriptivo>",
            "## Resumen breve",
            "## Temas principales",
            "## Notas detalladas",
            "## Decisiones y resultados",
            "## Acciones",
            "## Preguntas abiertas",
            "## Fuente",
        ],
    },
    "it": {
        "id": "it",
        "label": "Italian",
        "instruction": "Italian",
        "empty": "- Nessuno",
        "sections": [
            "# <titolo descrittivo>",
            "## Breve riepilogo",
            "## Argomenti principali",
            "## Note dettagliate",
            "## Decisioni e risultati",
            "## Azioni",
            "## Domande aperte",
            "## Fonte",
        ],
    },
}

DOCS_DETAIL_PROFILES: dict[str, dict[str, Any]] = {
    "short": {
        "id": "short",
        "label": "Short",
        "note": "Compact output for quick checks.",
        "chunk_multiplier": 0.65,
        "final_multiplier": 0.55,
        "instruction": "Keep the document short. Prefer concise bullets and only the most important details.",
    },
    "standard": {
        "id": "standard",
        "label": "Standard",
        "note": "Balanced detail for regular meeting notes.",
        "chunk_multiplier": 1.0,
        "final_multiplier": 1.0,
        "instruction": "Use balanced detail. Preserve important examples, decisions, and action items without over-expanding.",
    },
    "detailed": {
        "id": "detailed",
        "label": "Detailed",
        "note": "Longer documentation with more context and sub-bullets.",
        "chunk_multiplier": 1.45,
        "final_multiplier": 1.7,
        "instruction": (
            "Create a detailed document. Keep meaningful examples, reasoning, context, named entities, "
            "technical details, decisions, action owners if present, and open questions. Use sub-bullets when useful."
        ),
    },
}

DOCS_MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "meta-llama/llama-4-scout-17b-16e-instruct": {
        "id": "meta-llama/llama-4-scout-17b-16e-instruct",
        "label": "Llama 4 Scout 17B",
        "note": "MVP default: higher minute/day token limits for long notes.",
        "chunk_chars": 10000,
        "chunk_max_tokens": 1200,
        "final_max_tokens": 3600,
        "tpm": "30K",
        "tpd": "500K",
    },
    "qwen/qwen3-32b": {
        "id": "qwen/qwen3-32b",
        "label": "Qwen3 32B",
        "note": "Good daily token room; slower minute budget.",
        "chunk_chars": 7000,
        "chunk_max_tokens": 1000,
        "final_max_tokens": 3200,
        "tpm": "6K",
        "tpd": "500K",
    },
    "llama-3.3-70b-versatile": {
        "id": "llama-3.3-70b-versatile",
        "label": "Llama 3.3 70B",
        "note": "Higher quality option; lower daily token budget.",
        "chunk_chars": 8000,
        "chunk_max_tokens": 1200,
        "final_max_tokens": 3800,
        "tpm": "12K",
        "tpd": "100K",
    },
    "llama-3.1-8b-instant": {
        "id": "llama-3.1-8b-instant",
        "label": "Llama 3.1 8B Instant",
        "note": "Fast/light test option; lower summarization quality.",
        "chunk_chars": 7000,
        "chunk_max_tokens": 900,
        "final_max_tokens": 2600,
        "tpm": "6K",
        "tpd": "500K",
    },
}


class DocumentationError(RuntimeError):
    """Raised when Markdown documentation generation fails."""


@dataclass(frozen=True)
class DocumentationResult:
    markdown: str
    model: str
    detail: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class GroqDocumentationGenerator:
    """Generate structured Markdown notes from transcript text with Groq chat."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_DOCS_MODEL,
        detail: str = DEFAULT_DOCS_DETAIL,
        client: Any | None = None,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if not api_key:
            raise DocumentationError("Groq API key is required for Docs markdown generation.")
        if model not in DOCS_MODEL_PROFILES:
            raise DocumentationError(f"Unsupported Docs model: {model}")
        if detail not in DOCS_DETAIL_PROFILES:
            raise DocumentationError(f"Unsupported Docs detail: {detail}")
        self.model = model
        self.detail = detail
        self.profile = DOCS_MODEL_PROFILES[model]
        self.detail_profile = DOCS_DETAIL_PROFILES[detail]
        self.client = client or Groq(api_key=api_key)
        self._on_progress = on_progress
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def generate(self, transcript: str, *, source_name: str, language: str = "tr") -> DocumentationResult:
        transcript = (transcript or "").strip()
        if not transcript:
            raise DocumentationError("Transcript is empty.")
        language = self._normalize_language(language)

        chunks = self.split_text_for_model(transcript, self.model)
        if len(chunks) == 1:
            self._emit_progress("final", current=1, total=1)
            markdown = self._complete(
                self._final_messages(chunks[0], source_name=source_name, language=language, detail_instruction=str(self.detail_profile["instruction"])),
                max_tokens=self._token_limit("final_max_tokens"),
            )
        else:
            chunk_notes = []
            for index, chunk in enumerate(chunks):
                self._emit_progress("chunk", current=index + 1, total=len(chunks) + 1)
                chunk_notes.append(
                    self._complete(
                        self._chunk_messages(
                            chunk,
                            part=index + 1,
                            total=len(chunks),
                            language=language,
                            detail_instruction=str(self.detail_profile["instruction"]),
                        ),
                        max_tokens=self._token_limit("chunk_max_tokens"),
                    )
                )
            self._emit_progress("final", current=len(chunks) + 1, total=len(chunks) + 1)
            markdown = self._complete(
                self._final_messages(
                    "\n\n".join(chunk_notes),
                    source_name=source_name,
                    language=language,
                    reduced=True,
                    detail_instruction=str(self.detail_profile["instruction"]),
                ),
                max_tokens=self._token_limit("final_max_tokens"),
            )

        markdown = self._normalize_markdown(markdown, source_name)
        return DocumentationResult(
            markdown=markdown,
            model=self.model,
            detail=self.detail,
            calls=self.calls,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens,
        )

    def _emit_progress(self, phase: str, *, current: int, total: int) -> None:
        if self._on_progress:
            self._on_progress({"phase": phase, "current": current, "total": total})

    def _token_limit(self, base_key: str) -> int:
        multiplier_key = "final_multiplier" if base_key == "final_max_tokens" else "chunk_multiplier"
        return max(256, int(int(self.profile[base_key]) * float(self.detail_profile[multiplier_key])))

    def _complete(self, messages: list[dict[str, str]], *, max_tokens: int = 3600) -> str:
        try:
            response = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                temperature=0.2,
                max_tokens=max_tokens,
            )
            self._record_usage(response)
            content = response.choices[0].message.content
        except Exception as exc:  # pragma: no cover - SDK exception types vary by version.
            raise DocumentationError(f"Docs generation failed: {exc}") from exc
        if not isinstance(content, str) or not content.strip():
            raise DocumentationError("Docs generation returned empty content.")
        return content.strip()

    @classmethod
    def split_text_for_model(cls, text: str, model: str) -> list[str]:
        profile = DOCS_MODEL_PROFILES.get(model, DOCS_MODEL_PROFILES[DEFAULT_DOCS_MODEL])
        chunk_chars = int(profile["chunk_chars"])
        return cls._split_text(text, chunk_chars)

    @staticmethod
    def estimate_calls(transcript_chars: int, model: str) -> int:
        profile = DOCS_MODEL_PROFILES.get(model, DOCS_MODEL_PROFILES[DEFAULT_DOCS_MODEL])
        chunk_chars = int(profile["chunk_chars"])
        chunk_count = max(1, (max(0, transcript_chars) + chunk_chars - 1) // chunk_chars)
        return 1 if chunk_count == 1 else chunk_count + 1

    @staticmethod
    def _split_text(text: str, chunk_chars: int) -> list[str]:
        if len(text) <= chunk_chars:
            return [text]

        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        for paragraph in text.splitlines():
            part = paragraph.strip()
            if not part:
                continue
            if current and current_len + len(part) + 1 > chunk_chars:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            if len(part) > chunk_chars:
                for segment in GroqDocumentationGenerator._split_long_paragraph(part, chunk_chars):
                    if current:
                        chunks.append("\n".join(current))
                        current = []
                        current_len = 0
                    chunks.append(segment)
                continue
            current.append(part)
            current_len += len(part) + 1
        if current:
            chunks.append("\n".join(current))
        return chunks or [text[:chunk_chars]]

    @staticmethod
    def _split_long_paragraph(text: str, chunk_chars: int) -> list[str]:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", text) if part.strip()]
        if len(sentences) <= 1:
            return [text[start:start + chunk_chars] for start in range(0, len(text), chunk_chars)]

        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        for sentence in sentences:
            if len(sentence) > chunk_chars:
                if current:
                    chunks.append(" ".join(current))
                    current = []
                    current_len = 0
                chunks.extend(sentence[start:start + chunk_chars] for start in range(0, len(sentence), chunk_chars))
                continue
            if current and current_len + len(sentence) + 1 > chunk_chars:
                chunks.append(" ".join(current))
                current = []
                current_len = 0
            current.append(sentence)
            current_len += len(sentence) + 1
        if current:
            chunks.append(" ".join(current))
        return chunks

    def _record_usage(self, response: Any) -> None:
        self.calls += 1
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        self.prompt_tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
        self.completion_tokens += int(getattr(usage, "completion_tokens", 0) or 0)
        self.total_tokens += int(getattr(usage, "total_tokens", 0) or 0)

    @staticmethod
    def _chunk_messages(
        chunk: str,
        *,
        part: int,
        total: int,
        language: str,
        detail_instruction: str,
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You create faithful structured notes from transcript sections. "
                    "Do not invent facts. Keep names, dates, decisions, tasks, and open questions."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Output language: {GroqDocumentationGenerator._language_instruction(language)}\n"
                    f"Detail level instruction: {detail_instruction}\n"
                    f"Transcript part {part}/{total}:\n\n{chunk}\n\n"
                    "Return compact Markdown notes for this part only."
                ),
            },
        ]

    @staticmethod
    def _final_messages(
        text: str,
        *,
        source_name: str,
        language: str,
        detail_instruction: str,
        reduced: bool = False,
    ) -> list[dict[str, str]]:
        source_kind = "section notes" if reduced else "transcript"
        section_lines = "\n".join(GroqDocumentationGenerator._section_headings(language))
        empty_instruction = GroqDocumentationGenerator._empty_section_instruction(language)
        return [
            {
                "role": "system",
                "content": (
                    "You turn meeting, lecture, or long audio transcripts into useful Markdown documents. "
                    "Be concise, preserve important detail, and never add unsupported information. "
                    f"If a section has no evidence, write '{empty_instruction}' instead of inventing content."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Write the output in this language: {GroqDocumentationGenerator._language_instruction(language)}.\n"
                    "Use Markdown section headings in that output language.\n"
                    f"Source file name: {source_name}\n"
                    f"Input type: {source_kind}\n\n"
                    f"Detail level instruction: {detail_instruction}\n\n"
                    "Create a clean Markdown document with exactly these sections:\n"
                    f"{section_lines}\n\n"
                    f"Input:\n{text}"
                ),
            },
        ]

    @staticmethod
    def _language_instruction(language: str) -> str:
        normalized = GroqDocumentationGenerator._normalize_language(language)
        return str(DOCS_OUTPUT_LANGUAGES[normalized]["instruction"])

    @staticmethod
    def _section_headings(language: str) -> list[str]:
        normalized = GroqDocumentationGenerator._normalize_language(language)
        return [str(section) for section in DOCS_OUTPUT_LANGUAGES[normalized]["sections"]]

    @staticmethod
    def _empty_section_instruction(language: str) -> str:
        normalized = GroqDocumentationGenerator._normalize_language(language)
        return str(DOCS_OUTPUT_LANGUAGES[normalized]["empty"])

    @staticmethod
    def _normalize_language(language: str) -> str:
        normalized = (language or DEFAULT_DOCS_OUTPUT_LANGUAGE).strip().lower()
        if normalized not in DOCS_OUTPUT_LANGUAGES:
            raise DocumentationError(f"Unsupported Docs output language: {language}")
        return normalized

    @staticmethod
    def _normalize_markdown(markdown: str, source_name: str) -> str:
        text = markdown.strip()
        if not text.startswith("#"):
            text = f"# {source_name}\n\n{text}"
        return text + "\n"
