# -*- coding: utf-8 -*-

# -[ Imports ]-
import os
import re
import json
import logging
from enum import Enum
from urllib.parse import (
    urlparse,
    unquote,
)

import asyncio
import httpx
from textual import on
from textual.app import (
    App,
    ComposeResult,
)
from textual.widgets import (
    Select,
    Input,
    DataTable,
    Static,
    Header,
)
from textual.containers import Vertical

from utils import (
    platform,
    helpers,
)

# -[ Logging ]-
logging.basicConfig(
    filename="debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w"
)
# -[ Constants ]-

DOWNLOAD_LIMIT = 1


# -[ Enums ]-

class DL_STATUS(Enum):
    PENDING = "Pending"
    RESUME = "Resume"
    DOWNLOADING = "Downloading"
    COMPLETE = "Complete"
    ERROR = "Error"


# -[ Classes ]-
class Main(App):
    CSS_PATH = "tui.tcss"
    TITLE = "Rom Archives"
    DOWNLOAD_QUEUE_PATH = "download_queue.json"

    @staticmethod
    def get_downloaded_bytes(file_path: str) -> int:
        return os.path.getsize(file_path) if os.path.exists(file_path) else 0

    @staticmethod
    def get_rom_destination_path(system: str) -> str:
        return next(
            (
                platform["directory"]
                for platform in platform.CONF["platforms"]
                if platform["name"] == system
            ),
            None
        )

    @staticmethod
    def extract_filename(url: str) -> str:
        return unquote(urlparse(url).path.split('/')[-1])

    @staticmethod
    def create_directory(directory_path: str):
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

    async def check_download_queue(self):
        if os.path.exists(Main.DOWNLOAD_QUEUE_PATH):
            self.download_list = helpers.load_json(Main.DOWNLOAD_QUEUE_PATH)
            self.logger.info(f"Download queue loaded: {len(self.download_list)}")
            for rom in self.download_list:
                if rom["status"] == DL_STATUS.DOWNLOADING.value:
                    rom["status"] = DL_STATUS.RESUME.value
                row = self.downloads_table.add_row(
                    rom['name'],
                    rom['size'],
                    rom['status'],
                    "0%"
                )
                directory_path = Main.get_rom_destination_path(rom['platform'])
                await self.add_to_queue(
                    url=rom['url'],
                    row=row,
                    directory_path=directory_path
                )
                await self.process_queue()
        else:
            self.download_list = []
            self.logger.info("Download queue not found")
        return self.download_list

    def update_download_status(self, row, status: DL_STATUS):
        cell_coord = self.downloads_table.get_cell_coordinate(
            row,
            self.download_status_column
        )
        self.downloads_table.update_cell_at(
            cell_coord,
            status.value
        )
        self.download_list[cell_coord.row]["status"] = status.value

    def update_download_progress(self, row, progress):
        self.downloads_table.update_cell_at(
            self.downloads_table.get_cell_coordinate(
                row,
                self.download_progress_column
            ),
            f"{progress:.2f}%"
        )

    async def add_to_queue(self, url: str, row, directory_path: str):
        await self.queue.put((url, row, directory_path))

    async def process_queue(self):
        while not self.queue.empty():
            url, row, directory_path = await self.queue.get()
            asyncio.create_task(self.download_with_limit(
                url=url,
                row=row,
                directory_path=directory_path
            ))
            await asyncio.sleep(0.1)

    async def download_with_limit(self, url: str, row, directory_path: str):
        async with self.semaphore:
            await self.download_file(
                url=url,
                row=row,
                directory_path=directory_path
            )

    async def download_file(self, url: str, row, directory_path: str):
        filename = Main.extract_filename(url)
        full_path = os.path.join(directory_path, filename)

        downloaded_size = Main.get_downloaded_bytes(full_path)

        headers = {}
        if downloaded_size > 0:
            headers["Range"] = f"bytes={downloaded_size}-"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            async with client.stream("GET", url, headers=headers) as response:
                filename = Main.extract_filename(url)
                Main.create_directory(directory_path)
                full_path = os.path.join(directory_path, filename)

                total_size = \
                    int(response.headers.get("content-length", 0)) + \
                    downloaded_size

                write_mode = "ab" if downloaded_size > 0 else "wb"

                with open(full_path, write_mode) as file:
                    async for chunk in response.aiter_bytes(1024):
                        downloaded_size += len(chunk)
                        file.write(chunk)
                        progress = (downloaded_size / total_size) * 100
                        status = DL_STATUS.DOWNLOADING

                        self.update_download_status(
                            row,
                            status
                        )
                        self.update_download_progress(
                            row,
                            progress
                        )

                    if progress == 100:
                        status = DL_STATUS.COMPLETE
                    else:
                        status = DL_STATUS.ERROR
                    self.update_download_status(row, status)

    async def save_download_queue(self):
        if len(self.download_list) > 0:
            clean_list = [
                rom
                for rom in self.download_list
                if rom["status"] != DL_STATUS.COMPLETE.value
            ]
            if len(clean_list) == 0:
                self.logger.info("No incomplete downloads")
                if os.path.exists(Main.DOWNLOAD_QUEUE_PATH):
                    os.remove(Main.DOWNLOAD_QUEUE_PATH)
                return
            with open(Main.DOWNLOAD_QUEUE_PATH, "w") as file:
                json.dump(clean_list, file, indent=4)
        else:
            self.logger.info("No downloads to save")
            if os.path.exists(Main.DOWNLOAD_QUEUE_PATH):
                os.remove(Main.DOWNLOAD_QUEUE_PATH)

    def compose(self) -> ComposeResult:
        platforms = platform.get_platforms()
        self.platform_select = Select.from_values(platforms)
        self.search_input = Input()
        self.roms_table = DataTable(name="roms_table", id="roms_table")
        self.downloads_table = DataTable(
            name="downloads_table",
            id="downloads_table"
        )

        yield Vertical(
            Header(),
            Static("Platform"),
            self.platform_select,
            Static("Filter"),
            self.search_input,
            Static("Roms"),
            self.roms_table,
            Static("Downloads"),
            self.downloads_table,
        )

    async def on_mount(self):
        self.logger = logging.getLogger(__name__)
        self.queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(DOWNLOAD_LIMIT)

        table = self.roms_table
        table.cursor_type = "row"
        table.add_column("ROM")
        table.add_column("Size")

        downloads = self.downloads_table
        downloads.add_column("ROM")
        downloads.add_column("Size")
        self.download_status_column = downloads.add_column("Status", width=12)
        self.download_progress_column = downloads.add_column("Progress")
        self.download_list = await self.check_download_queue()

    async def on_unmount(self):
        await self.save_download_queue()

    @on(Input.Submitted)
    def on_search_submit(self, event: Input.Changed):
        regex_query = event.value
        rom_table = self.roms_table
        rom_table.clear()

        try:
            pattern = re.compile(regex_query, re.IGNORECASE)
            self.filtered_roms = list(
                filter(
                    lambda rom: pattern.search(rom['name']), self.fullset
                )
            )
            for rom in self.filtered_roms:
                rom_table.add_row(rom['name'], rom['size'])
        except re.error:
            for rom in self.fullset:
                rom_table.add_row(rom['name'], rom['size'])

    @on(Select.Changed)
    def on_platform_changed(self, event: Select.Changed):
        platform_name = event.value
        if platform_name != "":
            self.fullset = platform.load_platform(platform_name)
            rom_table = self.roms_table
            rom_table.clear()
            self.search_input.value = ""
            self.filtered_roms = self.fullset
            for rom in self.filtered_roms:
                rom_table.add_row(rom['name'], rom['size'])

    @on(DataTable.RowSelected)
    async def on_rom_selected(self, event: DataTable.RowSelected):
        current_index = event.cursor_row
        rom = self.filtered_roms[current_index]

        default_status = DL_STATUS.PENDING
        self.download_list.append({**rom, "status": default_status.value})
        row = self.downloads_table.add_row(
            rom['name'],
            rom['size'],
            default_status.value,
            "0%"
        )
        directory_path = Main.get_rom_destination_path(rom['platform'])
        await self.add_to_queue(
            url=rom['url'],
            row=row,
            directory_path=directory_path
        )
        await self.process_queue()

# -[ Private ]-

# -[ Public ]-

# -[ Main ]-


if __name__ == '__main__':
    asyncio.run(Main().run_async())
