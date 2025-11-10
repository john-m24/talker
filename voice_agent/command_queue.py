"""Thread-safe command queue used to bridge UI (Electron) and the Python agent."""

from queue import Queue, Empty
from typing import Optional, List
import threading


class _CommandQueue:
	_instance = None
	_lock = threading.Lock()

	def __new__(cls):
		if cls._instance is None:
			with cls._lock:
				if cls._instance is None:
					cls._instance = super().__new__(cls)
					cls._instance._queue = Queue()
		return cls._instance

	def put_command(self, command_text: str) -> None:
		if not isinstance(command_text, str):
			return
		text = command_text.strip()
		if not text:
			return
		self._queue.put(text)

	def try_get_command(self) -> Optional[str]:
		try:
			return self._queue.get_nowait()
		except Empty:
			return None

	def drain_commands(self, max_items: int = 100) -> List[str]:
		collected: List[str] = []
		for _ in range(max_items):
			try:
				collected.append(self._queue.get_nowait())
			except Empty:
				break
		return collected


_shared_queue = _CommandQueue()


def put_command(command_text: str) -> None:
	_shared_queue.put_command(command_text)


def try_get_command() -> Optional[str]:
	return _shared_queue.try_get_command()


def drain_commands(max_items: int = 100) -> List[str]:
	return _shared_queue.drain_commands(max_items=max_items)


