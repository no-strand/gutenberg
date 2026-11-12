"""Fontes disponíveis na barra do editor e na seleção tipográfica do leitor.

Os nomes são mantidos no HTML salvo como classes (não como estilo inline arbitrário).
"""

FONTES_NOMEADAS = {
    'fonte-atkinson-hyperlegible': ('Atkinson Hyperlegible', "'Atkinson Hyperlegible', Arial, sans-serif", 'fonte-sans'),
    'fonte-inter': ('Inter', 'Inter, Arial, sans-serif', 'fonte-sans'),
    'fonte-source-sans-3': ('Source Sans 3', "'Source Sans 3', Arial, sans-serif", 'fonte-sans'),
    'fonte-noto-sans': ('Noto Sans', "'Noto Sans', Arial, sans-serif", 'fonte-sans'),
    'fonte-ibm-plex-sans': ('IBM Plex Sans', "'IBM Plex Sans', Arial, sans-serif", 'fonte-sans'),
    'fonte-arial': ('Arial', 'Arial, Helvetica, sans-serif', 'fonte-sans'),
    'fonte-roboto': ('Roboto', 'Roboto, Arial, sans-serif', 'fonte-sans'),
    'fonte-literata': ('Literata', 'Literata, Georgia, serif', 'fonte-serif'),
    'fonte-source-serif-4': ('Source Serif 4', "'Source Serif 4', Georgia, serif", 'fonte-serif'),
    'fonte-noto-serif': ('Noto Serif', "'Noto Serif', Georgia, serif", 'fonte-serif'),
    'fonte-georgia': ('Georgia', "Georgia, 'Times New Roman', serif", 'fonte-serif'),
    'fonte-times-new-roman': ('Times New Roman', "'Times New Roman', Times, serif", 'fonte-serif'),
    'fonte-ibm-plex-mono': ('IBM Plex Mono', "'IBM Plex Mono', Consolas, monospace", 'fonte-mono'),
    'fonte-jetbrains-mono': ('JetBrains Mono', "'JetBrains Mono', Consolas, monospace", 'fonte-mono'),
    'fonte-source-code-pro': ('Source Code Pro', "'Source Code Pro', Consolas, monospace", 'fonte-mono'),
    'fonte-consolas': ('Consolas', "Consolas, 'Courier New', monospace", 'fonte-mono'),
    'fonte-courier-new': ('Courier New', "'Courier New', Courier, monospace", 'fonte-mono'),
}
CLASSES_FONTES_EDITOR = frozenset({"fonte-sans", "fonte-serif", "fonte-mono", *FONTES_NOMEADAS})
FONTES_CSS_EDITOR = {nome: css for nome, (_, css, _) in FONTES_NOMEADAS.items()}
FONTES_DOCX_EDITOR = {nome: titulo for nome, (titulo, _, _) in FONTES_NOMEADAS.items()}
FONTES_CATEGORIAS_EDITOR = {nome: categoria for nome, (_, _, categoria) in FONTES_NOMEADAS.items()}
