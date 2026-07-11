#!/usr/bin/env python3
"""
Извлекает заголовки и абстракты из всех *_en.tex файлов в папках,
создаёт единый ABSTRACTS.md с оглавлением.
"""

import os
import re
from pathlib import Path

def extract_title_and_abstract(tex_content):
    """Извлекает \title{...} и \begin{abstract}...\end{abstract} из LaTeX."""
    # Заголовок
    title_match = re.search(r'\\title\s*\{([^}]*)\}', tex_content, re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""

    # Абстракт
    abstract_match = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',
                               tex_content, re.DOTALL)
    if abstract_match:
        abstract = abstract_match.group(1).strip()
        # Убираем лишние команды LaTeX (например, \noindent, \\, фигурные скобки)
        abstract = re.sub(r'\\noindent\s*', '', abstract)
        abstract = re.sub(r'\\[a-zA-Z]+\s*', '', abstract)  # простые команды
        abstract = re.sub(r'\{|\}', '', abstract)
        abstract = re.sub(r'\s+', ' ', abstract).strip()
    else:
        abstract = ""

    return title, abstract

def main():
    repo_root = Path('.')
    abstracts_list = []

    # Проходим по всем подпапкам
    for folder in sorted(repo_root.iterdir()):
        if not folder.is_dir() or folder.name.startswith('.'):
            continue

        # Ищем первый попавшийся файл *_en.tex (можно взять любой)
        tex_files = list(folder.glob('*_en.tex'))
        if not tex_files:
            # Если нет *_en.tex, пропускаем папку
            continue

        tex_file = tex_files[0]  # берём первый (обычно единственный)
        try:
            with open(tex_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"Не удалось прочитать {tex_file}: {e}")
            continue

        title, abstract = extract_title_and_abstract(content)

        # Если абстракт не найден, попробуем взять первую часть документа
        if not abstract:
            # Просто берём первые 500 символов после \begin{document}
            doc_match = re.search(r'\\begin\{document\}(.*?)', content, re.DOTALL)
            if doc_match:
                snippet = doc_match.group(1)[:500]
                abstract = snippet.replace('\n', ' ').strip()
            else:
                abstract = "Abstract not found."

        if not title:
            # Используем имя папки как запасной вариант
            title = folder.name

        # Убираем лишние переносы строк в заголовке
        title = ' '.join(title.split())

        # Сохраняем
        abstracts_list.append({
            'folder': folder.name,
            'title': title,
            'abstract': abstract
        })

    # Теперь создаём ABSTRACTS.md
    with open('ABSTRACTS.md', 'w', encoding='utf-8') as f:
        f.write('# Abstracts of YUCT Appendices\n\n')
        f.write('This file contains the abstracts of all appendices (English versions).\n\n')
        f.write('---\n\n')

        for item in abstracts_list:
            f.write(f'## {item["title"]}\n\n')
            f.write(f'**Folder:** `{item["folder"]}`  \n\n')
            f.write(f'{item["abstract"]}\n\n')
            f.write('---\n\n')

    print(f"✅ Создан файл ABSTRACTS.md с {len(abstracts_list)} абстрактами.")

if __name__ == '__main__':
    main()