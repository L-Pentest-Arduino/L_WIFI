#!/usr/bin/env python3
import subprocess
import threading
import time
import os
import signal

print("""
\033[34m
  _   _  ____   ____        __  __       _      
 | \ | |/ ___| |  _ \      |  \/  | __ _| |_ __
 |  \| | |     | |_) |_____| |\/| |/ _` | | '_ \
 | |\  | |___  |  _ < |_____| |  | | (_| | | | | |
 |_| \_|\____| |_| \_\      |_|  |_|\__,_|_|_| |_|

              _       
             (_)      
              _ _ __  
             | | '_ \\ 
             | | | | |
             |_|_| |_|

      \033[32m 📶  📶  📶   L_WIFI   📶  📶  📶 \033[0m \n""")


def start_fake_ap(interface, essid, channel, ap_number):
    """Запускает airbase-ng для создания поддельной точки доступа."""
    try:
        print(f"[+] Запуск поддельной точки доступа {ap_number}: ESSID={essid}, Channel={channel}")
        subprocess.run(["sudo", "airbase-ng", "-e", essid, "-c", str(channel), interface], check=True)
    except subprocess.CalledProcessError as e:
        print(f"[-] Ошибка при запуске airbase-ng для {ap_number}: {e}")

def stop_airbase_ng(interface):
    """Останавливает все процессы airbase-ng, работающие на указанном интерфейсе."""
    try:
        # Получаем список PID процессов airbase-ng
        result = subprocess.run(["pgrep", "-f", f"airbase-ng {interface}"], capture_output=True, text=True, check=True)
        pids = result.stdout.strip().split("\n")

        # Убиваем каждый процесс
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)  # SIGTERM - сигнал для корректного завершения
                print(f"[+] Процесс airbase-ng с PID {pid} остановлен.")
            except OSError as e:
                print(f"[-] Не удалось остановить процесс airbase-ng с PID {pid}: {e}")

    except subprocess.CalledProcessError as e:
        # Если pgrep не нашел процессов, это не ошибка
        if e.returncode == 1:
            print("[-] Процессы airbase-ng не найдены.")
        else:
            print(f"[-] Ошибка при поиске процессов airbase-ng: {e}")

if __name__ == "__main__":
    # Запрашиваем параметры у пользователя
    interface = input("Введите имя беспроводного интерфейса (например, wlan0): ")
    while True:
        try:
            num_aps = int(input("Введите количество точек доступа для создания: "))
            if num_aps > 0:
                break
            else:
                print("Пожалуйста, введите положительное число.")
        except ValueError:
            print("Пожалуйста, введите число.")

    essid_base = input("Введите базовое имя ESSID для точек доступа: ")

    # Запускаем airbase-ng для каждой точки доступа в отдельном потоке
    threads = []
    for i in range(1, num_aps + 1):
        essid = f"{essid_base}-{i}"
        channel = i  # Можно сделать выбор канала более гибким, если нужно
        thread = threading.Thread(target=start_fake_ap, args=(interface, essid, channel, i))
        threads.append(thread)
        thread.start()

    # Ждем завершения всех потоков (Ctrl+C для остановки)
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\n[+] Остановка поддельных точек доступа...")
        stop_airbase_ng(interface)  # Останавливаем airbase-ng процессы
        print("[+] Завершение...")
