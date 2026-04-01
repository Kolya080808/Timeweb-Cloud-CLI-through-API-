# Timeweb-Cloud-CLI-through-API

Простенькая программка для управления серверами в Timeweb Cloud в CLI.

# Timeweb Cloud VPS CLI Manager

**Timeweb Cloud VPS CLI Manager** — это консольная утилита для управления облачными VPS серверами Timeweb Cloud через API.

## Возможности

- Просмотр списка VPS серверов
- Детальный просмотр информации по каждому серверу
- Управление статусом сервера (запуск, остановка, перезагрузка, жёсткая перезагрузка/выключение)
- Просмотр и графическое отображение метрик (CPU, RAM, диск, сеть)
- Поддержка интерактивного режима и аргументов командной строки

## Требования

- Python 3.8 или новее
- [rich](https://pypi.org/project/rich/) (для красивого вывода в терминал)

Установить необходимые зависимости можно командой:
```bash
pip install rich
```

## Установка

1. Скачайте файл `timeweb_cli.py` в удобное место.
2. Дайте права на запуск:
    ```bash
    chmod +x timeweb_cli.py
    ```

## Использование

1. Получите API-ключ на сайте Timeweb Cloud ([инструкция](https://timeweb.cloud/profile/api)).
2. Запустите утил��ту командой:
    ```bash
    ./timeweb_cli.py
    ```
   или явно через Python:
    ```bash
    python3 timeweb_cli.py
    ```
3. При первом запуске программа запросит ваш API-ключ (его можно также передать через переменную окружения `TIMEWEB_CLOUD_TOKEN` или флаг `--token`).

Примеры запуска:
```bash
export TIMEWEB_CLOUD_TOKEN=ваш_токен
./timeweb_cli.py
```
или
```bash
./timeweb_cli.py --token ваш_токен
```

## Флаги командной строки

- `--token` — передать API-ключ явно
- `--debug` — включить отладочный режим (вывод запросов к API)

## Используемые метрики

- CPU (загрузка процессора)
- Network request (входящий трафик)
- Network response (исходящий трафик)
- Disk (операции чтения/записи)
- RAM (занятость оперативной памяти)

## Скриншоты

<img width="830" height="661" alt="image" src="https://github.com/user-attachments/assets/a466771a-a222-4eff-b587-07067c0c7b70" />
<img width="868" height="949" alt="image" src="https://github.com/user-attachments/assets/8394cf6f-a482-4150-807d-ecfb216f035f" />


## Примечания

- Программа предназначена только для облачных VPS Timeweb Cloud.
- Для работы необходим действующий API-ключ с соответствующими правами.

## Лицензия

MIT

---

Автор: [Nikolay Kravtsov](https://github.com/Kolya080808)
