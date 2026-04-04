import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class WatcherState:
    """Module-level state for folder watcher"""
    observer: Observer = None
    folder: str = None
    is_watching: bool = False
    new_files: list = []


class MP3EventHandler(FileSystemEventHandler):
    """Handle file system events for MP3 files"""

    def on_created(self, event):
        """Called when a file is created"""
        if event.is_directory:
            return
        if event.src_path.lower().endswith('.mp3'):
            WatcherState.new_files.append(event.src_path)

    def on_moved(self, event):
        """Called when a file is moved/renamed"""
        if event.is_directory:
            return
        if event.dest_path.lower().endswith('.mp3'):
            WatcherState.new_files.append(event.dest_path)


def start_watching(folder_path: str) -> bool:
    """
    Start watching folder for new MP3 files.
    Args:
        folder_path: absolute path to folder to watch
    Returns:
        True if started successfully, False otherwise
    """
    try:
        if WatcherState.is_watching:
            # Already watching, stop first
            stop_watching()

        if not os.path.isdir(folder_path):
            raise ValueError(f"Path is not a directory: {folder_path}")

        # Create observer and event handler
        WatcherState.observer = Observer()
        event_handler = MP3EventHandler()
        WatcherState.observer.schedule(
            event_handler,
            folder_path,
            recursive=True
        )

        # Start observer
        WatcherState.observer.start()
        WatcherState.folder = folder_path
        WatcherState.is_watching = True
        WatcherState.new_files = []

        return True

    except Exception as e:
        raise Exception(f"Failed to start watcher: {str(e)}")


def stop_watching() -> bool:
    """
    Stop watching folder.
    Returns:
        True if stopped successfully
    """
    try:
        if WatcherState.observer is not None and WatcherState.is_watching:
            WatcherState.observer.stop()
            WatcherState.observer.join(timeout=5)

        WatcherState.is_watching = False
        WatcherState.folder = None
        WatcherState.observer = None

        return True

    except Exception as e:
        raise Exception(f"Failed to stop watcher: {str(e)}")


def get_new_files() -> list:
    """
    Return and clear the list of newly detected MP3 files.
    Returns:
        list of file paths
    """
    files = WatcherState.new_files.copy()
    WatcherState.new_files = []
    return files
