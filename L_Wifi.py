#!/usr/bin/env python3
import subprocess
import threading
import time
import os
import signal
import random
import re

# Конфигурация
INTERFACE = input("Введите имя беспроводного интерфейса (например, wlan0mon): ")
NUM_APS = int(input("Введите количество точек доступа для создания: "))
ESSID_BASE = input("Введите базовое имя ESSID для точек доступа: ")

# Список доступных каналов (избегаем перекрытия)
AVAILABLE_CHANNELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

def choose_channel(used_channels):
    """Выбирает канал, избегая перекрытия с уже используемыми."""
    available_channels = [ch for ch in AVAILABLE_CHANNELS if ch not in used_channels] # Исключаем использованные
    if not available_channels:
        print("[-] Все каналы заняты или перекрываются.  Будем использовать случайный канал.")
        return random.choice(AVAILABLE_CHANNELS)  # Используем случайный из всех, если все заняты.
    return random.choice(available_channels)


def generate_mac():
    """Генерирует случайный MAC-адрес."""
    mac = [ 0x00, 0x16, 0x3e,
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0xff),
            random.randint(0x00, 0xff) ]
    return ':'.join(map(lambda x: "%02x" % x, mac))

def create_virtual_interface(base_interface, ap_number):
    """Создает виртуальный интерфейс для каждой точки доступа."""
    vif_name = f"{base_interface}ap{ap_number}"
    try:
        # Создаем виртуальный интерфейс
        subprocess.run(["sudo", "iw", "dev", base_interface, "interface", "add", vif_name, "type", "managed"], check=True)
        print(f"[+] Создан виртуальный интерфейс {vif_name}")
        return vif_name
    except subprocess.CalledProcessError as e:
        print(f"[-] Ошибка при создании виртуального интерфейса: {e}")
        return None

def set_mac_address(interface):
    """Устанавливает случайный MAC-адрес для указанного интерфейса."""
    try:
        # Отключаем интерфейс
        subprocess.run(["sudo", "ip", "link", "set", interface, "down"], check=True)
        # Меняем MAC-адрес
        new_mac = generate_mac()
        subprocess.run(["sudo", "ip", "link", "set", interface, "address", new_mac], check=True)
        # Включаем интерфейс
        subprocess.run(["sudo", "ip", "link", "set", interface, "up"], check=True)
        print(f"[+] MAC-адрес интерфейса {interface} изменен на {new_mac}")
        return new_mac
    except subprocess.CalledProcessError as e:
        print(f"[-] Ошибка при изменении MAC-адреса: {e}")
        return None

def start_fake_ap(interface, essid, channel):
    """Запускает airbase-ng для создания поддельной точки доступа."""
    try:
        print(f"[+] Запуск поддельной точки доступа: Interface={interface}, ESSID={essid}, Channel={channel}")
        subprocess.run(["sudo", "airbase-ng", "-e", essid, "-c", str(channel), interface], check=True)
    except subprocess.CalledProcessError as e:
        print(f"[-] Ошибка при запуске airbase-ng для {essid}: {e}")

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

def remove_virtual_interface(interface):
    """Удаляет виртуальный интерфейс."""
    try:
        subprocess.run(["sudo", "iw", "dev", interface, "del"], check=True)
        print(f"[+] Виртуальный интерфейс {interface} удален.")
    except subprocess.CalledProcessError as e:
        print(f"[-] Ошибка при удалении виртуального интерфейса: {e}")

if __name__ == "__main__":
    # Список уже использованных каналов
    used_channels = []
    ap_interfaces = []  # Список для хранения имен виртуальных интерфейсов
    ap_macs = {}  # Словарь для хранения MAC-адресов для каждой AP
    ap_channels = {} #Словарь для хранения канала каждой AP

    # Создаем и запускаем точки доступа в отдельных потоках
    threads = []
    for i in range(1, NUM_APS + 1):
        # Создаем виртуальный интерфейс
        virtual_interface = create_virtual_interface(INTERFACE, i)
        if not virtual_interface:
            print(f"[-] Не удалось создать виртуальный интерфейс для AP {i}. Пропуск.")
            continue
        ap_interfaces.append(virtual_interface)  # Добавляем в список

        # Устанавливаем MAC-адрес для виртуального интерфейса (один раз!)
        mac_address = set_mac_address(virtual_interface)
        if not mac_address:
            print(f"[-] Не удалось установить MAC-адрес для AP {i}. Пропуск.")
            remove_virtual_interface(virtual_interface)  # Удаляем интерфейс, если не удалось установить MAC
            ap_interfaces.remove(virtual_interface) # Убираем из списка интерфейсов
            continue  # Пропускаем эту AP

        ap_macs[virtual_interface] = mac_address  # Сохраняем MAC-адрес

        # Выбираем канал (один раз!)
        channel = choose_channel(used_channels)
        used_channels.append(channel)  # Добавляем канал в список использованных
        ap_channels[virtual_interface] = channel #Сохраняем канал

        # Запускаем airbase-ng
        thread = threading.Thread(target=start_fake_ap, args=(virtual_interface, f"{ESSID_BASE}-{i}", channel))
        threads.append(thread)
        thread.start()

    # Ждем завершения всех потоков (Ctrl+C для остановки)
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\n[+] Остановка поддельных точек доступа...")
        for interface in ap_interfaces:
            stop_airbase_ng(interface)
            remove_virtual_interface(interface)
        print("[+] Завершение...")
