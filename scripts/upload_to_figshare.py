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

DEFAULT_AUTHOR = {
    "name": "Yakushev, Alexey V."
}

BASE_TAGS = ["YUCT", "Yakushev Unified Coordination Theory", "coordination efficiency", "K_eff"]

# Если вы знаете ID категории, укажите его здесь
# CATEGORY_ID = 25197  # например, Classical Physics
CATEGORY_ID = None  # пока оставляем None, чтобы создать черновики без категории

def load_zenodo_metadata(folder_path):
    zenodo_file = folder_path / ".zenodo.json"
    if not zenodo_file.exists():
        return None
    try:
        with open(zenodo_file, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception:
        return None

def extract_abstract_from_tex(content):
    title_match = re.search(r'\\title\s*\{([^}]*)\}', content, re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""

    abstract = ""
    m = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', content, re.DOTALL)
    if m:
        abstract = m.group(1)
    else:
        m = re.search(r'\\textbf\s*\{[^}]*Abstract\s*:\s*\}(.*?)(?=\\vspace|\\section|\\begin\{|$)', content, re.DOTALL)
        if m:
            abstract = m.group(1)
        else:
            m = re.search(r'(?<!\\)Abstract\s*:\s*(.*?)(?=\\section|\\begin\{|$)', content, re.DOTALL)
            if m:
                abstract = m.group(1)

    if abstract:
        abstract = re.sub(r'\\[a-zA-Z]+\s*', '', abstract)
        abstract = re.sub(r'\{|\}', '', abstract)
        abstract = re.sub(r'\s+', ' ', abstract).strip()

    return title, abstract

def get_metadata_for_folder(folder_path):
    zenodo = load_zenodo_metadata(folder_path)
    if zenodo:
        title = zenodo.get("title", folder_path.name)
        description = zenodo.get("description", "")
        tags = zenodo.get("keywords", [])
        tags = list(set(BASE_TAGS + tags))
        
        authors = []
        for creator in zenodo.get("creators", [DEFAULT_AUTHOR]):
            author = {"name": creator.get("name", "Yakushev, Alexey V.")}
            if "affiliation" in creator and creator["affiliation"]:
                author["affiliation"] = str(creator["affiliation"])
            if "orcid" in creator and creator["orcid"]:
                author["orcid_id"] = creator["orcid"]
            authors.append(author)
        if not authors:
            authors = [DEFAULT_AUTHOR]
            
        custom_fields = {}
        for field in ["version", "language", "multilingual_version", "publication_date", "official_url"]:
            if field in zenodo:
                custom_fields[field] = zenodo[field]
        defined_type = "publication" if zenodo.get("upload_type") == "publication" else "dataset"
        return {
            "title": title,
            "description": description,
            "tags": tags,
            "authors": authors,
            "custom_fields": custom_fields,
            "defined_type": defined_type
        }
    else:
        tex_files = list(folder_path.glob("*_en.tex"))
        if tex_files:
            try:
                with open(tex_files[0], 'r', encoding='utf-8-sig', errors='ignore') as f:
                    content = f.read()
            except Exception:
                with open(tex_files[0], 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            title, abstract = extract_abstract_from_tex(content)
            if not title:
                title = folder_path.name
            return {
                "title": title,
                "description": abstract or f"YUCT Appendix: {folder_path.name}",
                "tags": BASE_TAGS.copy(),
                "authors": [{"name": DEFAULT_AUTHOR["name"]}],
                "custom_fields": {},
                "defined_type": "dataset"
            }
        else:
            return {
                "title": folder_path.name,
                "description": f"YUCT Appendix: {folder_path.name}",
                "tags": BASE_TAGS.copy(),
                "authors": [{"name": DEFAULT_AUTHOR["name"]}],
                "custom_fields": {},
                "defined_type": "dataset"
            }

def create_article(metadata):
    url = f"{BASE_URL}/account/articles"
    data = {
        "title": metadata.get("title", "Untitled"),
        "description": metadata.get("description", ""),
        "defined_type": metadata.get("defined_type", "dataset"),
        "public": False,
        "tags": metadata.get("tags", []),
        "authors": metadata.get("authors", [])
    }
    if CATEGORY_ID:
        data["categories"] = [CATEGORY_ID]
    if metadata.get("custom_fields"):
        data["custom_fields"] = metadata["custom_fields"]

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

    # Для теста обрабатываем только первые 3 папки (раскомментируйте, когда отладите)
    folders = folders[:3]

    for folder in sorted(folders):
        print(f"\n📂 Обработка: {folder.name}")

        metadata = get_metadata_for_folder(folder)
        print(f"  📄 Заголовок: {metadata['title'][:60]}...")
        print(f"  📄 Авторы: {', '.join(a['name'] for a in metadata['authors'])}")
        print(f"  📄 Ключевые слова: {', '.join(metadata['tags'][:5])}...")

        try:
            article_id = create_article(metadata)
        except Exception as e:
            print(f"  ❌ Ошибка создания: {e}")
            continue

        try:
            count = upload_files(article_id, folder)
            print(f"  📎 Загружено файлов: {count}")
            if count == 0:
                print(f"  ⚠️ Файлы не загружены! Черновик {article_id} пуст.")
                continue
        except Exception as e:
            print(f"  ❌ Ошибка загрузки: {e}")
            continue

        # Публикуем, только если указана категория
        if CATEGORY_ID:
            try:
                publish_article(article_id)
            except Exception as e:
                print(f"  ❌ Ошибка публикации: {e}")
                continue
        else:
            print(f"  ⏳ Публикация отложена (нет категории). Опубликуйте вручную.")

        time.sleep(3)

if __name__ == "__main__":
    main()