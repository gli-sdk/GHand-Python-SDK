# Copyright 2026 GLITech
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import hashlib
import logging
import os
import platform
import tempfile
import threading
import time

import netifaces
import pysoem


logger = logging.getLogger("ghand.ethercat_client")


class EthercatClient:
    """Low-level EtherCAT client wrapping pysoem.

    Each :class:`GHand` instance owns an independent ``EthercatClient`` so that
    multiple adapters can drive different hands concurrently.
    """

    _DISCONNECT_SETTLE_SEC = 0.1

    @staticmethod
    def _matches_expected_size(actual_size: int, expected_size) -> bool:
        """Return whether an actual PDO size satisfies the expected size spec."""
        if expected_size is None:
            return True
        if isinstance(expected_size, int):
            return actual_size == expected_size
        return actual_size in expected_size

    @staticmethod
    def _format_expected_size(expected_size) -> str:
        """Format a scalar or collection of expected PDO sizes for logging."""
        if expected_size is None:
            return "any"
        if isinstance(expected_size, int):
            return str(expected_size)
        return ", ".join(str(size) for size in expected_size)

    def __init__(self):
        """Initialize a new EthercatClient instance."""
        self._master = self._create_master()
        self._actual_wkc = 0
        self._pd_thread_stop_event = threading.Event()
        self._ch_thread_stop_event = threading.Event()
        self._connected = False
        self._slave = None
        # Connection health flag
        self._connection_lost = False
        # Thread-safety lock
        self._data_lock = threading.RLock()
        # Exclusive adapter lock
        self._lock_file = None
        self._lock_file_path = None

    def _create_master(self):
        """Create a fresh SOEM master with SDK-owned runtime flags."""
        master = pysoem.Master()
        master.in_op = False
        master.do_check_state = False
        return master

    @property
    def input_size(self) -> int:
        """Return the mapped input PDO size in bytes."""
        return len(self._slave.input) if self._slave is not None else 0

    @property
    def output_size(self) -> int:
        """Return the mapped output PDO size in bytes."""
        return len(self._slave.output) if self._slave is not None else 0

    def __del__(self):
        """Destructor — ensures the adapter lock is released."""
        try:
            self._cleanup_connection(switch_to_init=False)
        except Exception:
            pass  # ignore errors during destruction

    def _get_lock_file_path(self, adapter_name: str) -> str:
        """Build the filesystem path for the adapter lock file.

        Args:
            adapter_name: Network adapter name.

        Returns:
            Absolute path to the lock file.
        """
        # Use an MD5 hash of the adapter name to avoid special-character issues
        adapter_hash = hashlib.md5(adapter_name.encode()).hexdigest()
        system = platform.system()
        if system == "Windows":
            lock_dir = tempfile.gettempdir()
        else:
            lock_dir = "/tmp"
        return os.path.join(lock_dir, f"ghand_ethernet_{adapter_hash}.lock")

    def _acquire_lock(self, adapter_name: str) -> bool:
        """Acquire an exclusive filesystem lock for the given adapter.

        Args:
            adapter_name: Network adapter name.

        Returns:
            True if the lock was acquired, False if another process holds it.
        """
        lock_path = self._get_lock_file_path(adapter_name)
        try:
            if platform.system() == "Windows":
                try:
                    import msvcrt

                    self._lock_file = open(lock_path, 'w')
                    msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    self._lock_file.write(f"{os.getpid()}\n{adapter_name}\n")
                    self._lock_file.flush()
                    self._lock_file_path = lock_path
                    return True
                except (IOError, OSError):
                    if self._lock_file:
                        self._lock_file.close()
                    self._lock_file = None
                    logger.warning("Adapter %s is already locked by another process", adapter_name)
                    return False
            else:
                import fcntl

                self._lock_file = open(lock_path, 'w')
                try:
                    fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._lock_file.write(f"{os.getpid()}\n{adapter_name}\n")
                    self._lock_file.flush()
                    self._lock_file_path = lock_path
                    return True
                except (IOError, OSError):
                    if self._lock_file:
                        self._lock_file.close()
                    self._lock_file = None
                    logger.warning("Adapter %s is already locked by another process", adapter_name)
                    return False
        except Exception as e:
            logger.error("Error acquiring lock for adapter %s: %s", adapter_name, e)
            if self._lock_file:
                self._lock_file.close()
            self._lock_file = None
            return False

    def _release_lock(self):
        """Release the exclusive adapter lock and clean up the lock file."""
        if self._lock_file is not None:
            try:
                lock_path = self._lock_file_path
                self._lock_file.close()
                if lock_path and os.path.exists(lock_path):
                    try:
                        os.remove(lock_path)
                    except (OSError, IOError):
                        pass
            except Exception as e:
                logger.error("Error releasing lock: %s", e)
            finally:
                self._lock_file = None
                self._lock_file_path = None

    def _stop_threads(self) -> None:
        """Stop process-data and state-check threads if they are running."""
        self._pd_thread_stop_event.set()
        self._ch_thread_stop_event.set()
        thread_join_timeout = 5.0
        current = threading.current_thread()

        if (
            hasattr(self, 'proc_thread')
            and self.proc_thread.is_alive()
            and self.proc_thread is not current
        ):
            self.proc_thread.join(timeout=thread_join_timeout)
        if (
            hasattr(self, 'check_thread')
            and self.check_thread.is_alive()
            and self.check_thread is not current
        ):
            self.check_thread.join(timeout=thread_join_timeout)

        self._pd_thread_stop_event.clear()
        self._ch_thread_stop_event.clear()

    def _cleanup_connection(self, switch_to_init: bool = True) -> None:
        """Close SOEM resources, release the adapter lock, and reset state."""
        self._stop_threads()

        with self._data_lock:
            if switch_to_init:
                try:
                    if self._slave:
                        self._slave.state = pysoem.INIT_STATE
                        self._slave.write_state()
                        time.sleep(0.01)
                except Exception as e:
                    logger.warning("Failed to switch slave to INIT state: %s", e)

            if self._master:
                try:
                    self._master.close()
                    logger.info("Master closed")
                except Exception as e:
                    logger.warning("Failed to close master: %s", e)

            self._slave = None
            self._connected = False
            self._actual_wkc = 0
            self._connection_lost = False

        self._release_lock()
        self._master = self._create_master()

    @staticmethod
    def _check_slave(slave):
        """Monitor and recover a single slave's state.

        Args:
            slave: pysoem slave object.
        """
        if slave.state == (pysoem.SAFEOP_STATE + pysoem.STATE_ERROR):
            slave.state = pysoem.SAFEOP_STATE + pysoem.STATE_ACK
            slave.write_state()
        elif slave.state == pysoem.SAFEOP_STATE:
            slave.state = pysoem.OP_STATE
            slave.write_state()
        elif slave.state > pysoem.NONE_STATE:
            if slave.reconfig():
                slave.is_lost = False
        elif not slave.is_lost:
            slave.state_check(pysoem.OP_STATE)
            if slave.state == pysoem.NONE_STATE:
                slave.is_lost = True
        else:
            pass
        if slave.is_lost:
            if slave.state == pysoem.NONE_STATE:
                if slave.recover():
                    slave.is_lost = False
            else:
                slave.is_lost = False

    def _processdata_thread(self):
        """Background thread that sends and receives cyclic process data."""
        invalid_wkc_count = 0
        max_invalid_wkc_count = 30

        while not self._pd_thread_stop_event.is_set():
            try:
                with self._data_lock:
                    self._master.send_processdata()
                    self._actual_wkc = self._master.receive_processdata(15_000)
                if self._actual_wkc < 1:
                    logger.warning("Invalid working counter (WKC): %s", self._actual_wkc)
                    invalid_wkc_count += 1
                    if invalid_wkc_count >= max_invalid_wkc_count:
                        logger.error(
                            "Too many invalid WKC counts (%s), disconnecting...",
                            invalid_wkc_count,
                        )
                        self._connection_lost = True
                        # Spawn a detached thread to avoid dead-lock
                        threading.Thread(target=self.disconnect).start()
                        self._pd_thread_stop_event.set()
                        break
                else:
                    invalid_wkc_count = 0
            except Exception as e:
                logger.error("Error in process data thread: %s", e)
            time.sleep(0.01)

    def _check_thread(self):
        """Background thread that monitors slave state and triggers recovery."""
        while not self._ch_thread_stop_event.is_set():
            try:
                need_check = False
                with self._data_lock:
                    if self._master.in_op and (
                        self._actual_wkc < 1 or self._master.do_check_state
                    ):
                        self._master.do_check_state = False
                        self._master.read_state()
                        need_check = True

                if need_check:
                    with self._data_lock:
                        for i, slave in enumerate(self._master.slaves):
                            if slave.state != pysoem.OP_STATE:
                                self._master.do_check_state = True
                                self._check_slave(slave)
            except Exception as e:
                logger.error("Error in check thread: %s", e)
            time.sleep(0.01)

    def recv_data(self) -> bytes:
        """Receive the latest TPDO bytes from the slave.

        Returns:
            Raw input process data.

        Raises:
            RuntimeError: If the device is disconnected.
        """
        with self._data_lock:
            if self._connection_lost:
                raise RuntimeError("Device disconnected")
            if self._slave is not None:
                return self._slave.input
            else:
                raise RuntimeError("Device disconnected")

    def send_data(self, data: bytes):
        """Send RPDO bytes to the slave.

        Args:
            data: Raw output process data.

        Raises:
            RuntimeError: If the device is disconnected.
        """
        with self._data_lock:
            if self._connection_lost:
                raise RuntimeError("Device disconnected")
            if self._slave is not None:
                hex_str = ' '.join(f'{b:02x}' for b in data)
                logger.debug("Sending %d bytes:\n%s", len(data), hex_str)
                self._slave.output = data
            else:
                raise RuntimeError("Device disconnected")

    def search(self) -> list[str]:
        """Discover available network interfaces.

        Returns:
            List of adapter IDs.
        """
        logger.info("Searching for network interfaces...")
        ids = netifaces.interfaces()
        if platform.system() == 'Windows':
            for i in range(len(ids)):
                ids[i] = "\\Device\\NPF_" + ids[i]
        logger.info("Found %s network interface(s)", len(ids))
        return ids

    def connect(self, id) -> bool:
        """Open the specified adapter and initialize the EtherCAT master.

        Args:
            id: Adapter ID (interface name).

        Returns:
            True if the adapter is opened and at least one slave is found.
        """
        if self._connected:
            return True

        if not self._acquire_lock(id):
            logger.error("Failed to connect: adapter %s is already locked by another process", id)
            return False

        try:
            self._master.open(id)

            if not self._master.config_init() > 0:
                self._cleanup_connection(switch_to_init=False)
                return False
            self._connected = True
            self._slave = self._master.slaves[0]
            self._slave.is_lost = False
            self._master.read_state()
            return True
        except Exception as e:
            logger.error("Error connecting to device %s: %s", id, e)
            self._cleanup_connection(switch_to_init=False)
            return False

    def run(
        self,
        expected_input_size: int | None = None,
        expected_output_size: int | None = None,
    ) -> bool:
        """Transition the EtherCAT master to OP state and start cyclic threads.

        Args:
            expected_input_size: Expected TPDO size in bytes. If None, size check is skipped.
            expected_output_size: Expected RPDO size in bytes. If None, size check is skipped.

        Returns:
            True if the master reaches OP state successfully.
        """
        if not self._connected or self._slave is None:
            logger.error("Not connected or no slave configured")
            return False

        if self._master.state != pysoem.INIT_STATE:
            self._master.state = pysoem.INIT_STATE

        try:
            if len(self._master.slaves) > 0:
                slave = self._master.slaves[0]

                if slave.state != pysoem.INIT_STATE:
                    slave.state = pysoem.INIT_STATE
                    slave.write_state()
                    if slave.state_check(pysoem.INIT_STATE, timeout=100_000) != pysoem.INIT_STATE:
                        logger.error("Failed to enter INIT state. Current state: %s", slave.state)
                        self._cleanup_connection(switch_to_init=False)
                        return False

                config_result = self._master.config_init()
                if config_result <= 0:
                    logger.error("Config init failed with result: %s", config_result)
                    self._cleanup_connection(switch_to_init=False)
                    return False

                self._master.config_map()

                if not self._matches_expected_size(len(slave.input), expected_input_size):
                    logger.error("Expected input size error!")
                    logger.error(
                        "Expected input size(s): %s, actual input size: %s",
                        self._format_expected_size(expected_input_size),
                        len(slave.input),
                    )
                    self._cleanup_connection(switch_to_init=False)
                    return False

                if not self._matches_expected_size(len(slave.output), expected_output_size):
                    logger.error("Expected output size error!")
                    logger.error(
                        "Expected output size(s): %s, actual output size: %s",
                        self._format_expected_size(expected_output_size),
                        len(slave.output),
                    )
                    self._cleanup_connection(switch_to_init=False)
                    return False
            else:
                logger.warning("No slaves found")
                self._cleanup_connection(switch_to_init=False)
                return False
        except Exception as e:
            logger.error("Failed to configure PDO mapping: %s", e)
            self._cleanup_connection(switch_to_init=False)
            return False

        if self._master.state_check(pysoem.SAFEOP_STATE, timeout=500_000) != pysoem.SAFEOP_STATE:

            logger.error("Failed to enter SAFEOP state")
            for i, slave in enumerate(self._master.slaves):
                logger.error("Slave %s: %s", i, slave.name)
                logger.error("  Current state: %s", slave.state)
                logger.error("  Expected state: %s", pysoem.SAFEOP_STATE)
                logger.error(
                    "  AL status code: %s (%s)",
                    hex(slave.al_status),
                    pysoem.al_status_code_to_string(slave.al_status),
                )
                logger.error("  Input size: %s bytes", len(slave.input))
                logger.error("  Output size: %s bytes", len(slave.output))
            self._cleanup_connection(switch_to_init=False)
            return False

        self._master.state = pysoem.OP_STATE
        self._master.write_state()

        self.check_thread = threading.Thread(target=self._check_thread)
        self.check_thread.daemon = True
        self.check_thread.start()
        self.proc_thread = threading.Thread(target=self._processdata_thread)
        self.proc_thread.daemon = True
        self.proc_thread.start()

        self._master.read_state()
        if self._master.state_check(pysoem.OP_STATE, timeout=500_000) != pysoem.OP_STATE:
            logger.error("Failed to reach OP state")
            self._cleanup_connection(switch_to_init=True)
            return False

        self._master.in_op = True

        return True

    def disconnect(self):
        """Stop cyclic threads, set the slave to INIT, and close the master."""
        if self._connected or self._slave is not None or self._lock_file is not None:
            self._cleanup_connection(switch_to_init=True)
            time.sleep(self._DISCONNECT_SETTLE_SEC)

    def sdo_read(self, index, subindex=0):
        """Read a value from the slave's object dictionary via SDO.

        Args:
            index: Object dictionary index.
            subindex: Object dictionary sub-index. Defaults to 0.

        Returns:
            Raw bytes read from the slave.

        Raises:
            RuntimeError: If the device is disconnected.
        """
        with self._data_lock:
            if self._slave is None:
                raise RuntimeError("Device disconnected")
            return self._slave.sdo_read(index, subindex)

    def sdo_write(self, index, subindex, value):
        """Write a value to the slave's object dictionary via SDO.

        Args:
            index: Object dictionary index.
            subindex: Object dictionary sub-index.
            value: Raw bytes to write.

        Returns:
            Result of the SDO write operation.

        Raises:
            RuntimeError: If the device is disconnected.
        """
        with self._data_lock:
            if self._slave is None:
                raise RuntimeError("Device disconnected")
            return self._slave.sdo_write(index, subindex, value)
