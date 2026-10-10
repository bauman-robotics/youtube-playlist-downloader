# Экспорт cookies для обхода ошибки 403

## Firefox
1. Установите расширение "cookies.txt" 
2. Зайдите на youtube.com и авторизуйтесь
3. Нажмите на иконку расширения
4. Выберите "Export cookies"
5. Сохраните файл как `cookies.txt` в папку скрипта

## Chrome/Chromium
1. Установите расширение "Get cookies.txt LOCALLY"
2. Зайдите на youtube.com и авторизуйтесь
3. Нажмите на иконку расширения
4. Нажмите "Export Cookies"
5. Сохраните файл как `cookies.txt` в папку скрипта

## Edge
1. Установите расширение "cookies.txt" из Edge Add-ons
2. Зайдите на youtube.com и авторизуйтесь
3. Нажмите на иконку расширения
4. Нажмите "Export"
5. Сохраните файл как `cookies.txt` в папку скрипта

## Проверка cookies
```bash
head -5 cookies.txt
# Должны увидеть строки с доменом .youtube.com