
import serial
import json
import time

PORT = "COM9"
BAUD_RATE = 115200

try:
    with serial.Serial(PORT, BAUD_RATE, timeout=1) as stm32:
        print(f"Connected to STM32 on {PORT}")
        print("Waiting for telemetry...\n")

        # Allow the serial connection to stabilize
        time.sleep(2)
        stm32.reset_input_buffer()

        while True:
            raw_data = stm32.readline()

            if not raw_data:
                continue

            message = raw_data.decode(
                "utf-8", errors="replace"
            ).strip()

            if not message:
                continue

            try:
                telemetry = json.loads(message)
                print("Received STM32 telemetry:")
                print(telemetry)
                print("-" * 40)

            except json.JSONDecodeError:
                print("Non-JSON message:", message)

except serial.SerialException as error:
    print("Could not connect to STM32.")
    print("Check the COM port and close PuTTY.")
    print("Details:", error)

except KeyboardInterrupt:
    print("\nSerial test stopped.")
