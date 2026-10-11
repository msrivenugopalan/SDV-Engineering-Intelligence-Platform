
import tkinter as tk
from tkinter import ttk
import serial
import json
import threading
import queue
import time

PORT = "COM9"
BAUD_RATE = 115200

# Communication between the serial thread and Tkinter
telemetry_queue = queue.Queue()

def serial_reader():
    """Read STM32 messages without blocking the GUI."""
    try:
        with serial.Serial(PORT, BAUD_RATE, timeout=1) as stm32:
            time.sleep(2)
            stm32.reset_input_buffer()

            while not stop_event.is_set():
                raw = stm32.readline()

                if not raw:
                    continue

                message = raw.decode(
                    "utf-8", errors="replace"
                ).strip()

                try:
                    data = json.loads(message)
                    telemetry_queue.put(data)
                except json.JSONDecodeError:
                    continue

    except serial.SerialException as exc:
        telemetry_queue.put({
            "type": "error",
            "message": str(exc)
        })

def update_dashboard():
    """Update widgets on Tkinter's main thread."""
    while not telemetry_queue.empty():
        data = telemetry_queue.get()

        if data.get("type") == "error":
            connection_label.config(
                text="Connection error",
                foreground="red"
            )
            continue

        connection_label.config(
            text="STM32 connected",
            foreground="green"
        )

        if "engine_temp" in data:
            engine_label.config(
                text=f'{data["engine_temp"]} °C'
            )

        if "battery_voltage" in data:
            battery_label.config(
                text=f'{data["battery_voltage"]} V'
            )

    root.after(100, update_dashboard)

def close_app():
    stop_event.set()
    root.destroy()

root = tk.Tk()
root.title("SDV Hardware Integration Test")
root.geometry("420x260")

stop_event = threading.Event()

ttk.Label(
    root, text="SDV Engineering Platform",
    font=("Arial", 16, "bold")
).pack(pady=15)

connection_label = ttk.Label(
    root, text="Connecting to STM32...",
    foreground="orange"
)
connection_label.pack(pady=5)

ttk.Label(root, text="Engine Temperature").pack()
engine_label = ttk.Label(root, text="Waiting...")
engine_label.pack()

ttk.Label(root, text="Battery Voltage").pack()
battery_label = ttk.Label(root, text="Waiting...")
battery_label.pack()

threading.Thread(
    target=serial_reader,
    daemon=True
).start()

root.after(100, update_dashboard)
root.protocol("WM_DELETE_WINDOW", close_app)
root.mainloop()
