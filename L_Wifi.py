#!/usr/bin/env python3
import subprocess
import threading
import time
import os
import signal
import random

# Конфигурация
INTERFACE = input("Введите имя беспроводного интерфейса (например, wlan0): ")
NUM_APS = int(input("Введите количество точек доступа для создания: "))
ESSID_BASE = input("Введите базовое имя ESSID для точек доступа: ")

# Функция для выбора канала, избегая перекрытия
def choose_channel(used_channels):
    """Выбирает канал, избегая перекрытия с уже используемыми."""
    available_channels = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    # Удаляем перекрывающиеся каналы: если занят 6, удаляем 4, 5, 7, 8
    for channel in used_channels:
        if channel in available_channels:
            available_channels.remove(channel) # Убираем сам канал
            if channel - 1 in available_channels:
                available_channels.remove(channel - 1)
            if channel + 1 in available_channels:
                available_channels.remove(channel + 1)
    if available_channels:
        return random.choice(available_channels)
    else:
        print("[-] Все каналы заняты или перекрываются.  Будем использовать случайный канал.")
        return random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]) # Если все занято - случайный канал

def start_fake_ap(interface, essid, channel, ap_number):
    """Запускает airbase-ng для создания поддельной точки доступа."""
    try:
        print(f"[+] Запуск поддельной точки доступа {ap_number}: ESSID={essid}, Channel={channel}")
        subprocess.run(["sudo", "airbase-ng", "-e", essid, "-c", str(channel), interface], check=True)
    except subprocess.CalledProcessError as e:
        print(f"[-] Ошибка при запуске airbase-ng для {ap_number}: {e}")

def stop_airbase_ng(interface):
    """Останавливает все процессы airbase-ng."""
    try:
        result = subprocess.run(["pgrep", "-f", f"airbase-ng {interface}"], capture_output=True, text=True, check=True)
        pids = result.stdout.strip().split("\n")

        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)
                print(f"[+] Процесс airbase-ng с PID {pid} остановлен.")
            except OSError as e:
                print(f"[-] Не удалось остановить процесс airbase-ng с PID {pid}: {e}")

    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            print("[-] Процессы airbase-ng не найдены.")
        else:
            print(f"[-] Ошибка при поиске процессов airbase-ng: {e}")


if __name__ == "__main__":
    # Список уже используемых каналов
    used_channels = []

    # Запускаем airbase-ng для каждой точки доступа в отдельном потоке
    threads = []
    for i in range(1, NUM_APS + 1):
        essid = f"{ESSID_BASE}-{i}"
        channel = choose_channel(used_channels)  # Выбираем канал
        used_channels.append(channel)  # Добавляем канал в список использованных

        thread = threading.Thread(target=start_fake_ap, args=(INTERFACE, essid, channel, i))
        threads.append(thread)
        thread.start()

    # Ждем завершения всех потоков (Ctrl+C для остановки)
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\n[+] Остановка поддельных точек доступа...")
        stop_airbase_ng(INTERFACE)
        print("[+] Завершение...")
