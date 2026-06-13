import re


class TerminologyMapper:
    def map_text(self, text: str) -> str:
        # 1. Alias rule: O @champion Alias -> A Tag @champion
        def replace_alias_with_o(match: re.Match[str]) -> str:
            article = match.group(1) or ""
            name = match.group(2)
            new_article = "A " if article.startswith("O") else "a "
            new_tag = (
                "Tag" if article.istitle() or article.isupper() else "tag"
            )
            return f"{new_article}{new_tag} {name}"

        text = re.sub(
            r"\b([Oo])\s+([@a-zA-Z0-9_-]+)\s+[Aa]lias\b",
            replace_alias_with_o,
            text,
        )

        # Matches: 'name Alias' or 'Alias name' -> 'tag name'
        text = re.sub(
            r"\b([@a-zA-Z0-9_-]+)\s+[Aa]lias\b",
            r"tag \1",
            text,
        )
        text = re.sub(
            r"\b[Aa]lias\s+([@a-zA-Z0-9_-]+)\b",
            r"tag \1",
            text,
        )

        # 2. Batch rule: Batch Noun -> Noun em Batch
        def replace_batch(match: re.Match[str]) -> str:
            noun = match.group(1)
            return f"{noun} em Batch"

        text = re.sub(
            r"\b[Bb]atch\s+([a-zA-Z0-9_Á-ú]+)\b",
            replace_batch,
            text,
        )

        # 3. Term replacements
        replacements = [
            (r"\bimplantar para\b", "implantação para"),
            (r"\bImplantar para\b", "Implantação para"),
            (r"\bdeploy\b", "implantação"),
            (r"\bDeploy\b", "Implantação"),
            (r"\bgasoduto\b", "pipeline"),
            (r"\bgasodutos\b", "pipelines"),
            (r"\bGasoduto\b", "Pipeline"),
            (r"\bGasodutos\b", "Pipelines"),
        ]
        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text)

        return text
