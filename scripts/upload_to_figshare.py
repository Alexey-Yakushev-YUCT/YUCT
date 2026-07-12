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

        # Шаг 1: Создаём запись файла
        url = f"{BASE_URL}/account/articles/{article_id}/files"
        metadata = {"name": safe_name, "size": file_path.stat().st_size}
        headers = HEADERS.copy()
        headers["Content-Type"] = "application/json"
        resp = requests.post(url, data=json.dumps(metadata), headers=headers, timeout=30)

        if resp.status_code != 201:
            print(f"  ❌ Ошибка создания записи: {file_path.name} - {resp.status_code} {resp.text}")
            continue

        file_data = resp.json()
        if "location" not in file_data:
            print(f"  ❌ Нет location! Полный ответ: {json.dumps(file_data, indent=2)}")
            continue

        # Шаг 2: Получаем upload_url из информации о файле
        location_url = file_data["location"]
        file_info_resp = requests.get(location_url, headers=HEADERS)
        if file_info_resp.status_code != 200:
            print(f"  ❌ Ошибка получения информации о файле: {file_path.name} - {file_info_resp.status_code} {file_info_resp.text}")
            continue

        file_info = file_info_resp.json()
        upload_url = file_info.get("upload_url")
        if not upload_url:
            print(f"  ❌ Нет upload_url в информации о файле: {file_info}")
            continue

        # Шаг 3: Загружаем содержимое по upload_url (PUT)
        with open(file_path, "rb") as f:
            put_resp = requests.put(upload_url, data=f, headers={"Content-Type": "application/octet-stream"}, timeout=60)
            if put_resp.status_code == 200:
                uploaded += 1
                print(f"  ✅ Загружен: {file_path.name} ({file_path.stat().st_size} байт)")
            else:
                print(f"  ❌ Ошибка PUT: {file_path.name} - {put_resp.status_code} {put_resp.text}")

        time.sleep(0.5)

    return uploaded