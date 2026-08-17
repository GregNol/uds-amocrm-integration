#!/usr/bin/env python3
"""Скрипт сборки архива виджета для загрузки в amoCRM.

Создает dist/uds_amocrm_widget.zip с правильной структурой файлов:
- manifest.json
- script.js
- style.css
- i18n/ru.json
- i18n/en.json
- images/logo.png
- images/icon.png
- images/icon_small.png
"""
import json
import os
import zipfile


def build_widget():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    widget_dir = os.path.join(base_dir, "widget")
    dist_dir = os.path.join(base_dir, "dist")
    os.makedirs(dist_dir, exist_ok=True)

    output_zip = os.path.join(dist_dir, "uds_amocrm_widget.zip")

    # Валидация manifest.json
    manifest_path = os.path.join(widget_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Файл {manifest_path} не найден!")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
        widget_info = manifest_data.get("widget", {})
        print(f"Сборка виджета: {widget_info.get('name')} v{widget_info.get('version')}")

    # Создание zip-архива (все файлы относительно папки widget/)
    file_count = 0
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(widget_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, widget_dir)
                zip_file.write(file_path, arcname=rel_path)
                print(f"  + {rel_path}")
                file_count += 1

    file_size_kb = os.path.getsize(output_zip) / 1024
    print(f"\nУспешно упаковано {file_count} файлов.")
    print(f"Архив готов: {output_zip} ({file_size_kb:.1f} KB)")


if __name__ == "__main__":
    build_widget()
