import sys
import threading
import time

from ghand import ProductType, TactileSensorId
from ghand.ghand import CommType, GHand
from ghand.types import GHandError


class TactileDisplay:

    def __init__(self):
        self.hand = GHand(product_type=ProductType.G5, comm_type=CommType.RS485)
        self.connected = False
        self.tactile_opened = False
        self.running = False
        self.display_thread = None
        self.start_time = None  # Record start time

    def connect(self):
        self.connected = self.hand.open("auto")
        if not self.connected:
            print("Connection failed")
            return False
        print("Connection successful!")
        return True

    def tactile_open(self):
        if not self.connected:
            print("Please connect to the device first")
            return False

        tactile_connected = self.hand.tactile_open()
        if tactile_connected:
            print("Tactile sensor opened")
            self.tactile_opened = True
            return True
        else:
            print("Failed to open tactile sensor")
            return False

    def tactile_close(self):
        if self.tactile_opened:
            self.hand.tactile_close()
            print("Tactile sensor closed")
            self.tactile_opened = False

    def start_display(self):
        if not self.tactile_opened:
            print("Please open the tactile sensor first")
            return

        self.running = True
        self.start_time = time.time()  # Record start time
        self.display_thread = threading.Thread(target=self._display_loop)
        self.display_thread.start()

    def _display_loop(self):
        try:
            while self.running:
                # Use get_tactile_data to retrieve tactile data
                tactile_data = self.hand.get_tactile_data()

                if tactile_data:
                    # Access resultant force data for each finger via enum

                    thumb_data = tactile_data[TactileSensorId.THUMB]
                    ff_data = tactile_data[TactileSensorId.FF]
                    mf_data = tactile_data[TactileSensorId.MF]
                    rf_data = tactile_data[TactileSensorId.RF]
                    lf_data = tactile_data[TactileSensorId.LF]

                    # Get resultant force on XYZ axes for each finger
                    thumb_x, thumb_y, thumb_z = thumb_data.resultant_force
                    ff_x, ff_y, ff_z = ff_data.resultant_force
                    mf_x, mf_y, mf_z = mf_data.resultant_force
                    rf_x, rf_y, rf_z = rf_data.resultant_force
                    lf_x, lf_y, lf_z = lf_data.resultant_force

                    # Calculate elapsed time
                    elapsed_time = time.time() - self.start_time if self.start_time else 0
                    hours = int(elapsed_time // 3600)
                    minutes = int((elapsed_time % 3600) // 60)
                    seconds = int(elapsed_time % 60)
                    runtime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                    # Determine status
                    status = "Tactile sensor ON" if self.tactile_opened else "Tactile sensor OFF"

                    # Use ANSI escape sequences to overwrite previous data lines
                    sys.stdout.write(
                        "\033[10A"
                    )  # Move cursor up 8+2 lines (header + 5 fingers + separator + status line + 2 lines to ensure full coverage)
                    sys.stdout.write("\033[J")  # Clear from cursor position to bottom of screen

                    # Update data display
                    print("Finger   |     X-axis     |     Y-axis     |     Z-axis     |")
                    sys.stdout.write("\033[K")  # Clear current line
                    print(f"Thumb    | {thumb_x:8.2f}N   | {thumb_y:8.2f}N   | {thumb_z:8.2f}N")
                    sys.stdout.write("\033[K")  # Clear current line
                    print(f"Index    | {ff_x:8.2f}N   | {ff_y:8.2f}N   | {ff_z:8.2f}N")
                    sys.stdout.write("\033[K")  # Clear current line
                    print(f"Middle   | {mf_x:8.2f}N   | {mf_y:8.2f}N   | {mf_z:8.2f}N")
                    sys.stdout.write("\033[K")  # Clear current line
                    print(f"Ring     | {rf_x:8.2f}N   | {rf_y:8.2f}N   | {rf_z:8.2f}N")
                    sys.stdout.write("\033[K")  # Clear current line
                    print(f"Little   | {lf_x:8.2f}N   | {lf_y:8.2f}N   | {lf_z:8.2f}N")
                    sys.stdout.write("\033[K")  # Clear current line
                    print("-" * 70)
                    sys.stdout.write("\033[K")  # Clear current line
                    print(
                        f"Live updating... Press Ctrl+C to stop | Runtime: {runtime_str} | Status: {status}"
                    )
                    sys.stdout.write("\033[K")  # Clear current line

                    sys.stdout.flush()
                else:
                    # Calculate elapsed time
                    elapsed_time = time.time() - self.start_time if self.start_time else 0
                    hours = int(elapsed_time // 3600)
                    minutes = int((elapsed_time % 3600) // 60)
                    seconds = int(elapsed_time % 60)
                    runtime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                    # Determine status
                    status = "Tactile sensor ON" if self.tactile_opened else "Tactile sensor OFF"

                    sys.stdout.write("\033[10A")  # Move cursor up 8+2 lines
                    sys.stdout.write("\033[J")  # Clear from cursor position to bottom of screen
                    print(f"Tactile data retrieval failed or empty")
                    sys.stdout.write("\033[K")  # Clear current line
                    print("-" * 70)
                    sys.stdout.write("\033[K")  # Clear current line
                    print(
                        f"Live updating... Press Ctrl+C to stop | Runtime: {runtime_str} | Status: {status}"
                    )
                    sys.stdout.write("\033[K")  # Clear current line
                    sys.stdout.flush()

                time.sleep(0.015)  # Refresh every 15 ms

        except GHandError as e:
            print(f"\nDisplay thread error: {e}")

    def stop_display(self):
        self.running = False
        if self.display_thread:
            self.display_thread.join()

    def close(self):
        self.stop_display()
        self.tactile_close()
        if self.connected:
            self.hand.close()
        print("\nProgram ended")


def simple_tactile_display():
    display = TactileDisplay()

    if not display.connect():
        return

    print("\nCommand instructions:")
    print("  'o' or 'open'  - Open tactile sensor")
    print("  'c' or 'close' - Close tactile sensor")
    print("  's' or 'start' - Start displaying tactile data")
    print("  't' or 'stop'  - Stop displaying tactile data")
    print("  'q' or 'quit'  - Exit program")
    print("-" * 50)

    try:
        while True:
            command = input("\nPlease enter command: ").strip().lower()

            if command in ['o', 'open']:
                if not display.tactile_opened:
                    display.tactile_open()
                else:
                    print("Tactile sensor already open")

            elif command in ['c', 'close']:
                if display.tactile_opened:
                    display.tactile_close()
                else:
                    print("Tactile sensor already closed")

            elif command in ['s', 'start']:
                if display.tactile_opened:
                    if not display.running:
                        display.start_display()
                        print("Tactile data display started")
                        print(
                            "Note: Data is being displayed in real-time. Press Ctrl+C to return to command mode"
                        )
                    else:
                        print("Tactile data already being displayed")
                else:
                    print("Please open the tactile sensor first")

            elif command in ['t', 'stop']:
                if display.running:
                    display.stop_display()
                    print("Tactile data display stopped")
                else:
                    print("Tactile data not being displayed")

            elif command in ['q', 'quit']:
                print("Exiting program...")
                break

            else:
                print("Invalid command, please re-enter")

    except KeyboardInterrupt:
        print("\n\nUser interrupted, shutting down...")
    finally:
        display.close()


if __name__ == "__main__":
    simple_tactile_display()
