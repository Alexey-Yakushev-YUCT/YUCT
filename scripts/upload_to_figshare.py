import os
import requests
import json
import time
from pathlib import Path

# --- НАСТРОЙКИ (измените под свою структуру) ---
FOLDER_NAME = "00. Yakushev's Law of Coordination. YUCT"
FILE_NAME = "Yakushevs_Law_of_Coordination_YUCT_en.pdf"
CATEGORY_ID = 2  # Physical Sciences
# ------------------------------------------------

TOKEN = os.environ.get("FIGSHARE_TOKEN")
if not TOKEN:
    raise ValueError("❌ FIGSHARE_TOKEN не установлен")

HEADERS = {"Authorization": f"token {TOKEN}"}
BASE_URL = "https://api.figshare.com/v2"

def create_article(title, description):
    url = f"{BASE_URL}/account/articles"
    data = {
        "title": title,
        "description": description,
        "defined_type": "dataset",
        "public": False,
        "categories": [CATEGORY_ID]
    }
    resp = requests.post(url, json=data, headers=HEADERS, timeout=30)
    if resp.status_code != 201:
        print(f"❌ Ошибка создания статьи: {resp.status_code} {resp.text}")
        resp.raise_for_status()
    article_id = resp.json()["entity_id"]
    print(f"  ✅ Создан черновик ID: {article_id}")
    return article_id

def upload_single_file(article_id, file_path):
    if not file_path.exists():
        print(f"  ❌ Файл не найден: {file_path}")
        return False

    file_size = file_path.stat().st_size
    file_name = file_path.name

    print(f"  📄 Загружаю файл: {file_name} ({file_size} байт)")

    # Шаг 1: Инициализация загрузки
    url = f"{BASE_URL}/account/articles/{article_id}/files"
    metadata = {"name": file_name, "size": file_size}
    headers = HEADERS.copy()
    headers["Content-Type"] = "application/json"
    resp = requests.post(url, data=json.dumps(metadata), headers=headers, timeout=30)

    if resp.status_code != 201:
        print(f"  ❌ Ошибка инициализации: {resp.status_code} {resp.text}")
        return False

    file_data = resp.json()
    if "location" not in file_data:
        print(f"  ❌ Нет location в ответе: {file_data}")
        return False

    # Шаг 2: Получение upload_url
    location_url = file_data["location"]
    file_info_resp = requests.get(location_url, headers=HEADERS)
    if file_info_resp.status_code != 200:
        print(f"  ❌ Ошибка получения информации о файле: {file_info_resp.status_code} {file_info_resp.text}")
        return False

    file_info = file_info_resp.json()
    upload_url = file_info.get("upload_url")
    if not upload_url:
        print(f"  ❌ Нет upload_url в информации о файле: {file_info}")
        return False

    print(f"  📄 upload_url: {upload_url}")

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
                print(f"  ❌ Ошибка PUT: {put_resp.status_code} {put_resp.text}")
                return False
            print(f"  ✅ Содержимое загружено")
    except Exception as e:
        print(f"  ❌ Исключение при загрузке: {e}")
        return False

    # Шаг 4: Подтверждение завершения загрузки
    file_id = file_info.get("id")
    if not file_id:
        print(f"  ❌ Нет file_id в информации о файле: {file_info}")
        return False

    complete_url = f"{BASE_URL}/account/articles/{article_id}/files/{file_id}"
    complete_resp = requests.post(complete_url, headers=HEADERS)
    if complete_resp.status_code != 200:
        print(f"  ❌ Ошибка подтверждения загрузки: {complete_resp.status_code} {complete_resp.text}")
        return False

    print(f"  ✅ Загрузка подтверждена")
    return True

def publish_article(article_id):
    url = f"{BASE_URL}/account/articles/{article_id}/publish"
    resp = requests.post(url, headers=HEADERS, timeout=30)
    if resp.status_code != 202:
        print(f"  ❌ Ошибка публикации: {resp.status_code} {resp.text}")
        return False
    print(f"  🚀 Опубликован! DOI будет присвоен в течение нескольких минут.")
    return True

def main():
    folder_path = Path(FOLDER_NAME)
    file_path = folder_path / FILE_NAME

    if not file_path.exists():
        print(f"❌ Файл не найден: {file_path}")
        return

    print(f"📁 Тестовая загрузка одного файла")
    print(f"   Папка: {FOLDER_NAME}")
    print(f"   Файл: {FILE_NAME}")
    print(f"   Категория ID: {CATEGORY_ID}")
    print("-" * 60)

    try:
        article_id = create_article(
            title=f"Test: {FILE_NAME}",
            description=f"Тестовая загрузка файла {FILE_NAME} из папки {FOLDER_NAME}"
        )

        success = upload_single_file(article_id, file_path)
        if not success:
            print(f"  ⚠️ Файл не загружен. Черновик {article_id} останется пустым.")
            return

        publish_article(article_id)

        print(f"\n✅ Готово! Проверьте Figshare: https://figshare.com/account/articles/{article_id}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()