import os
import requests
import json
import re
import time
from pathlib import Path

TOKEN = os.environ.get("FIGSHARE_TOKEN")
if not TOKEN:
    raise ValueError("❌ FIGSHARE_TOKEN не установлен")

HEADERS = {"Authorization": f"token {TOKEN}"}
BASE_URL = "https://api.figshare.com/v2"

EXCLUDE_DIRS = {".git", ".github", "scripts", "__pycache__"}
EXCLUDE_FILES = {".zenodo.json", ".DS_Store", "Thumbs.db"}

def extract_abstract_from_tex(content):
    """Извлекает заголовок и абстракт из содержимого TeX-файла."""
    # Заголовок
    title_match = re.search(r'\\title\s*\{([^}]*)\}', content, re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""

    # Абстракт — пробуем разные форматы
    abstract = ""
    # 1. \begin{abstract}...\end{abstract}
    m = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', content, re.DOTALL)
    if m:
        abstract = m.group(1)
    else:
        # 2. \textbf{Abstract:} ...
        m = re.search(r'\\textbf\s*\{[^}]*Abstract\s*:\s*\}(.*?)(?=\\vspace|\\section|\\begin\{|$)', content, re.DOTALL)
        if m:
            abstract = m.group(1)
        else:
            # 3. \textbf{Abstract} без двоеточия
            m = re.search(r'\\textbf\s*\{[^}]*Abstract\s*\}(?:\s*\\par|\s*\\noindent|\s*)\s*(.*?)(?=\\section|\\begin\{|$)', content, re.DOTALL)
            if m:
                abstract = m.group(1)
            else:
                # 4. Plain "Abstract:"
                m = re.search(r'(?<!\\)Abstract\s*:\s*(.*?)(?=\\section|\\begin\{|$)', content, re.DOTALL)
                if m:
                    abstract = m.group(1)

    # Очищаем абстракт от LaTeX-команд
    if abstract:
        abstract = re.sub(r'\\[a-zA-Z]+\s*', '', abstract)
        abstract = re.sub(r'\{|\}', '', abstract)
        abstract = re.sub(r'\s+', ' ', abstract).strip()

    return title, abstract

def get_abstract_for_folder(folder_path):
    """Ищет *_en.tex в папке и извлекает заголовок + абстракт."""
    tex_files = list(folder_path.glob("*_en.tex"))
    if not tex_files:
        return None, None
    try:
        with open(tex_files[0], 'r', encoding='utf-8-sig', errors='ignore') as f:
            content = f.read()
    except Exception:
        with open(tex_files[0], 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    return extract_abstract_from_tex(content)

def create_article(title, description):
    url = f"{BASE_URL}/account/articles"
    data = {
        "title": title,
        "description": description,
        "defined_type": "dataset",
        "public": False
        # categories не указываем — добавим вручную или позже
    }
    resp = requests.post(url, json=data, headers=HEADERS, timeout=30)
    if resp.status_code != 201:
        print(f"❌ Ошибка создания статьи: {resp.status_code} {resp.text}")
        resp.raise_for_status()
    article_id = resp.json()["entity_id"]
    print(f"  ✅ Создан черновик ID: {article_id}")
    return article_id

def upload_files(article_id, folder_path):
    folder_path = Path(folder_path)
    if not folder_path.exists():
        print(f"  ❌ Папка не существует: {folder_path}")
        return 0

    files_list = list(folder_path.rglob("*"))
    print(f"  📂 Найдено файлов в папке: {len(files_list)}")
    uploaded = 0

    for file_path in files_list:
        if not file_path.is_file():
            continue
        if file_path.name in EXCLUDE_FILES:
            print(f"  ⏭️ Пропущен: {file_path.name}")
            continue

        safe_name = file_path.name
        if safe_name.startswith("!") or " " in safe_name:
            safe_name = safe_name.replace("!", "").replace(" ", "_")
            print(f"  ⚠️ Переименован: {file_path.name} -> {safe_name}")

        # Шаг 1: Инициализация загрузки
        url = f"{BASE_URL}/account/articles/{article_id}/files"
        metadata = {"name": safe_name, "size": file_path.stat().st_size}
        headers = HEADERS.copy()
        headers["Content-Type"] = "application/json"
        resp = requests.post(url, data=json.dumps(metadata), headers=headers, timeout=30)

        if resp.status_code != 201:
            print(f"  ❌ Ошибка инициализации: {file_path.name} - {resp.status_code} {resp.text}")
            continue

        file_data = resp.json()
        if "location" not in file_data:
            print(f"  ❌ Нет location: {file_data}")
            continue

        # Шаг 2: Получение upload_url
        location_url = file_data["location"]
        file_info_resp = requests.get(location_url, headers=HEADERS)
        if file_info_resp.status_code != 200:
            print(f"  ❌ Ошибка получения информации о файле: {file_path.name} - {file_info_resp.status_code} {file_info_resp.text}")
            continue

        file_info = file_info_resp.json()
        upload_url = file_info.get("upload_url")
        if not upload_url:
            print(f"  ❌ Нет upload_url: {file_info}")
            continue

        # Шаг 3: Загрузка содержимого (с path=1)
        try:
            with open(file_path, "rb") as f:
                put_resp = requests.put(
                    upload_url + "/1",
                    data=f,
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=60
                )
                if put_resp.status_code != 200:
                    print(f"  ❌ Ошибка PUT: {file_path.name} - {put_resp.status_code} {put_resp.text}")
                    continue
        except Exception as e:
            print(f"  ❌ Исключение при загрузке: {file_path.name} - {e}")
            continue

        # Шаг 4: Подтверждение загрузки
        file_id = file_info.get("id")
        if not file_id:
            print(f"  ❌ Нет file_id: {file_info}")
            continue

        complete_url = f"{BASE_URL}/account/articles/{article_id}/files/{file_id}"
        complete_resp = requests.post(complete_url, headers=HEADERS)
        if complete_resp.status_code not in (200, 202):
            print(f"  ❌ Ошибка подтверждения: {file_path.name} - {complete_resp.status_code} {complete_resp.text}")
            continue

        uploaded += 1
        print(f"  ✅ Загружен: {file_path.name} ({file_path.stat().st_size} байт)")
        time.sleep(0.3)

    return uploaded

def publish_article(article_id):
    url = f"{BASE_URL}/account/articles/{article_id}/publish"
    resp = requests.post(url, headers=HEADERS, timeout=30)
    if resp.status_code != 202:
        print(f"  ❌ Ошибка публикации: {resp.status_code} {resp.text}")
        return False
    print(f"  🚀 Опубликован! DOI будет присвоен в течение нескольких минут.")
    return True

def main():
    repo_root = Path(".")
    folders = [f for f in repo_root.iterdir() if f.is_dir() and f.name not in EXCLUDE_DIRS]
    if not folders:
        print("❌ Папки не найдены!")
        return

    print(f"📁 Найдено {len(folders)} папок для загрузки.")
    print("-" * 60)

    # Для теста можно обработать только первые 3 папки:
    folders = folders[:3]

    for folder in sorted(folders):
        print(f"\n📂 Обработка: {folder.name}")

        # Извлекаем абстракт из *_en.tex
        title, abstract = get_abstract_for_folder(folder)
        if not title:
            title = folder.name
        if not abstract:
            abstract = f"YUCT Appendix: {folder.name}"

        # Создаём статью
        try:
            article_id = create_article(title, abstract)
        except Exception as e:
            print(f"  ❌ Ошибка создания: {e}")
            continue

        # Загружаем файлы
        try:
            count = upload_files(article_id, folder)
            print(f"  📎 Загружено файлов: {count}")
            if count == 0:
                print(f"  ⚠️ Файлы не загружены! Черновик {article_id} пуст.")
                continue
        except Exception as e:
            print(f"  ❌ Ошибка загрузки: {e}")
            continue

        # Публикуем
        try:
            publish_article(article_id)
        except Exception as e:
            print(f"  ❌ Ошибка публикации: {e}")
            continue

        time.sleep(3)

if __name__ == "__main__":
    main()