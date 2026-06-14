import re


class TerminologyMapper:
    def map_text(self, text: str) -> str:
        # 1. Alias rules
        # Matches: [Oo] name/TR0/champion Alias -> [Aa] Tag name/TR0/champion
        def replace_alias_with_o(match: re.Match[str]) -> str:
            article = match.group(1) or ""
            name = match.group(2)
            new_article = "A " if article.startswith("O") else "a "
            new_tag = (
                "Tag" if article.istitle() or article.isupper() else "tag"
            )
            return f"{new_article}{new_tag} {name}"

        text = re.sub(
            r"\b([Oo])\s+(@[a-zA-Z0-9_-]+|TR\d+|champion)\s+[Aa]lias\b",
            replace_alias_with_o,
            text,
        )

        # Matches: [Oo] alias name/TR0/champion -> [Aa] tag name/TR0/champion
        def replace_o_alias(match: re.Match[str]) -> str:
            article = match.group(1)
            name = match.group(2)
            new_article = "A " if article.startswith("O") else "a "
            new_tag = (
                "Tag" if article.istitle() or article.isupper() else "tag"
            )
            return f"{new_article}{new_tag} {name}"

        text = re.sub(
            r"\b([Oo])\s+[Aa]lias\s+(@[a-zA-Z0-9_-]+|TR\d+|champion)\b",
            replace_o_alias,
            text,
        )

        # Matches: [Uu]m alias name/TR0/champion -> [Uu]ma tag name/TR0/champion
        def replace_um_alias(match: re.Match[str]) -> str:
            article = match.group(1)
            name = match.group(2)
            new_article = "Uma " if article.startswith("U") else "uma "
            new_tag = "tag"
            return f"{new_article}{new_tag} {name}"

        text = re.sub(
            r"\b([Uu]m)\s+[Aa]lias\s+(@[a-zA-Z0-9_-]+|TR\d+|champion)\b",
            replace_um_alias,
            text,
        )

        # Matches: [Dd]o alias name/TR0/champion -> [Dd]a tag name/TR0/champion
        def replace_do_alias(match: re.Match[str]) -> str:
            prep = match.group(1)
            name = match.group(2)
            new_prep = "Da " if prep.startswith("D") else "da "
            new_tag = "tag"
            return f"{new_prep}{new_tag} {name}"

        text = re.sub(
            r"\b([Dd]o)\s+[Aa]lias\s+(@[a-zA-Z0-9_-]+|TR\d+|champion)\b",
            replace_do_alias,
            text,
        )

        # Matches: 'name Alias' -> 'tag name'
        text = re.sub(
            r"\b(@[a-zA-Z0-9_-]+|TR\d+|champion)\s+[Aa]lias\b",
            r"tag \1",
            text,
        )
        # Matches: 'Alias name' -> 'tag name'
        text = re.sub(
            r"\b[Aa]lias\s+(@[a-zA-Z0-9_-]+|TR\d+|champion)\b",
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
            (r"\bencanamento\b", "pipeline"),
            (r"\bencanamentos\b", "pipelines"),
            (r"\bEncanamento\b", "Pipeline"),
            (r"\bEncanamentos\b", "Pipelines"),
            (r"\bcaptador\b", "embarque"),
            (r"\bcaptadores\b", "embarques"),
            (r"\bCaptador\b", "Embarque"),
            (r"\bCaptadores\b", "Embarques"),
            (r"\bderiva de recurso\b", "drift de característica"),
            (r"\bderiva de recursos\b", "drift de característica"),
            (r"\bdrift característica\b", "drift de característica"),
            (r"\bdrift de recurso\b", "drift de característica"),
        ]
        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text)

        return text
