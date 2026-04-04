"""File system monitoring."""
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os


class Watcher:
    """Monitor folder for new MP3s."""

    def __init__(self, folder):
        self.folder = folder
        self.observer = Observer()
        self.new_files = []
        self.handler = self._Handler(self)

    def start(self):
        self.observer.schedule(self.handler, self.folder, recursive=True)
        self.observer.start()
        self.observer.join()

    def stop(self):
        self.observer.stop()
        self.observer.join()

    def get_new_files(self) -> list:
        result = self.new_files[:]
        self.new_files = []
        return result

    class _Handler(FileSystemEventHandler):
        def __init__(self, watcher):
            self.watcher = watcher

        def on_created(self, event):
            if event.src_path.lower().endswith(".mp3"):
                self.watcher.new_files.append(event.src_path)

        def on_moved(self, event):
            if event.dest_path.lower().endswith(".mp3"):
                self.watcher.new_files.append(event.dest_path)
