import os
import requests
import time
from pathlib import Path

TOKEN = os.environ["FIGSHARE_TOKEN"]
HEADERS = {"Authorization": f"token {TOKEN}"}
BASE_URL = "https://api.figshare.com/v2"

EXCLUDE_DIRS = {".git", ".github", "scripts", "__pycache__"}

def create_article(title, description):
    """Создаёт черновик статьи и возвращает её ID."""
    url = f"{BASE_URL}/account/articles"
    data = {
        "title": title,
        "description": description,
        "defined_type": "dataset",
        "public": False
    }
    resp = requests.post(url, json=data, headers=HEADERS)
    if resp.status_code != 201:
        print(f"❌ Ошибка создания статьи: {resp.status_code} {resp.text}")
        resp.raise_for_status()
    article_id = resp.json()["entity_id"]
    print(f"  ✅ Создан черновик ID: {article_id}")
    return article_id

def upload_files(article_id, folder_path):
    """Загружает все файлы из папки в статью."""
    folder_path = Path(folder_path)
    if not folder_path.exists():
        print(f"  ❌ Папка не существует: {folder_path}")
        return 0
    
    files = list(folder_path.rglob("*"))
    print(f"  📂 Найдено файлов в папке: {len(files)}")
    uploaded = 0
    for file_path in files:
        if file_path.is_file():
            # Пропускаем служебные файлы
            if file_path.name in [".DS_Store", "Thumbs.db"]:
                continue
            url = f"{BASE_URL}/account/articles/{article_id}/files"
            with open(file_path, "rb") as f:
                files_payload = {"file": (file_path.name, f)}
                resp = requests.post(url, files=files_payload, headers=HEADERS)
                if resp.status_code == 201:
                    uploaded += 1
                    print(f"  ✅ Загружен: {file_path.name} ({file_path.stat().st_size} байт)")
                else:
                    print(f"  ❌ Ошибка загрузки: {file_path.name} - {resp.status_code} {resp.text}")
                time.sleep(0.3)
    return uploaded

def publish_article(article_id):
    """Публикует статью (выдаёт DOI)."""
    url = f"{BASE_URL}/account/articles/{article_id}/publish"
    resp = requests.post(url, headers=HEADERS)
    if resp.status_code != 202:
        print(f"  ❌ Ошибка публикации: {resp.status_code} {resp.text}")
        resp.raise_for_status()
    print(f"  🚀 Опубликован! DOI будет присвоен в течение нескольких минут.")
    return True

def main():
    repo_root = Path(".")
    folders = [f for f in repo_root.iterdir() if f.is_dir() and f.name not in EXCLUDE_DIRS]
    if not folders:
        print("❌ Папки с приложениями не найдены!")
        return
    
    print(f"📁 Найдено {len(folders)} папок для загрузки.")
    print("-" * 60)
    
    for folder in sorted(folders):
        title = folder.name.strip()
        description = f"YUCT Appendix: {title}"
        
        print(f"\n📂 Обработка: {title}")
        
        # 1. Создаём статью
        try:
            article_id = create_article(title, description)
        except Exception as e:
            print(f"  ❌ Ошибка создания: {e}")
            continue
        
        # 2. Загружаем файлы
        try:
            count = upload_files(article_id, folder)
            print(f"  📎 Загружено файлов: {count}")
            if count == 0:
                print(f"  ⚠️ ВНИМАНИЕ: Файлы не загружены! Черновик {article_id} будет пустым.")
                continue
        except Exception as e:
            print(f"  ❌ Ошибка загрузки файлов: {e}")
            continue
        
        # 3. Публикуем (получаем DOI)
        try:
            publish_article(article_id)
        except Exception as e:
            print(f"  ❌ Ошибка публикации: {e}")
            continue
        
        print(f"  ✅ Готово! DOI для {title} будет доступен в Figshare.")
        time.sleep(2)  # Увеличенная пауза, чтобы не перегружать API

if __name__ == "__main__":
    main()