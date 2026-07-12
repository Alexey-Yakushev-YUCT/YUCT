import os
import requests
import json
import time
from pathlib import Path

# --- НАСТРОЙКИ (измените под свою структуру) ---
# Укажите путь к ПАПКЕ, которую хотите загрузить (относительно корня репозитория)
FOLDER_NAME = "00. Yakushev's Law of Coordination. YUCT"
# Укажите имя КОНКРЕТНОГО PDF-файла внутри этой папки (английская версия)
FILE_NAME = "Yakushevs_Law_of_Coordination_YUCT_en.pdf"
# ------------------------------------------------

TOKEN = os.environ.get("FIGSHARE_TOKEN")
if not TOKEN:
    raise ValueError("❌ FIGSHARE_TOKEN не установлен")

HEADERS = {"Authorization": f"token {TOKEN}"}
BASE_URL = "https://api.figshare.com/v2"

def create_article(title, description):
    """Создаёт черновик статьи."""
    url = f"{BASE_URL}/account/articles"
    data = {
        "title": title,
        "description": description,
        "defined_type": "dataset",
        "public": False
    }
    resp = requests.post(url, json=data, headers=HEADERS, timeout=30)
    if resp.status_code != 201:
        print(f"❌ Ошибка создания статьи: {resp.status_code} {resp.text}")
        resp.raise_for_status()
    article_id = resp.json()["entity_id"]
    print(f"  ✅ Создан черновик ID: {article_id}")
    return article_id

def upload_single_file(article_id, file_path):
    """Загружает один файл в Figshare (с правильным API)."""
    if not file_path.exists():
        print(f"  ❌ Файл не найден: {file_path}")
        return False

    file_size = file_path.stat().st_size
    file_name = file_path.name

    print(f"  📄 Загружаю файл: {file_name} ({file_size} байт)")

    # Шаг 1: Инициализация загрузки (POST /files)
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

    # Шаг 2: Получение информации о файле (GET по location)
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

    # Шаг 3: Загрузка содержимого (PUT по upload_url)
    # ВАЖНО: В некоторых случаях нужно указать номер части (path=1)
    try:
        with open(file_path, "rb") as f:
            # Пробуем загрузить как один "часть"
            put_resp = requests.put(
                upload_url,
                data=f,
                headers={"Content-Type": "application/octet-stream"},
                timeout=60
            )
            if put_resp.status_code == 200:
                print(f"  ✅ Файл загружен успешно!")
                return True
            else:
                print(f"  ❌ Ошибка PUT: {put_resp.status_code} {put_resp.text}")
                # Пробуем альтернативный вариант с параметром path=1
                print(f"  🔄 Пробую с path=1...")
                with open(file_path, "rb") as f2:
                    put_resp2 = requests.put(
                        upload_url + "/1",
                        data=f2,
                        headers={"Content-Type": "application/octet-stream"},
                        timeout=60
                    )
                    if put_resp2.status_code == 200:
                        print(f"  ✅ Файл загружен успешно (с path=1)!")
                        return True
                    else:
                        print(f"  ❌ Ошибка PUT с path=1: {put_resp2.status_code} {put_resp2.text}")
                        return False
    except Exception as e:
        print(f"  ❌ Исключение при загрузке: {e}")
        return False

def publish_article(article_id):
    """Публикует статью."""
    url = f"{BASE_URL}/account/articles/{article_id}/publish"
    resp = requests.post(url, headers=HEADERS, timeout=30)
    if resp.status_code != 202:
        print(f"  ❌ Ошибка публикации: {resp.status_code} {resp.text}")
        return False
    print(f"  🚀 Опубликован! DOI будет присвоен в течение нескольких минут.")
    return True

def main():
    # Формируем полный путь к файлу
    folder_path = Path(FOLDER_NAME)
    file_path = folder_path / FILE_NAME

    if not file_path.exists():
        print(f"❌ Файл не найден: {file_path}")
        print(f"   Убедитесь, что папка '{FOLDER_NAME}' и файл '{FILE_NAME}' существуют.")
        return

    print(f"📁 Тестовая загрузка одного файла")
    print(f"   Папка: {FOLDER_NAME}")
    print(f"   Файл: {FILE_NAME}")
    print("-" * 60)

    try:
        # 1. Создаём черновик
        article_id = create_article(
            title=f"Test: {FILE_NAME}",
            description=f"Тестовая загрузка файла {FILE_NAME} из папки {FOLDER_NAME}"
        )

        # 2. Загружаем файл
        success = upload_single_file(article_id, file_path)
        if not success:
            print(f"  ⚠️ Файл не загружен. Черновик {article_id} останется пустым.")
            return

        # 3. Публикуем
        publish_article(article_id)

        print(f"\n✅ Готово! Проверьте Figshare: https://figshare.com/account/articles/{article_id}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()